# CRDC GraphRAG

Initial scaffold for a GraphRAG system that combines FastAPI, Neo4j, and LangChain/OpenAI adapters around an ontology of cotton-industry terms, acronyms, documents, and authors.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Copy the example environment file and fill in your local credentials:

```bash
cp .env.example .env
```

1. Run the API:

```bash
uvicorn app.main:app --reload
```

1. Check the service health:

```bash
curl http://127.0.0.1:8000/health
```

## Project Layout

- `app/`: FastAPI app, ontology models, services, and infrastructure adapters
- `docs/architecture/`: architecture notes and diagrams
- `docs/research/`: methodology and research notes
- `scripts/`: standalone scripts for pilot workflows
- `data/raw/`: local raw PDFs for pilot ingestion
- `tests/`: pytest suite
