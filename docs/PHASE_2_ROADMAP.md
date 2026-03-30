# CRDC Knowledge Hub: Phase 2 Strategic Roadmap

## Vision
The CRDC Knowledge Hub is evolving from a standard RAG system into an advanced **Ontology-Grounded GraphRAG system**. While standard RAG excels at retrieving text, it struggles with industry-specific terminology, acronyms (e.g., "RD&E", "CRDC"), and evaluating researcher credibility (H-Index/ARC rankings), often losing critical context across page boundaries. 

Our vision for Phase 2 is to bridge these gaps by introducing a relational understanding layer. By identifying and mapping the critical entities of the cotton industry, we will deliver highly accurate, contextual, and authoritative answers to complex user queries.

## Technical Stack
Building a robust GraphRAG system requires a modernized, hybrid architecture designed for speed, scale, and accuracy:
- **FastAPI (Service Layer):** A high-performance, asynchronous backend framework that handles query orchestration and API routing.
- **Neo4j Aura (Relationship Engine):** A managed graph database dedicated to mapping our targeted industry ontology and structural relationships.
- **Supabase / pgvector (Vector Store):** Maintains the repository of thousands of raw text chunks, utilizing vector embeddings for semantic, similarity-based search.
- **LangChain (Orchestrator):** Acts as the cognitive orchestrator, connecting the language models to our graph and vector data stores to synthesize final responses.

## The "Lazy Graph" Strategy
Instead of attempting to construct a massive, computationally expensive graph of every sentence within the corpus, we are adopting a **"Lazy Graph" strategy**. 

This targeted approach focuses exclusively on mapping the foundational "nouns" of the cotton industry:
- **Pests & Diseases**
- **Chemicals & Treatments**
- **Acronyms & Terminology**
- **Researchers & Institutions (with credibility metrics)**

**How it works:** When a user asks a question, the system first consults the targeted Neo4j graph to understand the terms, identify relationships, and pinpoint experts. It then uses these "anchors" to retrieve the perfect, highly relevant text chunks from Supabase, ensuring precision without the overhead of maintaining an exhaustive full-document graph.

## Infrastructure Plan
To ensure our setup remains maintainable, scalable, and testing-friendly, the new `crdc-graphrag` repository is built upon a modular **Service-Adapter pattern**. 
This separation of concerns allows us to isolate our core business logic (Services) from external integrations (Adapters for Neo4j, Supabase, LLMs). Such modularity guarantees that as our data requirements and underlying AI models evolve, the core system remains decoupled and resilient to change.

## Data Foundation
To build our initial ontology and seed the Knowledge Graph, we are prioritizing the "rules of the industry." Our **Gold Standard** sources for initial knowledge extraction include:
1. **2025 Australian Cotton Production Manual (ACPM)** (Alongside 2024 and 2023 versions)
2. **2025-26 Cotton Pest Management Guide (CPMG)** (Alongside 2024-25 versions)

These documents serve as our primary pillars for extracting entities, establishing chemical and pest relationships, and defining industry terminology. This foundational dataset will be supplemented by the "PAK" series (NUTRIpak, FIBREpak, WATERpak, WEEDpak, SPRAYpak, SOILpak), specialized guides, and researcher profile case studies to establish H-Index and expertise links.

---

## Next Sprint: Core Objectives Checklist

- [ ] **Infrastructure Setup:** Provision Neo4j Aura instance and integrate connections within the `crdc-graphrag` repository.
- [ ] **Service-Adapter Implementation:** Finalize the base Adapter classes for Neo4j and Supabase, and implement the core Query Service.
- [ ] **Targeted Scraping Script:** Develop a lightweight Python script using `requests` and `BeautifulSoup` to scrape the core manuals and guides based on `<a>` tags containing "Manual" or "Guide".
- [ ] **Entity Extraction Pipeline (V1):** Write a LangChain extraction chain to pull core entities (Pests, Chemicals, Acronyms, Researchers) from the Gold Standard documents.
- [ ] **Graph Seeding:** Populate the Neo4j Aura database with the extracted entities and their immediate structural relationships.
- [ ] **Query Orchestration Prototype:** Build an end-to-end test query that queries the Graph for "anchors" and then pulls corresponding text chunks from Supabase.
