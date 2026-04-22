"""Pydantic models that define the pilot graph ontology and IPM extension."""

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeLabel(str, Enum):
    """Labels used for graph nodes in the ontology."""
    # Base Pilot
    TERM = "Term"
    ACRONYM = "Acronym"
    DOCUMENT = "Document"
    AUTHOR = "Author"
    # IPM Extension
    PEST = "Pest"
    CHEMICAL = "Chemical"
    MOA_GROUP = "MoAGroup"
    BENEFICIAL = "Beneficial"
    CROP_STAGE = "CropStage"
    THRESHOLD = "Threshold"
    RESEARCHER = "Researcher"
    ORGANISATION = "Organisation"
    DISEASE = "Disease"
    VARIETY = "Variety"
    REGION = "Region"
    WEED = "Weed"
    TRAIT = "Trait"


class RelationshipType(str, Enum):
    """Relationship types supported in the ontology."""
    # Base Pilot
    DEFINED_IN = "DEFINED_IN"
    WRITTEN_BY = "WRITTEN_BY"
    # IPM Extension
    CONTROLLED_BY = "CONTROLLED_BY"
    BELONGS_TO = "BELONGS_TO"
    HAS_THRESHOLD = "HAS_THRESHOLD"
    PREDATES = "PREDATES"
    PARASITISES = "PARASITISES"
    IMPACTS_BENEFICIAL = "IMPACTS_BENEFICIAL"
    HAS_RESISTANCE_TO = "HAS_RESISTANCE_TO"
    HOSTS_ON = "HOSTS_ON"
    ACTIVE_DURING = "ACTIVE_DURING"
    SPECIALISES_IN = "SPECIALISES_IN"
    RESISTANT_TO = "RESISTANT_TO"
    HAS_TRAIT = "HAS_TRAIT"
    PRECEDES = "PRECEDES"
    SUITED_TO = "SUITED_TO"


class BaseNode(BaseModel):
    """Shared fields across ontology node models."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: NodeLabel


# --- Base Pilot Models ---
class Term(BaseNode):
    label: Literal[NodeLabel.TERM] = NodeLabel.TERM
    canonical_term: str
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)

class Acronym(BaseNode):
    label: Literal[NodeLabel.ACRONYM] = NodeLabel.ACRONYM
    acronym: str
    expanded_form: str
    description: str | None = None

class Document(BaseNode):
    label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT
    document_id: str
    title: str
    source_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class Author(BaseNode):
    label: Literal[NodeLabel.AUTHOR] = NodeLabel.AUTHOR
    name: str
    organization: str | None = None


# --- IPM Extension Node Models ---
class Pest(BaseNode):
    label: Literal[NodeLabel.PEST] = NodeLabel.PEST
    name: str
    scientific_name: str | None = None
    pest_type: str | None = None
    category: str | None = None

class Chemical(BaseNode):
    label: Literal[NodeLabel.CHEMICAL] = NodeLabel.CHEMICAL
    name: str
    trade_names: list[str] = Field(default_factory=list)
    chemical_type: str | None = None

class MoAGroup(BaseNode):
    label: Literal[NodeLabel.MOA_GROUP] = NodeLabel.MOA_GROUP
    group_code: str
    group_name: str | None = None

class Beneficial(BaseNode):
    label: Literal[NodeLabel.BENEFICIAL] = NodeLabel.BENEFICIAL
    name: str
    beneficial_type: str | None = None

class CropStage(BaseNode):
    label: Literal[NodeLabel.CROP_STAGE] = NodeLabel.CROP_STAGE
    name: str
    phase: str | None = None

class Threshold(BaseNode):
    label: Literal[NodeLabel.THRESHOLD] = NodeLabel.THRESHOLD
    value: str
    unit: str | None = None
    sampling_method: str | None = None

class Researcher(BaseNode):
    label: Literal[NodeLabel.RESEARCHER] = NodeLabel.RESEARCHER
    name: str
    organisation: str | None = None

class Organisation(BaseNode):
    label: Literal[NodeLabel.ORGANISATION] = NodeLabel.ORGANISATION
    name: str
    acronym: str | None = None

class Disease(BaseNode):
    label: Literal[NodeLabel.DISEASE] = NodeLabel.DISEASE
    name: str
    pathogen: str | None = None

class Variety(BaseNode):
    label: Literal[NodeLabel.VARIETY] = NodeLabel.VARIETY
    name: str
    company: str | None = None
    crop_type: str | None = None

class Region(BaseNode):
    label: Literal[NodeLabel.REGION] = NodeLabel.REGION
    name: str

class Weed(BaseNode):
    label: Literal[NodeLabel.WEED] = NodeLabel.WEED
    name: str
    scientific_name: str | None = None
    weed_type: str | None = None

class Trait(BaseNode):
    label: Literal[NodeLabel.TRAIT] = NodeLabel.TRAIT
    name: str
    description: str | None = None


# --- Relationship Models ---
class BaseRelationship(BaseModel):
    """Shared fields across graph relationship models."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: RelationshipType
    source_id: str
    target_id: str
    source_label: NodeLabel
    target_label: NodeLabel

class DefinedInRelationship(BaseRelationship):
    type: Literal[RelationshipType.DEFINED_IN] = RelationshipType.DEFINED_IN
    source_label: Literal[NodeLabel.TERM, NodeLabel.ACRONYM]
    target_label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT

class WrittenByRelationship(BaseRelationship):
    type: Literal[RelationshipType.WRITTEN_BY] = RelationshipType.WRITTEN_BY
    source_label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT
    target_label: Literal[NodeLabel.AUTHOR] = NodeLabel.AUTHOR


OntologyNode = Term | Acronym | Document | Author | Pest | Chemical | MoAGroup | Beneficial | CropStage | Threshold | Researcher | Organisation | Disease | Variety | Region | Weed | Trait
OntologyRelationship = BaseRelationship
