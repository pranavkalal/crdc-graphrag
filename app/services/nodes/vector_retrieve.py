"""Vector retrieval node for the LangGraph RAG agent.

This node calls the VectorService to run hybrid search (vector + keyword + RRF)
against the production Supabase pgvector store.

KEY FEATURE — Query Enrichment:
  On the HYBRID path, graph entities discovered in the previous node are
  appended to the search query.  This makes the vector search more targeted.

  Example:
    Original query:  "resistance management for Silverleaf Whitefly"
    Graph found:     Pyriproxyfen (Group 7C), Spirotetramat (Group 23)
    Enriched query:  "resistance management for Silverleaf Whitefly
                      Pyriproxyfen Group 7C Spirotetramat Group 23"

  The enriched query pulls back more relevant chunks about those specific
  chemicals, rather than generic whitefly content.
"""

from __future__ import annotations

import json
import logging

from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


def make_vector_retrieve_node(vector_service: VectorService, top_k: int = 6):
    """Factory that returns a vector_retrieve node function."""

    async def vector_retrieve(state: dict) -> dict:
        """Run hybrid search, optionally enriched with graph entities.

        Reads:  state["question"], state["intent"],
                state["graph_records"] (if hybrid path)
        Writes: state["enriched_query"], state["vector_chunks"],
                state["vector_context"]
        """
        question = state["question"]
        intent = state.get("intent", "vector_only")
        graph_records = state.get("graph_records", [])

        # ── Query enrichment for hybrid path ─────────────────────────
        enriched_query = question
        if intent == "hybrid" and graph_records:
            entity_names = _extract_entity_names(graph_records)
            if entity_names:
                enriched_query = f"{question} {' '.join(entity_names)}"
                logger.info(
                    "Enriched query with %d graph entities: %s",
                    len(entity_names), entity_names,
                )

        # ── Run hybrid search ────────────────────────────────────────
        try:
            results = await vector_service.hybrid_search(enriched_query, top_k=top_k)

            vector_context = _format_vector_context(results)

            logger.info("Vector retrieve: %d chunks returned", len(results))

            return {
                "enriched_query": enriched_query,
                "vector_chunks": results,
                "vector_context": vector_context,
            }

        except Exception as exc:
            logger.error("Vector retrieval failed: %s", exc)
            return {
                "enriched_query": enriched_query,
                "vector_chunks": [],
                "vector_context": "",
            }

    return vector_retrieve


def _extract_entity_names(records: list[dict]) -> list[str]:
    """Pull unique entity names from graph records to enrich vector query.

    Looks for common field names that contain entity identifiers.
    """
    names = set()
    entity_keys = {
        "name", "chemical", "pest", "disease", "weed", "variety",
        "beneficial", "acronym", "canonical_term", "group_code",
        "Chemical", "Pest", "Disease", "Weed", "Variety", "Beneficial",
    }

    for record in records:
        for key, value in record.items():
            if key.lower().replace("_", "") in {k.lower() for k in entity_keys}:
                if isinstance(value, str) and len(value) > 1:
                    names.add(value)

    return list(names)[:10]  # Cap at 10 to avoid bloating the query


def _format_vector_context(chunks: list[dict]) -> str:
    """Format retrieved text chunks into a context block for the LLM prompt."""
    if not chunks:
        return ""

    lines = [
        "=== DOCUMENT CONTEXT (Retrieved from Cotton Industry Manuals) ===",
        "",
    ]

    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        source = metadata.get("title", metadata.get("source", "Unknown"))
        page = chunk.get("page_number", "?")
        text = chunk.get("text", "").strip()

        lines.append(f"  [Source {i}: {source}, p.{page}]")
        lines.append(f"  {text[:800]}")  # Truncate very long chunks
        lines.append("")

    return "\n".join(lines)
