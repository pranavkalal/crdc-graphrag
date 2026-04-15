"""Data access layer for Neo4j IPM graph."""

from app.infrastructure.neo4j_client import Neo4jClient
from app.models.ontology import Pest, Chemical, MoAGroup


class GraphRepository:
    """Repository mapping domain objects to Neo4j Cypher queries."""

    def __init__(self, neo4j_client: Neo4jClient):
        self._db = neo4j_client

    async def ensure_constraints(self) -> None:
        """Create required uniqueness constraints."""
        queries = [
            "CREATE CONSTRAINT pest_name IF NOT EXISTS FOR (p:Pest) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT chemical_name IF NOT EXISTS FOR (c:Chemical) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT moa_code IF NOT EXISTS FOR (m:MoAGroup) REQUIRE m.group_code IS UNIQUE",
        ]
        for query in queries:
            await self._db.run_query(query)

    async def merge_pest(self, pest: Pest) -> None:
        """Idempotent upsert of a Pest node."""
        query = """
        MERGE (p:Pest {name: $name})
        SET p.scientific_name = $scientific_name,
            p.pest_type = $pest_type,
            p.category = $category
        """
        await self._db.run_query(query, pest.model_dump())

    async def merge_chemical(self, chemical: Chemical) -> None:
        """Idempotent upsert of a Chemical node."""
        query = """
        MERGE (c:Chemical {name: $name})
        SET c.trade_names = $trade_names,
            c.chemical_type = $chemical_type
        """
        await self._db.run_query(query, chemical.model_dump())

    async def merge_moa_group(self, moa: MoAGroup) -> None:
        """Idempotent upsert of a Mode of Action Group node."""
        query = """
        MERGE (m:MoAGroup {group_code: $group_code})
        SET m.group_name = $group_name
        """
        await self._db.run_query(query, moa.model_dump())

    async def merge_controlled_by(
        self,
        pest_name: str,
        chemical_name: str,
        resistance_status: str | None = None,
        beneficial_impact: str | None = None,
        max_applications: str | None = None,
        source: str | None = None
    ) -> None:
        """Link a Pest to a Chemical via CONTROLLED_BY."""
        query = """
        MATCH (p:Pest {name: $pest_name})
        MATCH (c:Chemical {name: $chemical_name})
        MERGE (p)-[r:CONTROLLED_BY]->(c)
        SET r.resistance_status = $resistance_status,
            r.beneficial_impact = $beneficial_impact,
            r.max_applications = $max_applications,
            r.source = $source
        """
        await self._db.run_query(query, {
            "pest_name": pest_name,
            "chemical_name": chemical_name,
            "resistance_status": resistance_status,
            "beneficial_impact": beneficial_impact,
            "max_applications": max_applications,
            "source": source
        })

    async def merge_belongs_to_moa(self, chemical_name: str, group_code: str) -> None:
        """Link a Chemical to its MoAGroup."""
        query = """
        MATCH (c:Chemical {name: $chemical_name})
        MATCH (m:MoAGroup {group_code: $group_code})
        MERGE (c)-[:BELONGS_TO]->(m)
        """
        await self._db.run_query(query, {"chemical_name": chemical_name, "group_code": group_code})

    # ── Disease ─────────────────────────────────────────────────────────────

    async def merge_disease(self, name: str, pathogen: str | None = None,
                            symptoms: str | None = None,
                            favoured_by: str | None = None,
                            management: str | None = None,
                            source: str | None = None) -> None:
        """Idempotent upsert of a Disease node."""
        query = """
        MERGE (d:Disease {name: $name})
        SET d.pathogen = $pathogen,
            d.symptoms = $symptoms,
            d.favoured_by = $favoured_by,
            d.management = $management,
            d.source = $source
        """
        await self._db.run_query(query, {
            "name": name, "pathogen": pathogen, "symptoms": symptoms,
            "favoured_by": favoured_by, "management": management, "source": source
        })

    async def merge_affects_crop(self, disease_name: str, crop: str = "cotton") -> None:
        """Link a Disease to the crop it affects."""
        query = """
        MERGE (c:Crop {name: $crop})
        WITH c
        MATCH (d:Disease {name: $disease_name})
        MERGE (d)-[:AFFECTS]->(c)
        """
        await self._db.run_query(query, {"disease_name": disease_name, "crop": crop})

    # ── Beneficial ──────────────────────────────────────────────────────────

    async def merge_beneficial(self, name: str, scientific_name: str | None = None,
                               beneficial_type: str | None = None,
                               source: str | None = None) -> None:
        """Idempotent upsert of a Beneficial node."""
        query = """
        MERGE (b:Beneficial {name: $name})
        SET b.scientific_name = $scientific_name,
            b.beneficial_type = $beneficial_type,
            b.source = $source
        """
        await self._db.run_query(query, {
            "name": name, "scientific_name": scientific_name,
            "beneficial_type": beneficial_type, "source": source
        })

    async def merge_predates(self, beneficial_name: str, pest_name: str) -> None:
        """Link a Beneficial to a Pest via PREDATES."""
        query = """
        MATCH (b:Beneficial {name: $beneficial_name})
        MATCH (p:Pest {name: $pest_name})
        MERGE (b)-[:PREDATES]->(p)
        """
        await self._db.run_query(query, {
            "beneficial_name": beneficial_name, "pest_name": pest_name
        })

    # ── Defoliant (Chemical with specific type) ─────────────────────────────

    async def merge_defoliant(self, name: str, product_type: str,
                              trade_names: list[str] | None = None,
                              key_notes: str | None = None,
                              source: str | None = None) -> None:
        """Idempotent upsert of a harvest aid Chemical node."""
        query = """
        MERGE (c:Chemical {name: $name})
        SET c.chemical_type = $product_type,
            c.trade_names = $trade_names,
            c.key_notes = $key_notes,
            c.source = $source
        """
        await self._db.run_query(query, {
            "name": name, "product_type": product_type,
            "trade_names": trade_names or [], "key_notes": key_notes, "source": source
        })

    # ── Stats ───────────────────────────────────────────────────────────────

    async def get_graph_stats(self) -> dict[str, int]:
        """Return counts of nodes and relationships."""
        node_query = "MATCH (n) RETURN count(n) as count"
        rel_query = "MATCH ()-[r]->() RETURN count(r) as count"
        
        nodes = await self._db.run_query(node_query)
        rels = await self._db.run_query(rel_query)
        
        return {
            "nodes": nodes[0]["count"],
            "relationships": rels[0]["count"]
        }

    async def get_label_counts(self) -> list[dict]:
        """Return node counts by label for reporting."""
        query = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
        return await self._db.run_query(query)

