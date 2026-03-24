"""Pydantic models that define the pilot graph ontology."""

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeLabel(str, Enum):
    """Labels used for graph nodes in the pilot ontology."""

    TERM = "Term"
    ACRONYM = "Acronym"
    DOCUMENT = "Document"
    AUTHOR = "Author"


class RelationshipType(str, Enum):
    """Relationship types supported in the pilot ontology."""

    DEFINED_IN = "DEFINED_IN"
    WRITTEN_BY = "WRITTEN_BY"


class BaseNode(BaseModel):
    """Shared fields across ontology node models."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    label: NodeLabel


class Term(BaseNode):
    """A domain term defined within one or more source documents."""

    label: Literal[NodeLabel.TERM] = NodeLabel.TERM
    canonical_term: str
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)


class Acronym(BaseNode):
    """An acronym and its expanded form."""

    label: Literal[NodeLabel.ACRONYM] = NodeLabel.ACRONYM
    acronym: str
    expanded_form: str
    description: str | None = None


class Document(BaseNode):
    """A source document used by the pilot."""

    label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT
    document_id: str
    title: str
    source_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Author(BaseNode):
    """An author associated with one or more source documents."""

    label: Literal[NodeLabel.AUTHOR] = NodeLabel.AUTHOR
    name: str
    organization: str | None = None


class BaseRelationship(BaseModel):
    """Shared fields across graph relationship models."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: RelationshipType
    source_id: str
    target_id: str
    source_label: NodeLabel
    target_label: NodeLabel


class DefinedInRelationship(BaseRelationship):
    """Link a term or acronym to the document where it is defined."""

    type: Literal[RelationshipType.DEFINED_IN] = RelationshipType.DEFINED_IN
    source_label: Literal[NodeLabel.TERM, NodeLabel.ACRONYM]
    target_label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT


class WrittenByRelationship(BaseRelationship):
    """Link a document to one of its authors."""

    type: Literal[RelationshipType.WRITTEN_BY] = RelationshipType.WRITTEN_BY
    source_label: Literal[NodeLabel.DOCUMENT] = NodeLabel.DOCUMENT
    target_label: Literal[NodeLabel.AUTHOR] = NodeLabel.AUTHOR


OntologyNode = Term | Acronym | Document | Author
OntologyRelationship = DefinedInRelationship | WrittenByRelationship
