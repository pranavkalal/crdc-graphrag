"""LangGraph node functions for the GraphRAG agent pipeline.

Each module in this package implements a single node in the LangGraph
StateGraph.  Nodes are pure functions that accept the shared RAGState
dict, perform one step of the pipeline, and return a partial state
update.

Modules:
  classify      — Intent classification + entity extraction
  graph_retrieve — Neo4j Cypher generation + execution
  vector_retrieve — Supabase hybrid search
  assemble      — Context merger + prompt builder
  synthesise    — Final Gemini answer synthesis
"""
