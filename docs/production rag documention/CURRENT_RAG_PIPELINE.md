# Current Runtime RAG Architecture

This document shows the current end-to-end runtime architecture for the Knowledge Hub:
- how traffic moves through Cloudflare, Cloud Run, and Supabase
- where LLM calls happen
- how conversational, simple, and complex questions take different paths

This intentionally excludes ingestion details.

## 1. Deployment Topology

```mermaid
flowchart LR
    U["User Browser"]

    subgraph CF["Cloudflare"]
        FE["Next.js app on OpenNext/Cloudflare Worker"]
        PROXY["/api/* proxy route"]
    end

    subgraph GCP["Google Cloud Run"]
        API["FastAPI backend"]
        RAG["RAG pipeline"]
    end

    subgraph SB["Supabase"]
        AUTH["Supabase Auth"]
        PG["Postgres + pgvector"]
        STORE["Storage"]
    end

    subgraph AI["Model Providers"]
        OAI["OpenAI"]
    end

    U --> FE
    FE --> AUTH
    FE --> PROXY
    PROXY --> API
    API --> RAG
    API --> AUTH
    API --> PG
    API --> STORE
    RAG --> OAI
```

## 2. What Runs Where

| Layer | Current role |
| --- | --- |
| Cloudflare | Hosts the Next.js frontend via OpenNext and runs the `/api/*` proxy route |
| Cloud Run | Runs the FastAPI backend and all RAG orchestration |
| Supabase Auth | Handles login/session issuance |
| Supabase Postgres | Stores documents, chunks, chat history, metadata, and vector embeddings |
| Supabase Storage | Serves PDFs and related stored assets through backend-controlled routes |
| OpenAI | Embeddings, reranking, query rewriting, conversational responses, and final answer generation |

## 3. Important Current-State Notes

1. The frontend is clearly wired for Cloudflare.
   Evidence in repo:
   - `frontend/wrangler.jsonc`
   - `frontend/open-next.config.ts`
   - `frontend/package.json` Cloudflare deploy scripts

2. The backend is clearly wired for Cloud Run.
   Evidence in repo:
   - `deploy/manual_deploy_api.sh`
   - `deploy/deploy_public.yaml`
   - `deploy/Dockerfile.api`

3. Browser auth is direct to Supabase, but application data calls are proxied through the frontend.
   - Browser gets a Supabase session token
   - frontend sends `Authorization: Bearer ...`
   - backend verifies the bearer token with Supabase admin credentials

4. The repo contains both Cloudflare frontend config and an older containerized web build path.
   - The Cloudflare/OpenNext path looks like the intended frontend runtime
   - the Docker-based web build still exists in the repo as an alternate or older deployment path

5. The implemented LLM runtime is effectively OpenAI today.
   - `configs/runtime/gemini.yaml` exists
   - but `app/factory.py` currently instantiates `OpenAIAdapter` directly for the LLM path
   - so Gemini is not fully wired as a live generation backend in the current code path

## 4. End-to-End Request Flow

```mermaid
sequenceDiagram
    participant User as Browser
    participant CF as Cloudflare Next/OpenNext
    participant SBAuth as Supabase Auth
    participant API as Cloud Run FastAPI
    participant DB as Supabase Postgres
    participant Storage as Supabase Storage
    participant OAI as OpenAI

    User->>SBAuth: Sign in / restore session
    SBAuth-->>User: Access token

    User->>CF: Open app / ask question
    CF->>API: Proxy /api/ask with Bearer token + API key
    API->>SBAuth: Verify bearer token
    SBAuth-->>API: Authenticated user

    API->>DB: Load chat history / session context
    API->>API: Classify route

    alt Conversational
        API->>OAI: Direct chat response
        OAI-->>API: Tokens / answer
    else Simple knowledge query
        API->>OAI: Optional query analysis / rephrase
        API->>OAI: Query embedding
        API->>DB: Hybrid retrieval
        DB-->>API: Candidate chunks
        API->>OAI: Rerank candidates
        API->>OAI: Final answer generation
        OAI-->>API: Answer
    else Complex knowledge query
        API->>OAI: Query embedding
        API->>DB: Hybrid retrieval
        DB-->>API: Candidate chunks
        API->>OAI: Rerank candidates
        API->>OAI: Parallel map summaries per document
        API->>OAI: Reduce synthesis
        OAI-->>API: Final synthesized answer
    end

    API->>Storage: Resolve PDF links for citations when needed
    API-->>CF: Answer + citations + timings
    CF-->>User: Render chat response and PDF deep links
```

## 5. Where LLMs Are Used

This is the key runtime view.

| Stage | Used in which path | Model/provider role |
| --- | --- | --- |
| Conversational reply | Conversational only | Direct LLM answer, no retrieval |
| Query analyzer | Some multi-turn knowledge queries | Small routing/extraction model call |
| Query rephrase | Knowledge queries with chat history | Rewrite follow-up into standalone retrieval query |
| Query embedding | Simple and complex knowledge queries | OpenAI embedding for retrieval |
| Reranking | Simple and complex knowledge queries | OpenAI embeddings scored against candidate chunks |
| Final answer generation | Simple knowledge queries | Main answer synthesis |
| Map step | Complex knowledge queries | One LLM call per selected document |
| Reduce step | Complex knowledge queries | Final cross-document synthesis |

## 6. Runtime Paths

### A. Conversational path

Used for:
- greetings
- thanks
- chat-meta questions
- requests like "what did I ask before?"
- simple clarification turns that do not require retrieval

