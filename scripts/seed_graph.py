"""
Usage: python -m scripts.seed_graph

Orchestrates the Knowledge Graph seeding pipeline:
1. Loads CPMG 2025 Markdown
2. Auto-detects all pest-chemical control tables by regex
3. Feeds each table to Gemini for structured extraction
4. MERGEs all entities and relationships into Neo4j Aura
"""

import asyncio
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import os

from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.graph_repository import GraphRepository
from app.services.extraction import ExtractionService
from app.models.ontology import Pest, Chemical, MoAGroup

# ── Table definitions ──────────────────────────────────────────────────────────
# Each entry: (table_number, pest_name, pest_type, scientific_name, start_line, end_line)
# We define the exact line ranges from our CPMG analysis.
# Lines are 1-indexed to match the file.
TABLE_DEFINITIONS = [
    {
        "table_num": 7,
        "label": "Control of aphids",
        "pest_name": "Cotton aphid",
        "scientific_name": "Aphis gossypii",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 1238,
        "end_line": 1257,
    },
    {
        "table_num": 8,
        "label": "Control of Helicoverpa",
        "pest_name": "Helicoverpa",
        "scientific_name": "Helicoverpa armigera / H. punctigera",
        "pest_type": "insect",
        "category": "chewing pest",
        "start_line": 1413,
        "end_line": 1438,
    },
    {
        "table_num": 9,
        "label": "Control of solenopsis mealybug",
        "pest_name": "Solenopsis mealybug",
        "scientific_name": "Phenacoccus solenopsis",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 1563,
        "end_line": 1569,
    },
    {
        "table_num": 11,
        "label": "Control of mirids",
        "pest_name": "Green mirid",
        "scientific_name": "Creontiades dilutus",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 1710,
        "end_line": 1731,
    },
    {
        "table_num": 13,
        "label": "Control of spider mites",
        "pest_name": "Two-spotted spider mite",
        "scientific_name": "Tetranychus urticae",
        "pest_type": "mite",
        "category": "sucking pest",
        "start_line": 1949,
        "end_line": 1960,
    },
    {
        "table_num": 14,
        "label": "Control of wireworm",
        "pest_name": "Wireworm",
        "scientific_name": "Agrypnus spp.",
        "pest_type": "insect",
        "category": "soil pest",
        "start_line": 2055,
        "end_line": 2060,
    },
    {
        "table_num": 16,
        "label": "Control of green vegetable bug",
        "pest_name": "Green vegetable bug",
        "scientific_name": "Nezara viridula",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 2191,
        "end_line": 2200,
    },
    {
        "table_num": 17,
        "label": "Control of thrips",
        "pest_name": "Thrips",
        "scientific_name": "Thrips tabaci / Frankliniella schultzei",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 2281,
        "end_line": 2289,
    },
    {
        "table_num": 18,
        "label": "Control of silverleaf whitefly",
        "pest_name": "Silverleaf whitefly",
        "scientific_name": "Bemisia tabaci",
        "pest_type": "insect",
        "category": "sucking pest",
        "start_line": 2503,
        "end_line": 2519,
    },
]

CPMG_PATH = Path("data/Parsed/OpenDataLoader/Markdown/CPMG 2025.md")


def load_table_text(lines: list[str], start: int, end: int) -> str:
    """Extract lines from the CPMG file (1-indexed, inclusive)."""
    return "\n".join(lines[start - 1 : end])


