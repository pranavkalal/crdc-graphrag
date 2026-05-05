"""Intent classification node for the LangGraph RAG agent.

This node analyses the user's question and determines:
  1. intent — which retrieval path to take (graph_only / vector_only / hybrid)
  2. detected_entities — named entities that can anchor graph queries

This is the ENTRY POINT of the LangGraph state machine.
"""

from __future__ import annotations

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Structured output schema for Gemini ──────────────────────────────────────

class IntentClassification(BaseModel):
    """Structured output from the intent classifier."""
    intent: str = Field(
        description=(
            "One of: 'graph_only', 'vector_only', or 'hybrid'. "
            "Use 'graph_only' when the question asks about specific entities, "
            "relationships, acronyms, definitions, or structured lookups. "
            "Use 'vector_only' when the question asks about procedures, "
            "best practices, guidelines, or long-form knowledge. "
            "Use 'hybrid' when the question needs both entity facts AND "
            "procedural/contextual knowledge."
        )
    )
    detected_entities: list[str] = Field(
        default_factory=list,
        description=(
            "Named entities from the question that exist in the cotton industry "
            "knowledge graph. Examples: pest names, chemical names, disease names, "
            "weed names, variety names, acronyms, glossary terms. "
            "Return an empty list if no specific entities are detected."
        ),
    )
    reasoning: str = Field(
        description="One sentence explaining why this intent was chosen."
    )


# ── Classification prompt ────────────────────────────────────────────────────

_CLASSIFY_PROMPT = """\
You are a query router for an Australian cotton industry knowledge system.
The system has TWO retrieval sources:

1. **Knowledge Graph (Neo4j)** — contains structured entities and relationships:
   - Pests, Chemicals, MoA Groups, Diseases, Beneficials, Weeds, Varieties,
     Regions, Traits, Crop Stages, Thresholds, Terms (glossary), Acronyms
   - Relationships: CONTROLLED_BY, BELONGS_TO, PREDATES, AFFECTS, HAS_THRESHOLD,
     HAS_RESISTANCE_TO, SUITED_TO, HAS_TRAIT, PRECEDES

2. **Vector Database (Supabase pgvector)** — contains ~50K text chunks from
   cotton industry manuals, guides, and reports. Good for procedures, guidelines,
   best practices, and long-form knowledge.

Classify the user's question into one of three intents:

- **graph_only**: The answer can be fully constructed from entity lookups and
  relationship traversals. Examples: "What chemicals control Green Mirids?",
  "What does IPM stand for?", "Which weeds are resistant to glyphosate?"

- **vector_only**: The answer requires prose, procedures, or contextual knowledge
  that wouldn't exist as structured graph data. Examples: "Describe best practices
  for irrigation scheduling", "What safety precautions for chemical application?"

- **hybrid**: The answer needs BOTH structured facts (entities, relationships) AND
  prose context (procedures, guidelines). Examples: "What resistance management
  strategies exist for Silverleaf Whitefly?" (needs chemicals FROM graph +
  strategies FROM documents)

Also extract any named entities from the question that might exist in the graph.

User question: {question}
"""


# ── Node function ────────────────────────────────────────────────────────────

def make_classify_node(gemini_api_key: str, gemini_model: str = "gemini-2.5-flash"):
    """Factory that returns a classify_intent node function.

    We use a factory so the LLM client is created once and reused.
    """
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=gemini_api_key,
        temperature=0.0,
    )
    classifier = llm.with_structured_output(IntentClassification)

    async def classify_intent(state: dict) -> dict:
        """Classify the user question and extract entities.

        Reads:  state["question"]
        Writes: state["intent"], state["detected_entities"]
        """
        question = state["question"]
        prompt = _CLASSIFY_PROMPT.format(question=question)

        result: IntentClassification = await classifier.ainvoke(prompt)

        logger.info(
            "Classified: intent=%s, entities=%s, reason=%s",
            result.intent, result.detected_entities, result.reasoning,
        )

        return {
            "intent": result.intent,
            "detected_entities": result.detected_entities,
        }

    return classify_intent
