
## 1. Executive Summary

**GraphRAG is not one pattern, it is a family of patterns.** The right choice depends on the type of questions the system must answer.

A standard vector RAG stack is often enough for local, passage-level lookup. It becomes weaker when the system needs:

- cross-document entity linking,
- filtering, counting, sorting, and aggregation,
- multi-hop reasoning across entities and relations,
- explainability and provenance,
- corpus-level summarisation, or "what are the main themes?" style questions.

That is exactly where knowledge graphs help. Knowledge graphs are especially useful because they unify structured and unstructured data, support precise queries, and enable richer retrieval than chunk-only vector search.

The recommended position for this project:

- **GraphRAG / graph-first architecture is the primary focus.**
- **Neo4j is the recommended primary database** if the target system is genuinely graph-aware, not just vector-aware.
- **Langchain is the recommended initial environment**, with AI-SDK and Mastra being solid fully-typed LLM/Agent friendy alternative development tools, Langraph(Langcahin orchestration layer), Mastra(AI-SDK orchestration layer).
- **Workflow comes before provider and model comparison.** for solutions that rely on private data or data that is not considered withing a model training data, selecting SOTA models may not bring any substantial benefits, any model capable of interpreting the inyected context and user question, works good enough 

---

## 2. Why Standard RAG Is Not Enough

LLMs are strong generators but have hard limits around stale knowledge, hallucinations, and missing private data. RAG helps by retrieving external context at run time instead of relying only on model memory.

However, chunk-only retrieval has structural weaknesses:

- it retrieves semantically similar passages but often misses exact relationships,
- it struggles with aggregation queries,
- it struggles with entity disambiguation,
- it often loses document boundaries and source coherence,
- it is weak on dataset-wide or global questions.

**Practical implication:** if product requirements include questions like the following, vector-only RAG is usually not enough:

- "Which supplier contracts expiring in the next 90 days mention indemnity caps above $1M?"
- "Which incidents involve the same customer, product, and region as the latest escalation?"
- "Summarise the main tensions and themes across all board minutes this quarter."

The first two require structured graph reasoning. The third is where GraphRAG-style summarisation hierarchies become valuable.

---

## 3. What Knowledge Graphs Add to RAG

A knowledge graph improves RAG in five important ways:

**A. Entity grounding** — Entity mentions in text can be linked to canonical nodes. This reduces duplication and improves retrieval consistency.

**B. Multi-hop retrieval** — Graphs make it natural to traverse from one entity to related entities, events, documents, claims, or chunks.

**C. Precise filtering and aggregation** — Graphs can answer questions that require counts, joins, constraints, and path-aware filtering. Text alone cannot reliably answer these efficiently.

**D. Explainability** — A graph traversal or a set of linked nodes and relationships is easier to inspect than a purely latent vector match.

> Graphs do not replace vectors. They complement them. The best systems typically use combinations of: vector similarity, keyword or full-text retrieval, graph traversal, structured query generation, and reranking or agentic routing.
