"""
Graph Expansion: 6-batch extraction pipeline.

Batch 1: ACPM Glossary + Acronyms  (~260 nodes)
Batch 2: ACPM Varieties + Traits   (~33 nodes)
Batch 3: ACPM Weeds + Herbicides   (~20 nodes)
Batch 4: ACPM Crop Stages          (~10 nodes)
Batch 5: Biosecurity Exotic Threats (~16 nodes)
Batch 6: IPM Thresholds            (~15 nodes)

Usage:
    python -m scripts.seed_graph_expansion            # all batches
    python -m scripts.seed_graph_expansion --batch 1   # single batch
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.neo4j_client import Neo4jClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ACPM = Path("data/Parsed/OpenDataLoader/Markdown/2025 Australian Cotton Production Manual_interactive_sml.md")
BIOSECURITY = Path("data/Parsed/OpenDataLoader/Markdown/Farm-Biosecurity-Manual-for-the-Cotton-Industry.md")
IPM = Path("data/Parsed/OpenDataLoader/Markdown/IPM_Guidelines.md")


def read_lines(path: Path, start: int, end: int) -> str:
    """Read lines [start, end] (1-indexed) from a file."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[start - 1 : end])


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION SCHEMAS (Pydantic models for Gemini structured output)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Batch 1: Glossary ---
class GlossaryTerm(BaseModel):
    term: str = Field(description="The term or phrase being defined")
    definition: str = Field(description="The definition or explanation")

class GlossaryExtraction(BaseModel):
    terms: list[GlossaryTerm] = Field(description="All glossary terms and definitions")

class AcronymItem(BaseModel):
    acronym: str = Field(description="The acronym (e.g. CRDC, IPM)")
    expanded_form: str = Field(description="The full expanded form")

class AcronymExtraction(BaseModel):
    acronyms: list[AcronymItem] = Field(description="All acronyms and their expanded forms")

# --- Batch 2: Varieties ---
class TraitInfo(BaseModel):
    name: str = Field(description="Name of the trait (e.g. Bollgard 3, XtendFlex, Roundup Ready Flex)")
    description: str | None = Field(default=None, description="Brief description")

class VarietyInfo(BaseModel):
    name: str = Field(description="Name of the variety (e.g. Sicot 748B3F, Sicot 714B3F)")
    company: str | None = Field(default=None, description="Seed company (e.g. CSD, Bayer)")
    crop_type: str | None = Field(default=None, description="Upland or Pima")
    suited_regions: list[str] = Field(default_factory=list, description="Growing regions suited for")
    traits: list[TraitInfo] = Field(default_factory=list, description="Genetic traits")
    f_rank: str | None = Field(default=None, description="Fusarium wilt resistance rank if mentioned")
    v_rank: str | None = Field(default=None, description="Verticillium wilt resistance rank if mentioned")

class VarietyExtraction(BaseModel):
    varieties: list[VarietyInfo] = Field(description="All cotton varieties found")

# --- Batch 3: Weeds ---
class WeedInfo(BaseModel):
    name: str = Field(description="Common name (e.g. Fleabane, Feathertop Rhodes grass)")
    scientific_name: str | None = Field(default=None, description="Scientific name")
    weed_type: str | None = Field(default=None, description="grass, broadleaf, sedge, etc.")
    controlled_by: list[str] = Field(default_factory=list, description="Herbicide active ingredients that control this weed")
    resistance_noted: list[str] = Field(default_factory=list, description="Herbicides this weed has resistance to, if mentioned")

class WeedExtraction(BaseModel):
    weeds: list[WeedInfo] = Field(description="All weeds found in the text")

# --- Batch 4: Crop Stages ---
class CropStageInfo(BaseModel):
    name: str = Field(description="Stage name (e.g. Emergence, First Square, First Flower)")
    phase: str | None = Field(default=None, description="Broader phase: Vegetative, Reproductive, Maturation")
    follows: str | None = Field(default=None, description="The stage that comes immediately before this one")

class CropStageExtraction(BaseModel):
    stages: list[CropStageInfo] = Field(description="All growth stages in chronological order")

# --- Batch 5: Biosecurity ---
class ExoticThreatInfo(BaseModel):
    name: str = Field(description="Name of the exotic pest or disease")
    threat_type: str = Field(description="pest or disease")
    risk_rating: str = Field(description="EXTREME, HIGH, or MEDIUM")
    pathogen_or_species: str | None = Field(default=None, description="Scientific name of pathogen/pest")
    symptoms: str | None = Field(default=None, description="Key symptoms")
    spread_mechanism: str | None = Field(default=None, description="How it spreads")
    found_in: str | None = Field(default=None, description="Regions where it is found")

