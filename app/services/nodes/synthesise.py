"""Synthesis node for the LangGraph RAG agent.

This is the FINAL node in the pipeline.  It takes the assembled prompt
(containing graph context + vector context + question) and calls Gemini
to generate a concise, citation-backed answer.
"""

from __future__ import annotations

import logging
import time

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a knowledgeable assistant for Australian cotton growers and researchers.
You answer questions using verified data from the CRDC Knowledge Graph and
official cotton industry manuals (ACPM, CPMG, IPM Guidelines).

Rules:
- Be factual and specific: name chemicals, MoA groups, threshold values, varieties.
- If Knowledge Graph facts are provided, treat them as verified ground truth.
- If document context is provided, reference the source document where possible.
- Do not invent chemical names, MoA group codes, or threshold values.
- If the information is insufficient, say so honestly.
- Answer in 3-6 concise sentences.
"""


def make_synthesise_node(gemini_api_key: str, gemini_model: str = "gemini-2.5-flash"):
    """Factory that returns a synthesise node function."""

    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=gemini_api_key,
        temperature=0.2,  # Slightly more natural than 0.0
    )

    async def synthesise(state: dict) -> dict:
        """Generate the final answer from the assembled prompt.

        Reads:  state["assembled_prompt"], state["question"]
        Writes: state["answer"], state["metadata"]
        """
        assembled_prompt = state.get("assembled_prompt", "")
        question = state["question"]

        t0 = time.perf_counter()

        messages = [
            ("system", _SYSTEM_PROMPT),
            ("human", assembled_prompt),
        ]

        result = await llm.ainvoke(messages)
        answer = result.content

        elapsed = time.perf_counter() - t0

        logger.info("Synthesis complete: %.2fs, %d chars", elapsed, len(answer))

        # Build metadata for evaluation and debugging
        metadata = {
            "synthesis_time_s": round(elapsed, 2),
            "answer_length": len(answer),
            "intent": state.get("intent", "unknown"),
            "graph_records_count": len(state.get("graph_records", [])),
            "vector_chunks_count": len(state.get("vector_chunks", [])),
            "cypher_query": state.get("cypher_query"),
            "enriched_query": state.get("enriched_query", question),
        }

        return {
            "answer": answer,
            "metadata": metadata,
        }

    return synthesise
