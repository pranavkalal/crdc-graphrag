"""
Usage: python -m scripts.seed_graph_docs

Phase 2 extraction: processes prose-based documents beyond the CPMG tables.
Targets:
  1. Disease sections from CPMG 2025 (Key diseases chapter)
  2. Beneficial insects from IPM Guidelines & IPM Booklet 2024
  3. Defoliant chemicals from Defoliation Booklet 2024
"""

import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv
import os

from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.graph_repository import GraphRepository
from app.services.extraction import ExtractionService

# ── Data paths ──────────────────────────────────────────────────────────────
DATA_DIR = Path("data/Parsed/OpenDataLoader/Markdown")

# Known pest names in our graph (for linking PREDATES relationships)
KNOWN_PESTS = {
    "helicoverpa": "Helicoverpa",
    "aphid": "Cotton aphid",
    "aphids": "Cotton aphid",
    "cotton aphid": "Cotton aphid",
    "mirid": "Green mirid",
    "mirids": "Green mirid",
    "green mirid": "Green mirid",
    "mite": "Two-spotted spider mite",
    "mites": "Two-spotted spider mite",
    "two-spotted mite": "Two-spotted spider mite",
    "spider mite": "Two-spotted spider mite",
    "two spotted mite": "Two-spotted spider mite",
    "whitefly": "Silverleaf whitefly",
    "silverleaf whitefly": "Silverleaf whitefly",
    "slw": "Silverleaf whitefly",
    "thrips": "Thrips",
    "mealybug": "Solenopsis mealybug",
    "solenopsis mealybug": "Solenopsis mealybug",
    "wireworm": "Wireworm",
    "green vegetable bug": "Green vegetable bug",
    "gvb": "Green vegetable bug",
}


def resolve_pest_name(raw: str) -> str | None:
    """Fuzzy-match a pest name from LLM output to our graph's canonical names."""
    raw_lower = raw.lower().strip()
    # Direct match
    if raw_lower in KNOWN_PESTS:
        return KNOWN_PESTS[raw_lower]
    # Substring match
    for key, canonical in KNOWN_PESTS.items():
        if key in raw_lower or raw_lower in key:
            return canonical
    return None