class BiosecurityExtraction(BaseModel):
    threats: list[ExoticThreatInfo] = Field(description="All exotic pest/disease threats")

# --- Batch 6: IPM Thresholds ---
class ThresholdInfo(BaseModel):
    pest_name: str = Field(description="Name of the pest this threshold applies to")
    threshold_value: str = Field(description="The numeric threshold value (e.g. '2 per metre', '30% infested')")
    crop_phase: str | None = Field(default=None, description="When this threshold applies (e.g. 'seedling to first flower')")
    sampling_method: str | None = Field(default=None, description="How to sample (e.g. 'beat sheet', 'visual count')")
    notes: str | None = Field(default=None, description="Additional notes or conditions")

class ThresholdExtraction(BaseModel):
    thresholds: list[ThresholdInfo] = Field(description="All pest thresholds found")


# ═══════════════════════════════════════════════════════════════════════════════
# MERGE HELPERS (direct Cypher against Neo4j)
# ═══════════════════════════════════════════════════════════════════════════════

async def merge_term(db: Neo4jClient, term: str, definition: str, source: str) -> None:
    await db.run_query(
        "MERGE (t:Term {canonical_term: $term}) SET t.definition = $definition, t.source = $source",
        {"term": term, "definition": definition, "source": source},
    )

async def merge_acronym(db: Neo4jClient, acronym: str, expanded: str, source: str) -> None:
    await db.run_query(
        "MERGE (a:Acronym {acronym: $acronym}) SET a.expanded_form = $expanded, a.source = $source",
        {"acronym": acronym, "expanded": expanded, "source": source},
    )

async def merge_variety(db: Neo4jClient, v: VarietyInfo, source: str) -> None:
    await db.run_query(
        "MERGE (v:Variety {name: $name}) SET v.company = $company, v.crop_type = $crop_type, v.f_rank = $f_rank, v.v_rank = $v_rank, v.source = $source",
        {"name": v.name, "company": v.company, "crop_type": v.crop_type, "f_rank": v.f_rank, "v_rank": v.v_rank, "source": source},
    )
    for r in v.suited_regions:
        await db.run_query(
            "MERGE (r:Region {name: $region}) WITH r MATCH (v:Variety {name: $variety}) MERGE (v)-[:SUITED_TO]->(r)",
            {"region": r, "variety": v.name},
        )
    for t in v.traits:
        await db.run_query(
            "MERGE (t:Trait {name: $trait}) ON CREATE SET t.description = $desc WITH t MATCH (v:Variety {name: $variety}) MERGE (v)-[:HAS_TRAIT]->(t)",
            {"trait": t.name, "desc": t.description, "variety": v.name},
        )

async def merge_weed(db: Neo4jClient, w: WeedInfo, source: str) -> None:
    await db.run_query(
        "MERGE (w:Weed {name: $name}) SET w.scientific_name = $sci, w.weed_type = $wtype, w.source = $source",
        {"name": w.name, "sci": w.scientific_name, "wtype": w.weed_type, "source": source},
    )
    for chem in w.controlled_by:
        await db.run_query(
            "MERGE (c:Chemical {name: $chem}) ON CREATE SET c.chemical_type = 'Herbicide' WITH c MATCH (w:Weed {name: $weed}) MERGE (w)-[:CONTROLLED_BY]->(c)",
            {"chem": chem, "weed": w.name},
        )
    for chem in w.resistance_noted:
        await db.run_query(
            "MERGE (c:Chemical {name: $chem}) WITH c MATCH (w:Weed {name: $weed}) MERGE (w)-[:HAS_RESISTANCE_TO]->(c)",
            {"chem": chem, "weed": w.name},
        )

async def merge_crop_stage(db: Neo4jClient, s: CropStageInfo, source: str) -> None:
    await db.run_query(
        "MERGE (cs:CropStage {name: $name}) SET cs.phase = $phase, cs.source = $source",
        {"name": s.name, "phase": s.phase, "source": source},
    )
    if s.follows:
        await db.run_query(
            "MERGE (prev:CropStage {name: $prev}) WITH prev MATCH (cs:CropStage {name: $name}) MERGE (prev)-[:PRECEDES]->(cs)",
            {"prev": s.follows, "name": s.name},
        )

