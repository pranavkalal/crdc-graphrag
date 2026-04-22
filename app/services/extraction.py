"""Extraction chains for IPM knowledge graph using Gemini structured output."""

from pydantic import BaseModel, Field

from app.infrastructure.gemini_client import GeminiClient


# ── Schema: Pest-Chemical Control Table ─────────────────────────────────────

class ChemicalExtraction(BaseModel):
    """Extracted attributes for a chemical regarding a specific pest."""
    name: str = Field(description="Name of the active ingredient")
    moa_group_code: str = Field(description="Mode of Action group code, e.g. 1A, UNM, 4A. Use 'Unknown' if not specified.")
    resistance_status: str | None = Field(default=None, description="Known resistance status, e.g. 'Widespread resistance', 'Unknown'")
    beneficial_impact: str | None = Field(default=None, description="Impact on beneficial insects (e.g. Very low, Low, Moderate, High, Very high)")
    max_applications: str | None = Field(default=None, description="Constraints such as 'Maximum 2 applications per season'")

class PestChemicalTableExtraction(BaseModel):
    """Top-level extraction schema for a control table."""
    pest_name: str = Field(description="Common name of the primary pest being controlled in this table")
    chemicals: list[ChemicalExtraction]


# ── Schema: Disease Extraction (prose-based) ────────────────────────────────

class DiseaseItem(BaseModel):
    """A single disease entity extracted from prose."""
    name: str = Field(description="Common name of the disease (e.g. Black root rot, Fusarium wilt)")
    pathogen: str | None = Field(default=None, description="Scientific name of the causal pathogen (e.g. Berkeleyomyces rouxiae)")
    symptoms: str | None = Field(default=None, description="Brief summary of key symptoms")
    favoured_by: str | None = Field(default=None, description="Conditions that favour the disease (e.g. cool wet soils)")
    management_tactics: str | None = Field(default=None, description="Summary of IDM tactics")

class DiseaseExtraction(BaseModel):
    """Extraction result for a diseases section."""
    diseases: list[DiseaseItem] = Field(description="All diseases found in the text")


# ── Schema: Beneficial Insect Extraction (prose-based) ──────────────────────

class BeneficialItem(BaseModel):
    """A beneficial insect or spider extracted from prose."""
    name: str = Field(description="Common name (e.g. Red and blue beetle, Trichogramma)")
    scientific_name: str | None = Field(default=None, description="Scientific name if mentioned")
    beneficial_type: str = Field(description="One of: predator, parasitoid, or predator/parasitoid")
    prey_pests: list[str] = Field(default_factory=list, description="List of pest names this beneficial attacks (e.g. ['Helicoverpa eggs', 'aphids', 'mites'])")

class BeneficialExtraction(BaseModel):
    """Extraction result for a beneficials section."""
    beneficials: list[BeneficialItem] = Field(description="All beneficial insects found in the text")


# ── Schema: Defoliant Chemical Extraction ───────────────────────────────────

class DefoliantItem(BaseModel):
    """A defoliant/harvest aid chemical."""
    name: str = Field(description="Active ingredient name (e.g. Thidiazuron, Ethephon)")
    product_type: str = Field(description="One of: defoliant, boll opener, desiccant")
    trade_names: list[str] = Field(default_factory=list, description="Trade name examples (e.g. ['Dropp', 'Escalate'])")
    key_notes: str | None = Field(default=None, description="Brief usage notes or temperature constraints")

class DefoliantExtraction(BaseModel):
    """Extraction result for a defoliation section."""
    chemicals: list[DefoliantItem] = Field(description="All harvest aid chemicals found in the text")


# ── Schema: Variety Extraction ──────────────────────────────────────────────

class TraitItem(BaseModel):
    """A genetic trait possessed by a variety."""
    name: str = Field(description="Name of the trait (e.g. Bollgard 3, Roundup Ready Flex, XtendFlex)")
    description: str | None = Field(default=None, description="Brief description of the trait's purpose")

class VarietyItem(BaseModel):
    """A cotton variety and its suited regions and traits."""
    name: str = Field(description="Name of the variety (e.g. Sicot 748B3F)")
    company: str | None = Field(default=None, description="Seed company (e.g. CSD, Bayer)")
    crop_type: str | None = Field(default=None, description="Type of cotton (e.g. Upland, Pima)")
    suited_regions: list[str] = Field(default_factory=list, description="Regions this variety is suited for")
    traits: list[TraitItem] = Field(default_factory=list, description="Traits this variety possesses")

class VarietyExtraction(BaseModel):
    """Extraction result for a varieties section."""
    varieties: list[VarietyItem] = Field(description="All varieties found in the text")


# ── Schema: Weed Extraction ──────────────────────────────────────────────────