def load_lines(filepath: Path, start: int, end: int) -> str:
    """Read a specific line range from a file (1-indexed, inclusive)."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    return "\n".join(lines[start - 1 : end])


# ── Extraction tasks ───────────────────────────────────────────────────────

async def extract_diseases(
    extractor: ExtractionService,
    graph_repo: GraphRepository,
) -> dict:
    """Extract diseases from CPMG 2025 Key Diseases chapter (lines 5549-6500)."""
    print("\n  ── Diseases (CPMG 2025 Key Diseases) ──")
    filepath = DATA_DIR / "CPMG 2025.md"
    text = load_lines(filepath, 5549, 6500)

    try:
        result = await extractor.extract_diseases(text)
    except Exception as e:
        print(f"  ⚠ Extraction FAILED: {e}")
        return {"section": "diseases", "status": "FAILED", "count": 0}

    print(f"  Gemini returned {len(result.diseases)} diseases.")

    for d in result.diseases:
        await graph_repo.merge_disease(
            name=d.name,
            pathogen=d.pathogen,
            symptoms=d.symptoms,
            favoured_by=d.favoured_by,
            management=d.management_tactics,
            source="CPMG 2025 Key Diseases",
        )
        await graph_repo.merge_affects_crop(d.name)
        print(f"    ✓ {d.name} (pathogen: {d.pathogen or 'N/A'})")

    return {"section": "diseases", "status": "OK", "count": len(result.diseases)}


async def extract_beneficials(
    extractor: ExtractionService,
    graph_repo: GraphRepository,
) -> dict:
    """Extract beneficial insects from IPM Guidelines section 3.3 and IPM Booklet."""
    print("\n  ── Beneficials (IPM Guidelines + IPM Booklet) ──")

    # Combine two source sections for richer extraction
    ipm_guidelines = DATA_DIR / "IPM_Guidelines.md"
    ipm_booklet = DATA_DIR / "IPM Booklet 2024_website.md"

    text_parts = []
    # IPM Guidelines: Beneficial section (lines 1817-2150)
    text_parts.append(load_lines(ipm_guidelines, 1817, 2150))
    # IPM Booklet: beneficial sections (lines 622-710)
    text_parts.append(load_lines(ipm_booklet, 622, 710))

    combined_text = "\n\n".join(text_parts)

    try:
        result = await extractor.extract_beneficials(combined_text)
    except Exception as e:
        print(f"  ⚠ Extraction FAILED: {e}")
        return {"section": "beneficials", "status": "FAILED", "count": 0}

    print(f"  Gemini returned {len(result.beneficials)} beneficial organisms.")

    linked_count = 0
    for b in result.beneficials:
        await graph_repo.merge_beneficial(
            name=b.name,
            scientific_name=b.scientific_name,
            beneficial_type=b.beneficial_type,
            source="IPM Guidelines / IPM Booklet 2024",
        )

        # Try to link PREDATES to known pests in our graph
        for prey in b.prey_pests:
            canonical = resolve_pest_name(prey)
            if canonical:
                await graph_repo.merge_predates(b.name, canonical)
                linked_count += 1

        prey_str = ", ".join(b.prey_pests[:3]) or "N/A"
        print(f"    ✓ {b.name} ({b.beneficial_type}) → preys on: {prey_str}")

    return {"section": "beneficials", "status": "OK", "count": len(result.beneficials), "links": linked_count}


async def extract_defoliants(
    extractor: ExtractionService,
    graph_repo: GraphRepository,
) -> dict:
    """Extract harvest aid chemicals from Defoliation Booklet 2024."""
    print("\n  ── Defoliants (Defoliation Booklet 2024) ──")
    filepath = DATA_DIR / "Defoliation Booklet 2024.md"
    text = load_lines(filepath, 100, 280)

    try:
        result = await extractor.extract_defoliants(text)
    except Exception as e:
        print(f"  ⚠ Extraction FAILED: {e}")
        return {"section": "defoliants", "status": "FAILED", "count": 0}

    print(f"  Gemini returned {len(result.chemicals)} harvest aid chemicals.")

    for c in result.chemicals:
        await graph_repo.merge_defoliant(
            name=c.name,
            product_type=c.product_type,
            trade_names=c.trade_names,
            key_notes=c.key_notes,
            source="Defoliation Booklet 2024",
        )
        trades = ", ".join(c.trade_names[:2]) if c.trade_names else "N/A"
        print(f"    ✓ {c.name} ({c.product_type}) — trades: {trades}")

    return {"section": "defoliants", "status": "OK", "count": len(result.chemicals)}


async def extract_tropical_diseases(
    extractor: ExtractionService,
    graph_repo: GraphRepository,
) -> dict:
    """Extract disease mentions from Tropical Cotton guide."""
    print("\n  ── Tropical Diseases (2025 Tropical Cotton) ──")
    filepath = DATA_DIR / "2025 - Tropical Cotton.md"
    # The entire document is relevant for disease/region mentions
    text = filepath.read_text(encoding="utf-8")
    # Truncate if too long for a single call (take first ~15k chars to stay under token limits)
    text = text[:15000]

    try:
        result = await extractor.extract_diseases(text)
    except Exception as e:
        print(f"  ⚠ Extraction FAILED: {e}")
        return {"section": "tropical_diseases", "status": "FAILED", "count": 0}

    print(f"  Gemini returned {len(result.diseases)} diseases.")

    for d in result.diseases:
        await graph_repo.merge_disease(
            name=d.name,
            pathogen=d.pathogen,
            symptoms=d.symptoms,
            favoured_by=d.favoured_by,
            management=d.management_tactics,
            source="Tropical Cotton 2025",
        )
        await graph_repo.merge_affects_crop(d.name)
        print(f"    ✓ {d.name} (pathogen: {d.pathogen or 'N/A'})")

    return {"section": "tropical_diseases", "status": "OK", "count": len(result.diseases)}


# ── Main ────────────────────────────────────────────────────────────────────

async def main():
    load_dotenv()

    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_user = os.environ.get("NEO4J_USERNAME")
    neo4j_pass = os.environ.get("NEO4J_PASSWORD")
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    if not neo4j_pass:
        print("ERROR: Please set NEO4J_PASSWORD in the .env file")
        return

    print("=" * 60)
    print("  CRDC Knowledge Graph — Multi-Document Extraction")
    print("=" * 60)

    print("\n[1/3] Connecting to Neo4j Aura...")
    neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_pass, database=neo4j_database)
    await neo4j_client.connect()
    graph_repo = GraphRepository(neo4j_client)
    print("  ✓ Connected.")

    print("\n[2/3] Initializing Gemini extraction client...")
    gemini_client = GeminiClient(gemini_key, gemini_model)
    extractor = ExtractionService(gemini_client)
    print(f"  ✓ Model: {gemini_model}")

    print(f"\n[3/3] Running 4 extraction tasks across multiple documents...")
    start_time = time.time()

    results = []

    # 1. Diseases from CPMG
    results.append(await extract_diseases(extractor, graph_repo))
    await asyncio.sleep(1)

    # 2. Beneficials from IPM Guidelines + Booklet
    results.append(await extract_beneficials(extractor, graph_repo))
    await asyncio.sleep(1)

    # 3. Defoliants from Defoliation Booklet
    results.append(await extract_defoliants(extractor, graph_repo))
    await asyncio.sleep(1)

    # 4. Tropical diseases
    results.append(await extract_tropical_diseases(extractor, graph_repo))

    elapsed = time.time() - start_time

    # ── Summary ─────────────────────────────────────────────────────────────
    stats = await graph_repo.get_graph_stats()
    label_counts = await graph_repo.get_label_counts()

    print("\n" + "=" * 60)
    print("  EXTRACTION SUMMARY")
    print("=" * 60)

    for r in results:
        icon = "✓" if r["status"] == "OK" else "✗"
        extra = f" ({r.get('links', 0)} PREDATES links)" if "links" in r else ""
        print(f"  {icon} {r['section']:<25} → {r['count']} entities{extra}")

    print(f"\n  Neo4j totals:")
    print(f"    Nodes:         {stats['nodes']}")
    print(f"    Relationships: {stats['relationships']}")
    print(f"  By label:")
    for lc in label_counts:
        print(f"    {lc['label']:<15} {lc['count']}")
    print(f"  Time elapsed: {elapsed:.1f}s")
    print("=" * 60)

    await neo4j_client.close()
    print("\n✓ Done. Open Neo4j Workspace to visualize: https://console.neo4j.io")


if __name__ == "__main__":
    asyncio.run(main())
