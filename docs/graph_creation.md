# Document-to-Graph Extraction Tools & Approaches

## 1. Overview

This document surveys tools and frameworks used to convert **unstructured documents (e.g., PDFs, text, reports)** into structured graph representations (nodes + relationships).

The goal is **not to select a single solution**, but to:
- Understand the landscape
- Compare approaches
- Highlight trade-offs
- Identify where each tool fits in a pipeline

---

## 2. The General Problem

Transforming documents into graphs typically involves:

1. Parsing documents (text, tables, structure)
2. Extracting entities (nodes)
3. Extracting relationships (edges)
4. Normalising and deduplicating entities
5. Loading into a graph database

Modern systems increasingly rely on **LLMs to automate steps 2–3**, replacing traditional NLP pipelines.

Reference:
- https://neo4j.com/blog/developer/unstructured-text-to-knowledge-graph/

---

## 3. Categories of Tools

Rather than a single type of tool, the ecosystem splits into **three major categories**:

### 3.1 End-to-End Graph Extraction Platforms
- Full pipeline: document → graph
- Often include UI, ingestion, and storage integrations

### 3.2 LLM Frameworks / Libraries
- Provide building blocks for custom pipelines
- Focus on extraction logic rather than infrastructure

### 3.3 Document Parsing & Preprocessing Tools
- Focus on extracting structured content from complex documents
- Feed downstream extraction systems

---

## 4. Tooling Landscape

### 4.1 Neo4j LLM Knowledge Graph Builder

#### Description
A tool designed to convert unstructured text into knowledge graphs using LLMs, tightly integrated with Neo4j and GraphRAG workflows.

Reference:
- https://neo4j.com/labs/genai-ecosystem/llm-graph-builder/

#### Key Features
- Text → nodes + relationships extraction
- Schema-aware graph generation
- Direct integration with Neo4j databases
- Built-in visualisation

#### Strengths
- Very fast to prototype
- Strong ecosystem alignment (GraphRAG)
- Minimal setup required

#### Limitations
- Tied to Neo4j ecosystem
- Less flexible for custom pipelines

---

### 4.2 LangChain Graph Transformer

#### Description
A module within LangChain for transforming text into graph structures using LLMs.

Reference:
- https://python.langchain.com/docs/use_cases/graph/graph_transformers/

#### Key Features
- Two modes:
  - Tool-based (structured extraction)
  - Prompt-based (few-shot extraction)
- Supports property extraction

#### Strengths
- Highly flexible
- Easily integrates into agent pipelines
- Good for experimentation

#### Limitations
- Requires more engineering effort
- Output quality depends heavily on prompt/tool design

---

### 4.3 LlamaParse + LlamaIndex

#### Description
A document parsing and ingestion system designed to handle complex documents (PDFs, tables, figures) before downstream processing.

References:
- https://www.llamaindex.ai/llamaparse
- https://neo4j.com/blog/developer/llamaparse-knowledge-graph-documents/

#### Key Features
- Extracts structured content from complex documents
- Handles tables, layouts, and embedded objects
- Integrates into ingestion pipelines

#### Strengths
- Excellent preprocessing quality
- Handles real-world messy documents
- Improves downstream extraction accuracy

#### Limitations
- Not a graph extractor itself
- Requires pairing with an LLM extraction layer

---

### 4.4 ContextClue Graph Builder

#### Description
An open-source toolkit for building knowledge graphs from semi-structured and unstructured data.

Reference:
- https://github.com/Addepto/graph_builder

#### Key Features
- Document → graph pipeline
- Supports multiple data formats
- Designed for analytics and search

#### Strengths
- Open-source and extensible
- Suitable for experimentation

#### Limitations
- Less mature ecosystem
- Requires setup and customisation

---

### 4.5 Docling

#### Description
A document parsing tool designed to convert complex files into structured representations for downstream processing.

Reference:
- https://github.com/DS4SD/docling

#### Key Features
- Parses diverse formats
- Produces structured outputs
- Simplifies downstream extraction

#### Strengths
- Strong preprocessing layer
- Useful for heterogeneous document sets

#### Limitations
- Not a full graph solution
- Needs integration with LLM extraction

---

### 4.6 LLM-Driven Custom Pipelines

#### Description
Custom pipelines built using:
- LLM APIs (OpenAI-compatible or open-source)
- Prompt engineering or tool-calling
- Multi-step workflows (entity → relationship → validation)

#### Key Features
- Fully customisable
- Supports ontology-driven extraction
- Enables multi-pass workflows

#### Strengths
- Maximum flexibility
- High potential accuracy
- Adaptable to domain-specific data

#### Limitations
- Engineering complexity
- Requires evaluation frameworks
- Risk of hallucination and inconsistency

---

## 5. Emerging Patterns in Tooling

### 5.1 LLM-Augmented Extraction
- LLMs extract entities and relationships directly from text
- Reduces reliance on manual NLP pipelines

---

### 5.2 Multi-Pass Pipelines
Common structure:
1. Node extraction
2. Relationship extraction
3. Entity resolution

This improves graph quality and consistency.

---

### 5.3 Hybrid Systems (Graph + Vector + LLM)

Modern systems combine:
- Vector search (semantic retrieval)
- Graph traversal (relationships)
- LLM reasoning

Reference:
- https://atlan.com/know/combining-knowledge-graphs-llms/

---

### 5.4 Document Complexity Handling

Tools increasingly focus on:
- Tables
- Figures
- Layout-aware parsing

Because poor parsing → poor graph quality.

---

## 6. Comparison Summary

| Category | Example Tools | Strengths | Weaknesses | Best Use Case |
|----------|-------------|----------|------------|--------------|
| End-to-End Platforms | Neo4j LLM Graph Builder | Fast setup, integrated | Less flexible | Prototyping |
| LLM Frameworks | LangChain Graph Transformer | Flexible | More engineering | Custom pipelines |
| Parsing Tools | LlamaParse, Docling | High-quality extraction | Not graph-aware | Preprocessing |
| Open-source Toolkits | ContextClue | Extensible | Less mature | Research |
| Custom Pipelines | LLM APIs | Maximum control | Complex | Production systems |

---

## 7. Key Trade-offs

### Flexibility vs Simplicity
- End-to-end tools → easy but rigid
- Custom pipelines → powerful but complex

### Accuracy vs Automation
- Fully automated extraction → faster, noisier
- Guided extraction → cleaner graphs

### Speed vs Control
- Prebuilt tools → rapid development
- Custom workflows → tunable but slower

---

## 8. Challenges Across All Tools

- Entity duplication
- Relationship ambiguity
- Hallucinated edges
- Context loss in long documents
- Difficult evaluation

---

## 9. Observations

- No single tool solves the entire problem well
- Most systems benefit from **combining multiple tools**
- Trend is toward:
  - LLM-driven extraction
  - Hybrid architectures
  - GraphRAG systems

---

## 10. Conclusion

The ecosystem for document-to-graph extraction is **fragmented but rapidly evolving**.

Most real-world systems will require a **composed pipeline**, combining:
- Parsing tools
- LLM extraction
- Graph storage systems

---