async def merge_exotic_threat(db: Neo4jClient, t: ExoticThreatInfo, source: str) -> None:
    label = "Disease" if t.threat_type.lower() == "disease" else "Pest"
    if label == "Disease":
        await db.run_query(
            "MERGE (d:Disease {name: $name}) SET d.pathogen = $pathogen, d.symptoms = $symptoms, d.biosecurity_risk = $risk, d.spread_mechanism = $spread, d.found_in = $found_in, d.source = $source",
            {"name": t.name, "pathogen": t.pathogen_or_species, "symptoms": t.symptoms, "risk": t.risk_rating, "spread": t.spread_mechanism, "found_in": t.found_in, "source": source},
        )
    else:
        await db.run_query(
            "MERGE (p:Pest {name: $name}) SET p.scientific_name = $species, p.biosecurity_risk = $risk, p.spread_mechanism = $spread, p.found_in = $found_in, p.source = $source",
            {"name": t.name, "species": t.pathogen_or_species, "risk": t.risk_rating, "spread": t.spread_mechanism, "found_in": t.found_in, "source": source},
        )
    # Link to cotton crop
    await db.run_query(
        f"MERGE (c:Crop {{name: 'cotton'}}) WITH c MATCH (n:{label} {{name: $name}}) MERGE (n)-[:AFFECTS]->(c)",
        {"name": t.name},
    )

