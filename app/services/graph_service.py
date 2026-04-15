"""GraphQATool: Natural Language → Cypher → Neo4j → Synthesised Answer.

Pipeline:
  1. Gemini receives the question + graph schema context → outputs valid Cypher.
  2. Cypher is executed against Neo4j Aura.
  3. Gemini receives the raw records + original question → outputs a concise answer.
"""

from __future__ import annotations

import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.infrastructure.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# ── Graph schema context (injected into every Cypher-generation prompt) ──────

_SCHEMA = """
Node labels and key properties:
  Pest       {name, scientific_name, pest_type}
  Chemical   {name, chemical_type, trade_names, key_notes}
             chemical_type values for insecticides: NULL (not set)
             chemical_type values for harvest aids: 'defoliant', 'boll opener', 'desiccant'
  MoAGroup   {group_code, group_name}
  Disease    {name, pathogen, symptoms, favoured_by, management}
  Beneficial {name, scientific_name, beneficial_type}
  Crop       {name}

Relationship types:
  (Pest)-[:CONTROLLED_BY {resistance_status, beneficial_impact, max_applications, source}]->(Chemical)
  (Chemical)-[:BELONGS_TO]->(MoAGroup)
  (Disease)-[:AFFECTS]->(Crop)
  (Beneficial)-[:PREDATES]->(Pest)

Query tips:
  - Pest names: 'Cotton aphid', 'Helicoverpa', 'Green mirid', 'Two-spotted spider mite',
    'Wireworm', 'Green vegetable bug', 'Thrips', 'Silverleaf whitefly', 'Solenopsis mealybug'
  - Harvest aid chemicals (defoliants, boll openers, desiccants) are queried via:
    MATCH (c:Chemical) WHERE c.chemical_type IN ['defoliant', 'boll opener', 'desiccant'] RETURN c
  - Use case-insensitive matching: WHERE toLower(p.name) CONTAINS toLower($term)
  - Always use LIMIT (max 50) to avoid large result sets.
  - Return human-readable field names using AS aliases.
  - AVOID MATCH … WHERE … with unbound variables.
"""

# ── Pydantic schema for Cypher generation ────────────────────────────────────

class CypherQuery(BaseModel):
    """Structured output: a single valid read-only Cypher query."""
    cypher: str = Field(description="A valid, read-only Cypher query for Neo4j.")
    explanation: str = Field(description="One sentence explaining what this query does.")


# ── Service ──────────────────────────────────────────────────────────────────

class GraphService:
    """Translate natural language questions into Cypher, run against Neo4j,
    then synthesise a concise answer using Gemini."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        gemini_api_key: str,
        gemini_model: str = "gemini-2.5-flash",
    ) -> None:
        self._db = neo4j_client
        self._llm = ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=gemini_api_key,
            temperature=0.0,
        )
        self._cypher_chain = self._llm.with_structured_output(CypherQuery)

    # ── Step 1: NL → Cypher ─────────────────────────────────────────────────

    async def _generate_cypher(self, question: str) -> CypherQuery:
        prompt = (
            "You are a Neo4j Cypher expert for an Australian cotton IPM knowledge graph.\n"
            "Generate a single, read-only Cypher query (no MERGE/CREATE/DELETE) that answers "
            "the user's question.\n\n"
            f"Graph schema:\n{_SCHEMA}\n\n"
            f"User question: {question}\n\n"
            "Output a valid Cypher query and a one-sentence explanation."
        )
        return await self._cypher_chain.ainvoke(prompt)

    # ── Step 2: Execute Cypher ───────────────────────────────────────────────

    @staticmethod
    def _sanitise(cypher: str) -> str:
        """Strip markdown fencing and dangerous write clauses."""
        cypher = re.sub(r"```(?:cypher)?", "", cypher, flags=re.IGNORECASE).strip("`").strip()
        for forbidden in ("MERGE", "CREATE", "DELETE", "DETACH", "DROP", "SET"):
            if re.search(rf"\b{forbidden}\b", cypher, re.IGNORECASE):
                raise ValueError(f"Forbidden clause in generated Cypher: {forbidden}")
        return cypher

    async def _run_cypher(self, cypher: str) -> list[dict]:
        clean = self._sanitise(cypher)
        logger.info("Executing Cypher: %s", clean)
        try:
            return await self._db.run_query(clean)
        except Exception as exc:
            logger.error("Cypher execution error: %s", exc)
            raise

    # ── Step 3: Synthesise answer ────────────────────────────────────────────

    async def _synthesise(self, question: str, records: list[dict]) -> str:
        if not records:
            return "The graph did not return any results for that question. The data may not be in the current graph scope."

        records_str = json.dumps(records[:30], indent=2, default=str)
        prompt = (
            "You are a knowledgeable assistant for Australian cotton growers.\n"
            "Based on the following data retrieved from the CRDC Knowledge Graph, "
            "answer the user's question clearly and concisely. "
            "Refer to specific names and values from the data.\n\n"
            f"User question: {question}\n\n"
            f"Graph query results:\n{records_str}\n\n"
            "Write a clear, helpful answer in 3-5 sentences."
        )
        result = await self._llm.ainvoke(prompt)
        return result.content

    # ── Public interface ─────────────────────────────────────────────────────

    async def query(self, question: str) -> dict[str, object]:
        """Full pipeline: question → Cypher → records → answer."""
        cypher_obj = await self._generate_cypher(question)
        cypher = cypher_obj.cypher

        try:
            records = await self._run_cypher(cypher)
        except Exception as exc:
            return {
                "question": question,
                "cypher": cypher,
                "explanation": cypher_obj.explanation,
                "records": [],
                "answer": f"Query execution failed: {exc}",
                "record_count": 0,
            }

        answer = await self._synthesise(question, records)

        return {
            "question": question,
            "cypher": cypher,
            "explanation": cypher_obj.explanation,
            "records": records,
            "answer": answer,
            "record_count": len(records),
        }