Flow:
- `/api/ask`
- detect conversational intent
- skip retrieval
- call LLM directly
- return answer without citations

```mermaid
flowchart LR
    A["User message"] --> B["Intent detection"]
    B --> C["Conversational fast-path"]
    C --> D["OpenAI chat response"]
    D --> E["Answer without retrieval or citations"]
```

### B. Simple knowledge path

Used for:
- normal factual document-backed questions
- single-topic queries
- most standard RAG requests

Flow:
- authenticate user
- load chat history
- classify as non-conversational
- classify as simple
- optional query analysis
- optional query rewrite
- embed query
- run hybrid retrieval in Postgres
- prepare and diversify hits
- rerank
- build prompt with citations
- generate final answer

```mermaid
flowchart LR
    A["Question"] --> B["Simple classifier result"]
    B --> C["Optional analyzer + rephrase"]
    C --> D["OpenAI query embedding"]
    D --> E["Supabase Postgres hybrid search"]
    E --> F["Hit prep + neighbor stitching"]
    F --> G["OpenAI rerank"]
    G --> H["Prompt assembly"]
    H --> I["OpenAI final answer"]
```

### C. Complex knowledge path

Used for:
- compare/synthesize/across-many-documents questions
- trends, gaps, overlap, ranking, multi-report summaries

Flow:
- authenticate user
- classify as complex
- run retrieval-only prep chain first
- convert citations into chunk payloads
- group chunks by document
- run parallel map LLM calls
- run one reduce synthesis call
- return synthesized answer with citations

```mermaid
flowchart LR
    A["Question"] --> B["Complex classifier result"]
    B --> C["Retrieval-only prep chain"]
    C --> D["Hybrid retrieval from Postgres"]
    D --> E["OpenAI rerank"]
    E --> F["Group retrieved chunks by document"]
    F --> G["Parallel map LLM calls"]
    G --> H["Reduce LLM call"]
    H --> I["Final synthesized answer"]
```

## 7. Retrieval Architecture

The active knowledge path is hybrid retrieval over Supabase Postgres.

Current runtime flow:
1. query embedding is generated with OpenAI
2. backend runs parallel vector and keyword search
3. backend fuses results with Reciprocal Rank Fusion
4. backend applies hit preparation, preview construction, neighbor stitching, and per-doc diversification
5. backend reranks with OpenAI embeddings
6. top sources go into prompt assembly

```mermaid
flowchart TD
    A["Query text"] --> B["OpenAI embedding"]
    B --> C["Vector search in pgvector"]
    A --> D["Keyword search in Postgres tsvector"]
    C --> E["RRF fusion in backend"]
    D --> E
    E --> F["Deep-content and freshness score shaping"]
    F --> G["Prepare hits"]
    G --> H["Neighbor stitching and diversification"]
    H --> I["OpenAI rerank"]
    I --> J["Final source pack"]
```

## 8. Auth and Data Flow

The auth/data split matters because the browser does not talk directly to the application database.

### Auth flow

```mermaid
flowchart LR
    U["Browser"] --> SA["Supabase Auth"]
    SA --> U
    U --> CF["Cloudflare frontend"]
    CF --> API["Cloud Run backend"]
    API --> SA
```

Meaning:
- login/session is managed with Supabase in the frontend
- the frontend attaches the bearer token to API calls
- the backend validates the bearer token using Supabase admin access

### Data flow

```mermaid
flowchart LR
    API["Cloud Run backend"] --> PG["Supabase Postgres"]
    API --> ST["Supabase Storage"]
```

Backend responsibilities:
- query `documents`, `chunks`, and chat/session tables in Postgres
- resolve internal PDF URLs and signed/storage-backed document access
- return citations with PDF deep-link metadata

## 9. Streaming Behavior

Streaming is split into phases so the UI can show citations early.

Simple streaming:
1. retrieve sources
2. emit `sources`
3. stream answer tokens

Complex streaming:
1. retrieve sources
2. emit `sources`
3. emit map-reduce status messages
4. stream reduce output

## 10. Current Component Responsibility Map

| Concern | Main file |
| --- | --- |
| Cloudflare API proxy | `frontend/src/app/api/[...path]/route.ts` |
| Backend origin wiring | `frontend/src/lib/server-api.ts` |
| Frontend auth token attachment | `frontend/src/lib/auth-client.ts` |
| Supabase browser auth client | `frontend/src/lib/supabase/client.ts` |
| Bearer verification in backend | `app/api/deps.py` |
| Main ask endpoint | `app/api/routers/ask.py` |
| Pipeline assembly | `app/factory.py` |
| Retrieval/prompt chain | `rag/chain.py` |
| Complexity routing | `rag/routing/classifier.py` |
| Postgres hybrid retrieval | `app/infrastructure/adapters/vector_postgres.py` |
| Reranker | `app/infrastructure/adapters/rerank_openai.py` |
| Complex map-reduce | `rag/synthesis/map_reduce.py` |

## 11. Bottom Line

The current runtime architecture is:
- Cloudflare-hosted Next.js frontend
- frontend proxying `/api/*` to a Cloud Run FastAPI backend
- Supabase handling auth, Postgres, and storage
- OpenAI handling every implemented LLM/embedding/rerank step in the active code path

The three runtime behaviors are:
- conversational: direct LLM, no retrieval
- simple: standard hybrid RAG + rerank + single final generation
- complex: hybrid RAG + rerank + map-reduce synthesis
