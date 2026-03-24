# The GraphRAG Core: Architectural Vision and Repository Strategy

Kevin, Yi Jie, Connor:

As we move GraphRAG development into `crdc-graphrag`, the intent is explicit. This repository is not a side project, a staging area, or a short-lived experiment. It is the long-term engineering home for the CRDC Knowledge Hub graph engine: the place where we define the cotton industry knowledge model, operationalize graph extraction, and build the retrieval layer that will carry Phase 2 and everything that follows.

## Why We Are Separating This

The main repository remains the production API and delivery layer. Its job is to serve users reliably, move data through stable application paths, and stay optimized for deployment, integration, and product delivery.

This repository has a different mandate. `crdc-graphrag` is where we build the graph-native engine that the production layer will depend on. That engine introduces a materially different stack and a materially different development cadence:

- Neo4j and Cypher as first-class infrastructure
- A domain-specific ontology for cotton terminology, acronyms, documents, and metadata
- Extraction workflows that are heavier, more iterative, and more experimental than standard API work
- RAG evaluation patterns that depend on graph structure, schema evolution, and relationship quality

Keeping that work inside the main repository would blur concerns that should stay cleanly separated. It would mix graph extraction logic with production delivery logic, expand the deployment surface with infrastructure that the main app does not need to own directly, and make the core API pipeline absorb complexity that belongs in the knowledge engine itself.

This split is architectural discipline, not repo preference.

## Not a Pilot, but a Foundation

We should think about this repository as core infrastructure.

This is where we will:

- Define and evolve the industry ontology
- Manage Neo4j schema conventions and graph modeling decisions
- Establish extraction and normalization patterns for terms, acronyms, entities, and metadata
- Run retrieval and reasoning experiments that test graph-augmented RAG strategies
- Build the interfaces that the main CRDC application can call as a stable graph service

In practical terms, the main repository is the delivery surface. This repository is the graph brain behind it.

That distinction matters because it changes how we evaluate decisions. In the main repository, we optimize for product reliability, API clarity, and operational simplicity. In this repository, we optimize for knowledge depth, semantic precision, ontology quality, and the ability to answer questions that depend on relationships rather than proximity in embedding space.

## The "Lazy" Methodology: Ontology-Grounded GraphRAG

The methodology here is intentionally not "chunk, embed, and hope."

We are building an ontology-grounded system. That means the goal is not merely to index text passages, but to construct a structured terminology and metadata map of the cotton industry. The graph is the durable semantic layer; embeddings are supporting machinery, not the system definition.

This matters because our problem space contains exactly the patterns that standard vector RAG handles poorly:

- Acronyms whose meaning depends on domain context
- Terms that appear in multiple manuals with slightly different definitions
- Relationships between documents, authors, and technical concepts
- Cross-document terminology alignment that requires normalization, not just similarity search

The "lazy" part is not about cutting corners. It is about being deliberate in where we introduce structure. We do not need to model the entire world upfront. We do need to model the industry concepts that materially improve retrieval, grounding, and explanation quality. That means building the ontology incrementally, but building it as real infrastructure from day one.

## Modular Workflow: Service-Adapter Pattern

This repository follows a Service-Adapter pattern so the graph engine stays composable as it grows.

The separation is straightforward:

- Infrastructure adapters own external systems such as Neo4j and OpenAI
- Services own business logic such as graph traversal, extraction orchestration, and retrieval strategy
- API routes remain thin orchestration layers over the service layer
- Models define the ontology and schema contract that keep the system coherent

This structure gives us a few important engineering advantages:

- We can evolve database access independently from graph logic
- We can swap or expand model providers without rewriting business workflows
- We can test traversal and extraction logic without dragging infrastructure concerns into every unit
- We can keep the graph schema explicit instead of letting it dissolve into ad hoc prompt code

In other words, the architecture is designed to protect the knowledge layer from becoming an unstructured collection of scripts.

## Our Objective

The objective is clear: solve the acronym problem and the relationship problem that standard vector RAG does not solve well enough.

Vector retrieval is strong at finding semantically similar passages quickly. It is weaker when a correct answer depends on explicit structure:

- What does this acronym mean in this subdomain?
- Which document defines this term most authoritatively?
- How is this concept related to a broader process, author, or publication source?
- Which entities co-occur consistently across technical documents, and which ones are only superficially similar?

GraphRAG gives us a way to answer those questions with traceable structure rather than approximate textual proximity alone. That is the gap this repository exists to close.

## Why Not Keep It in One Repo?

If someone asks why this work is not staying in the main repository, this is the short answer:

| Feature | Main Repo (Vector RAG) | This Repo (GraphRAG Core) |
| --- | --- | --- |
| Database | Supabase (Postgres/Vector) | Neo4j (Graph/Cypher) |
| Primary Goal | High-speed document retrieval | Relationship & Acronym mapping |
| Complexity | Deployment & Frontend | Extraction, Ontology & Logic |
| Scaling | Horizontal (more users) | Vertical (deeper knowledge) |

These are complementary systems, not competing ones. The main repository is optimized to serve. This repository is optimized to understand.

## Strategic Outcome

If we execute this well, `crdc-graphrag` becomes the durable semantic core of the CRDC Knowledge Hub:

- The ontology becomes a reusable asset, not a one-off artifact
- The graph schema becomes a stable contract for future retrieval systems
- Extraction quality compounds over time instead of resetting with each experiment
- The production application gains a stronger reasoning layer without inheriting graph-engine complexity

That is the architectural vision. We are not building a detached experiment. We are building the core knowledge infrastructure that makes the rest of the platform smarter, more defensible, and more capable over time.