class WeedItem(BaseModel):
    """A weed entity and herbicides that control it."""
    name: str = Field(description="Common name of the weed (e.g. Fleabane, Feathertop Rhodes grass)")
    scientific_name: str | None = Field(default=None, description="Scientific name if mentioned")
    weed_type: str | None = Field(default=None, description="Type of weed (e.g. grass, broadleaf)")
    controlled_by: list[str] = Field(default_factory=list, description="List of herbicides or chemicals that control this weed")

class WeedExtraction(BaseModel):
    """Extraction result for a weeds section."""
    weeds: list[WeedItem] = Field(description="All weeds found in the text")


# ── Schema: Crop Stage Extraction ────────────────────────────────────────────

class CropStageItem(BaseModel):
    """A stage of crop growth."""
    name: str = Field(description="Name of the growth stage (e.g. Emergence, First Square, First Flower)")
    phase: str | None = Field(default=None, description="Broader phase (e.g. Vegetative, Reproductive)")
    precedes: list[str] = Field(default_factory=list, description="Names of the stages that immediately follow this one")

class CropStageExtraction(BaseModel):
    """Extraction result for crop stages."""
    stages: list[CropStageItem] = Field(description="All crop stages found in the text")


# ── Service ─────────────────────────────────────────────────────────────────

class ExtractionService:
    """Service to coordinate extraction from document chunks."""

    def __init__(self, gemini_client: GeminiClient):
        self._client = gemini_client

    async def extract_pest_chemical_table(self, table_text: str) -> PestChemicalTableExtraction:
        """Extract Pest, Chemical, and MoAGroup relationships from control tables."""
        extractor = self._client.get_extractor(PestChemicalTableExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton pest management knowledge graph.\n"
            "Extract the primary pest name and ALL associated chemical control options from the following Markdown table.\n\n"
            f"Here is the table text:\n{table_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_diseases(self, prose_text: str) -> DiseaseExtraction:
        """Extract Disease entities from prose disease descriptions."""
        extractor = self._client.get_extractor(DiseaseExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton disease management knowledge graph.\n"
            "Extract ALL cotton diseases mentioned in the following text.\n"
            "For each disease, capture its common name, the pathogen's scientific name, the key symptoms, "
            "what conditions favour it, and any management tactics.\n"
            "Only extract actual named diseases — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_beneficials(self, prose_text: str) -> BeneficialExtraction:
        """Extract Beneficial insect entities and the pests they prey on."""
        extractor = self._client.get_extractor(BeneficialExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton IPM knowledge graph.\n"
            "Extract ALL beneficial insects and spiders mentioned in the following text.\n"
            "For each, capture: common name, scientific name if given, whether it is a predator or parasitoid, "
            "and exactly which cotton pests it attacks or preys on.\n"
            "Only extract named beneficial organisms — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_defoliants(self, prose_text: str) -> DefoliantExtraction:
        """Extract defoliant/harvest aid chemicals from the defoliation guide."""
        extractor = self._client.get_extractor(DefoliantExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
            "Extract ALL harvest aid chemicals (defoliants, boll openers, desiccants) from the following text.\n"
            "For each, capture: active ingredient name, product type (defoliant/boll opener/desiccant), "
            "any trade name examples, and key usage notes.\n"
            "Only extract named chemicals — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_varieties(self, prose_text: str) -> VarietyExtraction:
        """Extract cotton varieties, their traits, and suited regions."""
        extractor = self._client.get_extractor(VarietyExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
            "Extract ALL cotton varieties mentioned in the following text.\n"
            "For each variety, capture its name, seed company, crop type (Upland/Pima), "
            "the regions it is suited to, and the specific genetic traits it has (e.g., Bollgard 3).\n"
            "Only extract named varieties — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_weeds(self, prose_text: str) -> WeedExtraction:
        """Extract weeds and the herbicides that control them."""
        extractor = self._client.get_extractor(WeedExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
            "Extract ALL weeds mentioned in the following text.\n"
            "For each weed, capture its common name, scientific name (if any), weed type, "
            "and a list of herbicides or chemical active ingredients mentioned as controlling it.\n"
            "Only extract named weeds — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)

    async def extract_crop_stages(self, prose_text: str) -> CropStageExtraction:
        """Extract crop growth stages and their chronological order."""
        extractor = self._client.get_extractor(CropStageExtraction)
        prompt = (
            "You are an entity extraction agent for an Australian cotton knowledge graph.\n"
            "Extract ALL crop growth stages mentioned in the following text.\n"
            "For each stage, capture its name, the broader phase it belongs to, "
            "and the names of the stages that directly follow it (to establish a 'precedes' timeline).\n"
            "Only extract named stages — do not invent any.\n\n"
            f"Here is the text:\n{prose_text}"
        )
        return await extractor.ainvoke(prompt)
