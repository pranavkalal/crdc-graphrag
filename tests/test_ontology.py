import pytest
from pydantic import ValidationError

from app.models.ontology import (
    Acronym,
    Author,
    DefinedInRelationship,
    Document,
    NodeLabel,
    RelationshipType,
    Term,
    WrittenByRelationship,
)


def test_ontology_models_accept_valid_data() -> None:
    term = Term(canonical_term="boll weevil", definition="A cotton pest")
    acronym = Acronym(acronym="GIN", expanded_form="ginning")
    document = Document(
        document_id="doc-001",
        title="Cotton Handling Manual",
        source_path="data/raw/cotton-manual.pdf",
    )
    author = Author(name="CRDC")

    defined_in = DefinedInRelationship(
        source_id=term.id,
        target_id=document.id,
        source_label=NodeLabel.TERM,
    )
    written_by = WrittenByRelationship(source_id=document.id, target_id=author.id)

    assert term.label is NodeLabel.TERM
    assert acronym.label is NodeLabel.ACRONYM
    assert document.label is NodeLabel.DOCUMENT
    assert author.label is NodeLabel.AUTHOR
    assert defined_in.type is RelationshipType.DEFINED_IN
    assert written_by.type is RelationshipType.WRITTEN_BY


def test_ontology_models_reject_invalid_relationship_types() -> None:
    with pytest.raises(ValidationError):
        DefinedInRelationship(
            type=RelationshipType.WRITTEN_BY,
            source_id="term-1",
            target_id="doc-1",
            source_label=NodeLabel.TERM,
        )


def test_ontology_models_require_required_fields() -> None:
    with pytest.raises(ValidationError):
        Term()