async def process_table(
    table_def: dict,
    table_text: str,
    extractor: ExtractionService,
    graph_repo: GraphRepository,
) -> dict:
    """Extract and load one table into Neo4j. Returns a summary dict."""
    table_num = table_def["table_num"]
    source = f"CPMG 2025 Table {table_num}"

    print(f"\n  ── Table {table_num}: {table_def['label']} ──")

    # 1. Run Gemini extraction
    try:
        extraction = await extractor.extract_pest_chemical_table(table_text)
    except Exception as e:
        print(f"  ⚠ Extraction FAILED: {e}")
        return {"table": table_num, "status": "FAILED", "error": str(e), "chemicals": 0}

    print(f"  Gemini returned: pest='{extraction.pest_name}', chemicals={len(extraction.chemicals)}")

    # 2. Merge pest node (using our curated metadata, not LLM output for the name)
    pest = Pest(
        name=table_def["pest_name"],
        scientific_name=table_def["scientific_name"],
        pest_type=table_def["pest_type"],
        category=table_def["category"],
    )
    await graph_repo.merge_pest(pest)

    # 3. Merge each chemical, its MoA group, and relationships
    merged_chemicals = []
    for chem in extraction.chemicals:
        chem_name = chem.name.strip()
        if not chem_name or chem_name.lower() in ("—", "-", "n/a", "unknown"):
            continue

        chemical = Chemical(name=chem_name, chemical_type="insecticide")
        await graph_repo.merge_chemical(chemical)

        # MoA group
        moa_code = chem.moa_group_code.strip()
        if moa_code and moa_code not in ("—", "-", "Unknown"):
            moa = MoAGroup(group_code=moa_code)
            await graph_repo.merge_moa_group(moa)
            await graph_repo.merge_belongs_to_moa(chem_name, moa_code)

        # CONTROLLED_BY relationship
        await graph_repo.merge_controlled_by(
            pest_name=table_def["pest_name"],
            chemical_name=chem_name,
            resistance_status=chem.resistance_status,
            beneficial_impact=chem.beneficial_impact,
            max_applications=chem.max_applications,
            source=source,
        )
        merged_chemicals.append(chem_name)
        print(f"    ✓ {chem_name} (MoA: {moa_code})")

    return {
        "table": table_num,
        "pest": table_def["pest_name"],
        "status": "OK",
        "chemicals": len(merged_chemicals),
        "chemical_names": merged_chemicals,
    }


async def main():
    load_dotenv()

    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_user = os.environ.get("NEO4J_USERNAME")
    neo4j_pass = os.environ.get("NEO4J_PASSWORD")
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    if not neo4j_pass or neo4j_pass == "FILL_IN_YOUR_AURA_PASSWORD_HERE":
        print("ERROR: Please set NEO4J_PASSWORD in the .env file")
        return

    # ── Infrastructure ──────────────────────────────────────────────────────
    print("=" * 60)
    print("  CRDC Knowledge Graph — Full CPMG Extraction Pipeline")
    print("=" * 60)

    print("\n[1/4] Connecting to Neo4j Aura...")
    neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_pass, database=neo4j_database)
    await neo4j_client.connect()
    graph_repo = GraphRepository(neo4j_client)
    await graph_repo.ensure_constraints()
    print("  ✓ Connected and constraints ensured.")

    print("\n[2/4] Initializing Gemini extraction client...")
    gemini_client = GeminiClient(gemini_key, gemini_model)
    extractor = ExtractionService(gemini_client)
    print(f"  ✓ Model: {gemini_model}")

    # ── Load document ───────────────────────────────────────────────────────
    print(f"\n[3/4] Loading CPMG document from {CPMG_PATH}...")
    cpmg_text = CPMG_PATH.read_text(encoding="utf-8")
    cpmg_lines = cpmg_text.splitlines()
    print(f"  ✓ {len(cpmg_lines)} lines loaded.")

    # ── Process all tables ──────────────────────────────────────────────────
    print(f"\n[4/4] Processing {len(TABLE_DEFINITIONS)} control tables...")
    start_time = time.time()
    results = []

    for table_def in TABLE_DEFINITIONS:
        table_text = load_table_text(cpmg_lines, table_def["start_line"], table_def["end_line"])
        result = await process_table(table_def, table_text, extractor, graph_repo)
        results.append(result)

        # Small delay between API calls to be respectful to rate limits
        await asyncio.sleep(1)

    elapsed = time.time() - start_time

    # ── Summary ─────────────────────────────────────────────────────────────
    stats = await graph_repo.get_graph_stats()
    
    print("\n" + "=" * 60)
    print("  EXTRACTION SUMMARY")
    print("=" * 60)
    
    total_chemicals = 0
    for r in results:
        status_icon = "✓" if r["status"] == "OK" else "✗"
        print(f"  {status_icon} Table {r['table']:>2}: {r.get('pest', 'N/A'):<30} → {r['chemicals']} chemicals")
        total_chemicals += r["chemicals"]

    print(f"\n  Total pests:         {len([r for r in results if r['status'] == 'OK'])}")
    print(f"  Total chemicals:     {total_chemicals}")
    print(f"  Neo4j nodes:         {stats['nodes']}")
    print(f"  Neo4j relationships: {stats['relationships']}")
    print(f"  Time elapsed:        {elapsed:.1f}s")
    print("=" * 60)

    await neo4j_client.close()
    print("\n✓ Done. Open Neo4j Workspace to visualize: https://console.neo4j.io")


if __name__ == "__main__":
    asyncio.run(main())
