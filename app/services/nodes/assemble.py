"""Context assembly node for the LangGraph RAG agent.

This node merges the graph_context and vector_context into a single
unified prompt that the synthesis LLM will use to generate the final answer.

The 3-section prompt template is the core of the "context augmentation"
strategy — graph facts come first (as ground truth), then document chunks
(as supporting evidence), then the user's question.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def assemble_context(state: dict) -> dict:
    """Merge graph and vector contexts into a unified prompt.

    Reads:  state["question"], state["graph_context"], state["vector_context"]
    Writes: state["assembled_prompt"]
    """
    question = state["question"]
    graph_context = state.get("graph_context", "")
    vector_context = state.get("vector_context", "")

    sections = []

    if graph_context:
        sections.append(graph_context)

    if vector_context:
        sections.append(vector_context)

    if not sections:
        # Edge case: both retrievals returned nothing
        sections.append(
            "No relevant information was found in either the Knowledge Graph "
            "or the document database. Answer based on your general knowledge "
            "but clearly state that no specific sources were found."
        )

    combined_context = "\n\n".join(sections)

    assembled_prompt = (
        f"{combined_context}\n\n"
        f"=== USER QUESTION ===\n"
        f"{question}\n\n"
        f"Instructions: Answer the question using the context above. "
        f"If KNOWLEDGE GRAPH CONTEXT is present, treat those facts as verified "
        f"ground truth and prioritise them. Use DOCUMENT CONTEXT for additional "
        f"detail, procedures, and nuance. Be specific — cite exact chemical names, "
        f"values, and sources where available. Answer in 3-6 sentences."
    )

    # Log context composition for debugging
    has_graph = "yes" if graph_context else "no"
    has_vector = "yes" if vector_context else "no"
    logger.info(
        "Context assembled: graph=%s, vector=%s, total_chars=%d",
        has_graph, has_vector, len(assembled_prompt),
    )

    return {"assembled_prompt": assembled_prompt}
