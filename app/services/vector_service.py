"""Lightweight read-only bridge to the production Supabase pgvector store.

This service replicates the core hybrid search pipeline (vector + keyword + RRF)
from the production Knowledge Hub without importing any code from that repo.

Design notes:
  - Read-only: no writes, no mutations to the production database.
  - Self-contained: all search logic lives here; nothing is shared with
    the production codebase.
  - Cleanly removable: delete this file + the two config fields and the
    rest of the graph repo continues to work unchanged.

Requires two env vars to be set (see app/core/config.py):
  POSTGRES_CONNECTION_STRING  — read-only Supabase Postgres URI
  OPENAI_API_KEY              — for embedding generation
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
RRF_K = 60            # Reciprocal Rank Fusion smoothing constant
DEFAULT_TOP_K = 6     # Final results returned to the caller
OVERFETCH_FACTOR = 4  # How many candidates to pull before RRF merge


class VectorService:
    """Async hybrid search (vector + keyword + RRF) over the production
    Supabase Postgres chunks table.

    Usage:
        svc = VectorService(pg_uri="postgresql+asyncpg://...", openai_key="sk-...")
        await svc.connect()
        results = await svc.hybrid_search("control Green Mirids", top_k=6)
        await svc.close()
    """

    def __init__(self, pg_uri: str, openai_key: str) -> None:
        # Convert postgres:// to postgresql+asyncpg:// for SQLAlchemy async
        uri = pg_uri.replace("postgresql://", "postgresql+asyncpg://", 1)
        uri = uri.replace("postgres://", "postgresql+asyncpg://", 1)
        self._engine = create_async_engine(uri, pool_size=3, max_overflow=2)
        self._openai = AsyncOpenAI(api_key=openai_key)
        self._embedding_cache: dict[str, list[float]] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Verify the database is reachable (optional warm-up)."""
        async with self._engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("VectorService: Supabase Postgres connection verified.")

    async def close(self) -> None:
        """Dispose of the connection pool."""
        await self._engine.dispose()
        logger.info("VectorService: connection pool disposed.")

    # ── Embedding ────────────────────────────────────────────────────────

    async def _embed(self, query: str) -> list[float]:
        """Generate an embedding, with in-memory caching."""
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        resp = await self._openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
        )
        vec = resp.data[0].embedding
        self._embedding_cache[cache_key] = vec
        return vec

    # ── Vector search ────────────────────────────────────────────────────

    async def _vector_search(
        self, session: AsyncSession, embedding: list[float], limit: int
    ) -> list[dict[str, Any]]:
        """Cosine-similarity search over pgvector embeddings."""
        stmt = text("""
            SELECT id, doc_id, chunk_index, page_number, text,
                   metadata,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :lim
        """)
        result = await session.execute(
            stmt, {"embedding": str(embedding), "lim": limit}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    # ── Keyword search ───────────────────────────────────────────────────

    async def _keyword_search(
        self, session: AsyncSession, query: str, limit: int
    ) -> list[dict[str, Any]]:
        """Full-text search using Postgres tsvector + ts_rank_cd."""
        stmt = text("""
            SELECT id, doc_id, chunk_index, page_number, text,
                   metadata,
                   ts_rank_cd(search_vector, plainto_tsquery('english', :q)) AS score
            FROM chunks
            WHERE search_vector @@ plainto_tsquery('english', :q)
            ORDER BY score DESC
            LIMIT :lim
        """)
        result = await session.execute(stmt, {"q": query, "lim": limit})
        return [dict(row._mapping) for row in result.fetchall()]

    # ── RRF Fusion ───────────────────────────────────────────────────────

    @staticmethod
    def _rrf_merge(
        vector_hits: list[dict], keyword_hits: list[dict], k: int = RRF_K
    ) -> list[dict]:
        """Reciprocal Rank Fusion: combine two ranked lists into one.

        Formula per document: RRF(d) = Σ 1/(k + rank(d))
        """
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for rank, hit in enumerate(vector_hits, start=1):
            hid = str(hit["id"])
            scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank)
            docs[hid] = hit

        for rank, hit in enumerate(keyword_hits, start=1):
            hid = str(hit["id"])
            scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank)
            if hid not in docs:
                docs[hid] = hit

        # Sort by fused score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for hid, score in ranked:
            doc = docs[hid].copy()
            doc["rrf_score"] = score
            results.append(doc)

        return results

    # ── Deep content bias ────────────────────────────────────────────────

    @staticmethod
    def _apply_deep_bias(hits: list[dict]) -> list[dict]:
        """Penalise front-matter pages (title, TOC, abstract).

        Pages 1-2 get a 30% penalty, pages 3-4 get 15%.
        """
        for hit in hits:
            page = hit.get("page_number") or 999
            if page <= 2:
                hit["rrf_score"] *= 0.7
            elif page <= 4:
                hit["rrf_score"] *= 0.85
        # Re-sort after bias
        hits.sort(key=lambda h: h["rrf_score"], reverse=True)
        return hits

    # ── Public API ───────────────────────────────────────────────────────

    async def hybrid_search(
        self, query: str, top_k: int = DEFAULT_TOP_K
    ) -> list[dict[str, Any]]:
        """Run full hybrid search: embed → parallel search → RRF → bias → top-k.

        Returns a list of dicts with keys: id, doc_id, chunk_index,
        page_number, text, metadata, rrf_score.
        """
        overfetch = max(top_k * OVERFETCH_FACTOR, 60)

        # Step 1: Generate embedding
        embedding = await self._embed(query)

        # Step 2: Run vector + keyword search in parallel
        async with AsyncSession(self._engine) as session:
            # We run them sequentially here for simplicity; the DB
            # handles the parallelism internally.  For true Python-level
            # parallelism we could use asyncio.gather, but the latency
            # difference is negligible for a single connection.
            vector_hits = await self._vector_search(session, embedding, overfetch)
            keyword_hits = await self._keyword_search(session, query, overfetch)

        logger.info(
            "Hybrid search: %d vector hits, %d keyword hits",
            len(vector_hits), len(keyword_hits),
        )

        # Step 3: RRF fusion
        merged = self._rrf_merge(vector_hits, keyword_hits)

        # Step 4: Deep content bias
        merged = self._apply_deep_bias(merged)

        # Step 5: Return top-k
        return merged[:top_k]