async def merge_threshold(db: Neo4jClient, t: ThresholdInfo, source: str) -> None:
    await db.run_query(
        "MERGE (th:Threshold {value: $value, pest_name: $pest}) SET th.crop_phase = $phase, th.sampling_method = $method, th.notes = $notes, th.source = $source",
        {"value": t.threshold_value, "pest": t.pest_name, "phase": t.crop_phase, "method": t.sampling_method, "notes": t.notes, "source": source},
    )
    # Link to pest
    await db.run_query(
        "MATCH (p:Pest {name: $pest}) MATCH (th:Threshold {value: $value, pest_name: $pest}) MERGE (p)-[:HAS_THRESHOLD]->(th)",
        {"pest": t.pest_name, "value": t.threshold_value},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH RUNNERS
# ═══════════════════════════════════════════════════════════════════════════════

async def run_batch_1(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 1: ACPM Glossary + Acronyms"""
    logger.info("═══ BATCH 1: Glossary + Acronyms ═══")
    count = 0

    # Glossary terms (lines 8407-8700)
    text = read_lines(ACPM, 8407, 8700)
    extractor = gemini.get_extractor(GlossaryExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent. Extract ALL glossary terms and their definitions from the following text. "
        "Each entry has a term/phrase followed by its definition on the same line. "
        "Extract every single term — do not skip any.\n\n" + text
    )
    for t in result.terms:
        await merge_term(db, t.term, t.definition, "ACPM 2025 Glossary")
        count += 1
    logger.info(f"  Merged {count} glossary terms.")

    # Acronyms (lines 8705-8772)
    text = read_lines(ACPM, 8705, 8772)
    extractor = gemini.get_extractor(AcronymExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent. Extract ALL acronyms and their expanded forms from the following text. "
        "The text contains lines like 'CRDC – Cotton Research & Development Corporation'. "
        "Extract every single acronym.\n\n" + text
    )
    acr_count = 0
    for a in result.acronyms:
        await merge_acronym(db, a.acronym, a.expanded_form, "ACPM 2025 Acronyms")
        acr_count += 1
    logger.info(f"  Merged {acr_count} acronyms.")
    return count + acr_count


async def run_batch_2(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 2: ACPM Varieties + Traits"""
    logger.info("═══ BATCH 2: Varieties + Traits ═══")
    text = read_lines(ACPM, 1780, 1900)
    extractor = gemini.get_extractor(VarietyExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
        "Extract ALL cotton varieties mentioned in the following text.\n"
        "For each variety, capture: name, seed company, crop type (Upland/Pima), "
        "suited regions, genetic traits (Bollgard 3, XtendFlex, Roundup Ready Flex), "
        "F rank (fusarium resistance) and V rank (verticillium resistance) if mentioned.\n"
        "Only extract named varieties — do not invent any.\n\n" + text
    )
    for v in result.varieties:
        await merge_variety(db, v, "ACPM 2025 Ch7")
    logger.info(f"  Merged {len(result.varieties)} varieties.")
    return len(result.varieties)


async def run_batch_3(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 3: ACPM Weeds + Herbicides"""
    logger.info("═══ BATCH 3: Weeds + Herbicides ═══")
    # Combine pest prevention + in-crop management chapters
    text = read_lines(ACPM, 2826, 3400)
    extractor = gemini.get_extractor(WeedExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
        "Extract ALL weeds mentioned in the following text.\n"
        "For each weed, capture: common name, scientific name, weed type (grass/broadleaf/sedge), "
        "herbicide active ingredients that control it, and any herbicide resistance noted.\n"
        "Only extract named weeds — do not invent any.\n\n" + text
    )
    for w in result.weeds:
        await merge_weed(db, w, "ACPM 2025 Ch11/16")
    logger.info(f"  Merged {len(result.weeds)} weeds.")
    return len(result.weeds)


async def run_batch_4(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 4: ACPM Crop Stages"""
    logger.info("═══ BATCH 4: Crop Stages ═══")
    text = read_lines(ACPM, 4300, 4600)
    extractor = gemini.get_extractor(CropStageExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
        "Extract ALL crop growth stages mentioned in the following text.\n"
        "Put them in chronological order. For each stage, capture: "
        "name, broader phase (Vegetative/Reproductive/Maturation), "
        "and the name of the stage that comes immediately before it.\n"
        "Common cotton stages include: Planting, Emergence, Seedling, First True Leaf, "
        "First Square, First Flower, Peak Flower, Cut-out, First Open Boll, Defoliation, Harvest.\n"
        "Only extract stages actually mentioned or clearly implied.\n\n" + text
    )
    for s in result.stages:
        await merge_crop_stage(db, s, "ACPM 2025 Ch15")
    logger.info(f"  Merged {len(result.stages)} crop stages.")
    return len(result.stages)


async def run_batch_5(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 5: Biosecurity Exotic Threats"""
    logger.info("═══ BATCH 5: Biosecurity Threats ═══")
    text = read_lines(BIOSECURITY, 210, 450)
    extractor = gemini.get_extractor(BiosecurityExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
        "Extract ALL exotic pest and disease threats mentioned in the following text.\n"
        "For each, capture: name, whether it's a pest or disease, risk rating (EXTREME/HIGH/MEDIUM), "
        "scientific name of the pathogen or pest species, key symptoms, "
        "spread mechanism, and where it has been found in the world.\n"
        "Only extract named threats.\n\n" + text
    )
    for t in result.threats:
        await merge_exotic_threat(db, t, "Biosecurity Manual")
    logger.info(f"  Merged {len(result.threats)} exotic threats.")
    return len(result.threats)


async def run_batch_6(gemini: GeminiClient, db: Neo4jClient) -> int:
    """Batch 6: IPM Thresholds"""
    logger.info("═══ BATCH 6: IPM Thresholds ═══")
    text = read_lines(IPM, 1099, 1220)
    extractor = gemini.get_extractor(ThresholdExtraction)
    result = await extractor.ainvoke(
        "You are an entity extraction agent for an Australian cotton IPM knowledge graph.\n"
        "Extract ALL pest control thresholds mentioned in the following text.\n"
        "For each threshold, capture: pest name, the threshold value (e.g. '2 per metre', '30% infested'), "
        "which crop phase it applies to, the recommended sampling method, and any additional notes.\n"
        "Only extract thresholds that have specific numeric values.\n\n" + text
    )
    for t in result.thresholds:
        await merge_threshold(db, t, "IPM Guidelines")
    logger.info(f"  Merged {len(result.thresholds)} thresholds.")
    return len(result.thresholds)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

BATCHES = {
    1: run_batch_1,
    2: run_batch_2,
    3: run_batch_3,
    4: run_batch_4,
    5: run_batch_5,
    6: run_batch_6,
}

async def main(batch: int | None = None) -> None:
    load_dotenv()

    neo4j_client = Neo4jClient(
        uri=os.environ["NEO4J_URI"],
        username=os.environ["NEO4J_USERNAME"],
        password=os.environ["NEO4J_PASSWORD"],
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    await neo4j_client.connect()

    gemini_client = GeminiClient(
        api_key=os.environ["GEMINI_API_KEY"],
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )

    total = 0
    try:
        if batch is not None:
            if batch not in BATCHES:
                logger.error(f"Unknown batch: {batch}. Valid: 1-6")
                return
            total = await BATCHES[batch](gemini_client, neo4j_client)
        else:
            for i in sorted(BATCHES):
                try:
                    count = await BATCHES[i](gemini_client, neo4j_client)
                    total += count
                except Exception as e:
                    logger.error(f"Batch {i} failed: {e}")
                    continue

        # Final stats
        stats = await neo4j_client.run_query("MATCH (n) RETURN count(n) AS nodes")
        rels = await neo4j_client.run_query("MATCH ()-[r]->() RETURN count(r) AS rels")
        labels = await neo4j_client.run_query(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
        )

        logger.info(f"\n{'═' * 50}")
        logger.info(f"TOTAL NEW ENTITIES MERGED: {total}")
        logger.info(f"GRAPH NOW: {stats[0]['nodes']} nodes, {rels[0]['rels']} relationships")
        logger.info(f"{'─' * 50}")
        for lbl in labels:
            logger.info(f"  {lbl['label']:20s} {lbl['count']:>5d}")
        logger.info(f"{'═' * 50}")

    finally:
        await neo4j_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graph Expansion Pipeline")
    parser.add_argument("--batch", type=int, default=None, help="Run specific batch (1-6)")
    args = parser.parse_args()
    asyncio.run(main(args.batch))
