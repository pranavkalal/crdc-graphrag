"""LangGraph agent: orchestrates the GraphRAG pipeline.

This module defines the StateGraph that routes user questions through
the appropriate retrieval path(s) and produces a synthesised answer.

Three paths through the graph:

  graph_only:   classify → graph_retrieve → assemble → synthesise
  vector_only:  classify → vector_retrieve → assemble → synthesise
  hybrid:       classify → graph_retrieve → vector_retrieve → assemble → synthesise

Usage:
    agent = build_agent(settings, neo4j_client, vector_service)
    result = await agent.ainvoke({"question": "What chemicals control Green Mirids?"})
    print(result["answer"])
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import Settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.services.graph_service import GraphService
from app.services.nodes.assemble import assemble_context
from app.services.nodes.classify import make_classify_node
from app.services.nodes.graph_retrieve import make_graph_retrieve_node
from app.services.nodes.synthesise import make_synthesise_node
from app.services.nodes.vector_retrieve import make_vector_retrieve_node
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


# ── State schema ─────────────────────────────────────────────────────────────

class RAGState(TypedDict, total=False):
    """Shared state that flows through every node in the graph.

    total=False means all fields are optional — each node only sets
    the fields it owns.  This is the standard LangGraph pattern.
    """
    # Input
    question: str

    # Classify node outputs
    intent: str                    # "graph_only" | "vector_only" | "hybrid"
    detected_entities: list[str]

    # Graph retrieve node outputs
    cypher_query: str | None
    graph_records: list[dict]
    graph_context: str

    # Vector retrieve node outputs
    enriched_query: str
    vector_chunks: list[dict]
    vector_context: str

    # Assemble node output
    assembled_prompt: str

    # Synthesise node outputs
    answer: str
    metadata: dict


# ── Routing function ─────────────────────────────────────────────────────────

def route_after_classify(state: dict) -> str:
    """Conditional edge: decide which retrieval path to take."""
    intent = state.get("intent", "hybrid")
    if intent == "graph_only":
        return "graph_retrieve"
    elif intent == "vector_only":
        return "vector_retrieve"
    else:
        return "graph_retrieve"   # hybrid: graph first, then vector


def route_after_graph(state: dict) -> str:
    """Conditional edge: after graph retrieval, go to vector or assemble?"""
    intent = state.get("intent", "hybrid")
    if intent == "graph_only":
        return "assemble_context"  # Skip vector search
    else:
        return "vector_retrieve"   # hybrid: continue to vector search


# ── Agent builder ────────────────────────────────────────────────────────────

def build_agent(
    settings: Settings,
    neo4j_client: Neo4jClient,
    vector_service: VectorService,
) -> Any:
    """Build and compile the LangGraph RAG agent.

    Args:
        settings: Application config (contains API keys).
        neo4j_client: Connected Neo4j async client.
        vector_service: Connected Supabase vector search service.

    Returns:
        A compiled LangGraph runnable.  Call with:
            result = await agent.ainvoke({"question": "..."})
    """
    gemini_key = settings.gemini_api_key.get_secret_value()
    gemini_model = settings.gemini_model

    # ── Build node functions ─────────────────────────────────────────
    graph_service = GraphService(
        neo4j_client=neo4j_client,
        gemini_api_key=gemini_key,
        gemini_model=gemini_model,
    )

    classify_node = make_classify_node(gemini_key, gemini_model)
    graph_node = make_graph_retrieve_node(graph_service)
    vector_node = make_vector_retrieve_node(vector_service)
    synthesise_node = make_synthesise_node(gemini_key, gemini_model)

    # ── Define the StateGraph ────────────────────────────────────────
    workflow = StateGraph(RAGState)

    # Register nodes
    workflow.add_node("classify_intent", classify_node)
    workflow.add_node("graph_retrieve", graph_node)
    workflow.add_node("vector_retrieve", vector_node)
    workflow.add_node("assemble_context", assemble_context)
    workflow.add_node("synthesise", synthesise_node)

    # Entry point
    workflow.set_entry_point("classify_intent")

    # Edge: classify → (conditional) → graph_retrieve OR vector_retrieve
    workflow.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "graph_retrieve": "graph_retrieve",
            "vector_retrieve": "vector_retrieve",
        },
    )

    # Edge: graph_retrieve → (conditional) → assemble_context OR vector_retrieve
    workflow.add_conditional_edges(
        "graph_retrieve",
        route_after_graph,
        {
            "assemble_context": "assemble_context",
            "vector_retrieve": "vector_retrieve",
        },
    )

    # Edge: vector_retrieve → assemble_context (always)
    workflow.add_edge("vector_retrieve", "assemble_context")

    # Edge: assemble_context → synthesise (always)
    workflow.add_edge("assemble_context", "synthesise")

    # Edge: synthesise → END
    workflow.add_edge("synthesise", END)

    # ── Compile ──────────────────────────────────────────────────────
    agent = workflow.compile()

    logger.info("LangGraph RAG agent compiled successfully.")
    return agent
