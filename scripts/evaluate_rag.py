"""Evaluation script for the GraphRAG pipeline.

This script runs a set of test questions through TWO pipelines:
  1. Baseline (Vector RAG only)
  2. GraphRAG (LangGraph agent: Graph + Vector)

It outputs a JSON file with the side-by-side answers and metadata,
which can then be scored by an LLM judge.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from app.core.config import get_settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.services.langgraph_agent import build_agent
from app.services.nodes.assemble import assemble_context
from app.services.nodes.synthesise import make_synthesise_node
from app.services.vector_service import VectorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 15 test questions across 3 categories to evaluate GraphRAG vs Baseline
TEST_QUESTIONS = [
    # ── Category A: Entity/Relational (Graph should dominate) ────────
    {
        "id": "A1",
        "category": "Entity",
        "text": "What chemicals can I use to control Green Mirids?",
    },
    {
        "id": "A2",
        "category": "Entity",
        "text": "Which MoA group does Spirotetramat belong to?",
    },
    {
        "id": "A3",
        "category": "Entity",
        "text": "Which beneficial insects prey on Helicoverpa?",
    },
    {
        "id": "A4",
        "category": "Entity",
        "text": "What diseases affect cotton and what pathogens cause them?",
    },
    {
        "id": "A5",
        "category": "Entity",
        "text": "What exotic pests have an EXTREME biosecurity risk rating?",
    },
    # ── Category B: Prose/Semantic (Vector should dominate) ──────────
    {
        "id": "B1",
        "category": "Prose",
        "text": "What are the key recommendations for soil preparation before planting cotton?",
    },
    {
        "id": "B2",
        "category": "Prose",
        "text": "Describe best practices for cotton irrigation scheduling.",
    },
    {
        "id": "B3",
        "category": "Prose",
        "text": "What safety precautions should be taken when applying chemicals?",
    },
    {
        "id": "B4",
        "category": "Prose",
        "text": "Explain the process for hand-picking for pest monitoring in cotton.",
    },
    {
        "id": "B5",
        "category": "Prose",
        "text": "What are the recommended record-keeping practices for spray applications?",
    },
    # ── Category C: Hybrid (Both should contribute) ──────────────────
    {
        "id": "C1",
        "category": "Hybrid",
        "text": "What are the resistance management strategies for Silverleaf Whitefly?",
    },
    {
        "id": "C2",
        "category": "Hybrid",
        "text": "What are the approved chemicals for Helicoverpa and their recommended application timing?",
    },
    {
        "id": "C3",
        "category": "Hybrid",
        "text": "What are the spray thresholds for mirids and how do I sample for them?",
    },
    {
        "id": "C4",
        "category": "Hybrid",
        "text": "How should I manage Fusarium wilt and what varieties are resistant?",
    },
    {
        "id": "C5",
        "category": "Hybrid",
        "text": "What are the key defoliants used in cotton and their temperature requirements?",
    },
]


async def run_baseline_rag(question: str, vector_svc: VectorService, synthesise_node) -> dict:
    """Simulate the existing production pipeline: Vector Search -> Synthesis."""
    t0 = time.perf_counter()
    
    # 1. Vector Search
    chunks = await vector_svc.hybrid_search(question, top_k=6)
    
    # 2. Format Context
    vector_context = ""
    if chunks:
        lines = ["=== DOCUMENT CONTEXT ==="]
        for i, c in enumerate(chunks, 1):
            lines.append(f"Source {i}: {c.get('text', '')[:500]}...")
        vector_context = "\n".join(lines)
    
    # 3. Assemble (Graph is empty)
    state = {"question": question, "vector_context": vector_context, "graph_context": ""}
    state.update(await assemble_context(state))
    
    # 4. Synthesise
    result = await synthesise_node(state)
    
    elapsed = time.perf_counter() - t0
    return {
        "answer": result["answer"],
        "time_s": round(elapsed, 2),
        "vector_chunks": len(chunks)
    }


async def run_evaluation():
    load_dotenv()
    settings = get_settings()
    
    logger.info("Connecting to databases...")
    neo4j = Neo4jClient(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    await neo4j.connect()
    
    vector_svc = VectorService(
        pg_uri=settings.postgres_connection_string.get_secret_value(),
        openai_key=settings.openai_api_key.get_secret_value(),
    )
    await vector_svc.connect()
    
    # Build LangGraph agent
    agent = build_agent(settings, neo4j, vector_svc)
    
    # Build a standalone synthesise node for the baseline
    gemini_key = settings.gemini_api_key.get_secret_value()
    synthesise_node = make_synthesise_node(gemini_key, settings.gemini_model)
    
    results = []
    
    print("\n" + "="*80)
    print("🚀 STARTING GRAPHRAG EVALUATION")
    print("="*80 + "\n")
    
    for idx, q in enumerate(TEST_QUESTIONS, 1):
        print(f"[{idx}/{len(TEST_QUESTIONS)}] Category: {q['category']}")
        print(f"Question: {q['text']}")
        
        # 1. Run Baseline
        print("  -> Running Baseline RAG...")
        baseline = await run_baseline_rag(q["text"], vector_svc, synthesise_node)
        
        # 2. Run GraphRAG
        print("  -> Running LangGraph Agent...")
        try:
            graphrag = await agent.ainvoke({"question": q["text"]})
        except Exception as e:
            logger.error(f"GraphRAG failed: {e}")
            graphrag = {"answer": f"ERROR: {e}", "metadata": {}}
        
        print(f"  ✓ Done. Baseline: {baseline['time_s']}s | GraphRAG: {graphrag.get('metadata', {}).get('synthesis_time_s', 0)}s\n")
        
        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["text"],
            "baseline": {
                "answer": baseline["answer"],
                "time_s": baseline["time_s"],
                "chunks_used": baseline["vector_chunks"]
            },
            "graphrag": {
                "answer": graphrag["answer"],
                "intent": graphrag.get("intent"),
                "time_s": graphrag.get("metadata", {}).get("synthesis_time_s"),
                "graph_records_used": len(graphrag.get("graph_records", [])),
                "cypher_query": graphrag.get("cypher_query")
            }
        })
    
    await vector_svc.close()
    await neo4j.close()
    
    # Save results
    os.makedirs("scripts/eval_results", exist_ok=True)
    out_file = "scripts/eval_results/rag_comparison.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print("="*80)
    print(f"✅ Evaluation complete. Results saved to {out_file}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
