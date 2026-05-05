"""Graph retrieval node for the LangGraph RAG agent.

This node reuses the existing GraphService to:
  1. Generate a Cypher query from the user's question (via Gemini)
  2. Execute it against Neo4j Aura
  3. Format the results into a structured context block

The formatted graph_context is later injected into the synthesis prompt
alongside any vector context — this is the "context augmentation" pattern.
"""

from __future__ import annotations

import json
import logging

from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


def make_graph_retrieve_node(graph_service: GraphService):
    """Factory that returns a graph_retrieve node function.

    Takes an already-initialised GraphService (Neo4j + Gemini are ready).
    """

    async def graph_retrieve(state: dict) -> dict:
        """Query the Knowledge Graph and format results as context.

        Reads:  state["question"]
        Writes: state["cypher_query"], state["graph_records"], state["graph_context"]
        """
        question = state["question"]

        try:
            result = await graph_service.query(question)

            cypher = result.get("cypher", "")
            records = result.get("records", [])
            record_count = result.get("record_count", 0)

            # Format records into a readable context block
            graph_context = _format_graph_context(question, records, cypher)

            logger.info(
                "Graph retrieve: %d records, cypher=%s",
                record_count, cypher[:100],
            )

            return {
                "cypher_query": cypher,
                "graph_records": records,
                "graph_context": graph_context,
            }

        except Exception as exc:
            logger.error("Graph retrieval failed: %s", exc)
            # Graceful fallback — don't crash the pipeline
            return {
                "cypher_query": None,
                "graph_records": [],
                "graph_context": "",
            }

    return graph_retrieve


def _format_graph_context(question: str, records: list[dict], cypher: str) -> str:
    """Turn raw Neo4j records into a structured text block for the LLM prompt.

    This is the key "context injection" — we format graph data as text that
    the synthesis LLM can read alongside the vector chunks.
    """
    if not records:
        return ""

    lines = [
        "=== KNOWLEDGE GRAPH CONTEXT (Verified Structured Facts) ===",
        "",
    ]

    # Show up to 25 records formatted as key-value pairs
    for i, record in enumerate(records[:25], 1):
        parts = []
        for key, value in record.items():
            if value is not None and value != "":
                parts.append(f"{key}: {value}")
        if parts:
            lines.append(f"  [{i}] {' | '.join(parts)}")

    lines.append("")
    lines.append(
        "The above facts are extracted from the CRDC Knowledge Graph "
        "and should be treated as verified ground truth."
    )

    return "\n".join(lines)
