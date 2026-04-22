import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
import pandas as pd
from pyvis.network import Network
import tempfile

from app.infrastructure.neo4j_client import Neo4jClient
from app.services.graph_service import GraphService

st.set_page_config(page_title="CRDC Knowledge Graph", layout="wide", page_icon="🌱")

load_dotenv()

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stMetric { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 16px; border-radius: 12px; }
    .stMetric label { color: #a8dadc !important; }
    .stMetric [data-testid="stMetricValue"] { color: #f1faee !important; font-size: 2rem !important; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


def get_secret(key_name: str, default: str | None = None) -> str | None:
    """Helper to fetch secrets: tries Streamlit Cloud secrets first, then local environment variables."""
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return os.environ.get(key_name, default)

@st.cache_resource
def init_neo4j():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        get_secret("NEO4J_URI"),
        auth=(get_secret("NEO4J_USERNAME"), get_secret("NEO4J_PASSWORD"))
    )

@st.cache_resource
def init_gemini():
    client = Neo4jClient(
        get_secret("NEO4J_URI"),
        get_secret("NEO4J_USERNAME"),
        get_secret("NEO4J_PASSWORD"),
        get_secret("NEO4J_DATABASE", "neo4j")
    )
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client.connect())
    svc = GraphService(
        neo4j_client=client,
        gemini_api_key=get_secret("GEMINI_API_KEY"),
        gemini_model=get_secret("GEMINI_MODEL", "gemini-2.5-flash")
    )
    return svc, loop

driver = init_neo4j()
qa_service, _qa_loop = init_gemini()

DB = get_secret("NEO4J_DATABASE", "neo4j")

def run_q(cypher: str) -> list[dict]:
    """Run a Cypher query and return records as dicts."""
    with driver.session(database=DB) as session:
        result = session.run(cypher)
        return [r.data() for r in result]


# ── Header ───────────────────────────────────────────────────────────────────
st.title("🌱 CRDC Cotton Knowledge Graph")
st.caption("Extracted from 2025 Cotton Industry Manuals using Gemini 2.5 Flash + LangChain + Neo4j Aura")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview",
    "🔍 Relationship Verifier",
    "🕸️ Visual Explorer",
    "🤖 Ask the Graph"
])

# ═══════════════════════════════════════════════════════════════════════════════
# COLOUR MAP — all 15 entity types
# ═══════════════════════════════════════════════════════════════════════════════
COLOR_MAP = {
    "Pest":       "#e63946",   # red
    "Chemical":   "#2a9d8f",   # teal
    "MoAGroup":   "#e9c46a",   # gold
    "Beneficial": "#457b9d",   # steel blue
    "Disease":    "#f4a261",   # orange
    "Crop":       "#264653",   # dark teal
    "Term":       "#8ecae6",   # light blue
    "Acronym":    "#219ebc",   # medium blue
    "Weed":       "#76c893",   # green
    "Variety":    "#d4a5a5",   # dusty rose
    "Region":     "#ffb703",   # amber
    "Trait":      "#fb8500",   # tangerine
    "CropStage":  "#b5838d",   # mauve
    "Threshold":  "#6d6875",   # grey-purple
    "Document":   "#adb5bd",   # grey
}

# Hidden labels — skip these in Overview tables
HIDDEN_LABELS = {"Chunk", "__Entity__", "Document"}
HIDDEN_RELS = {"SIMILAR", "PART_OF", "NEXT_CHUNK", "HAS_ENTITY", "FIRST_CHUNK"}


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW — dynamic from Neo4j
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Graph Statistics")

    total_nodes = run_q("MATCH (n) RETURN count(n) AS c")[0]["c"]
    total_rels = run_q("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    label_data = run_q("MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count ORDER BY Count DESC")
    rel_data = run_q("MATCH ()-[r]->() RETURN type(r) AS Type, count(r) AS Count ORDER BY Count DESC")
    entity_types = len([l for l in label_data if l["Label"] not in HIDDEN_LABELS])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Nodes", f"{total_nodes:,}")
    c2.metric("Total Relationships", f"{total_rels:,}")
    c3.metric("Entity Types", entity_types)
    c4.metric("Source Documents", "4 manuals")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Nodes by Label")
        df_labels = pd.DataFrame(label_data)
        df_labels = df_labels[~df_labels["Label"].isin(HIDDEN_LABELS)]
        st.bar_chart(df_labels.set_index("Label"), y="Count", color="#2a9d8f", horizontal=True)
        with st.expander("Raw Data"):
            st.dataframe(df_labels, hide_index=True, width="stretch")

    with col2:
        st.subheader("Relationships by Type")
        df_rels = pd.DataFrame(rel_data)
        df_rels = df_rels[~df_rels["Type"].isin(HIDDEN_RELS)]
        st.bar_chart(df_rels.set_index("Type"), y="Count", color="#e63946", horizontal=True)
        with st.expander("Raw Data"):
            st.dataframe(df_rels, hide_index=True, width="stretch")

    st.divider()
    st.subheader("📄 Source Documents & Extraction Coverage")
    st.markdown("""
    | # | Document | Entities Extracted |
    |---|---|---|
    | 1 | **Cotton Pest Management Guide (CPMG) 2025** | Pests, Chemicals, MoA Groups, Weeds, Herbicide Resistance |
    | 2 | **2025 Australian Cotton Production Manual (ACPM)** | Glossary (127 terms), Acronyms (61), Varieties, Traits, Regions, Crop Stages, Weeds |
    | 3 | **Farm Biosecurity Manual** | 11 Exotic Pest/Disease Threats with risk ratings |
    | 4 | **IPM Guidelines** | 18 Beneficials, 26 Pest Thresholds |
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: RELATIONSHIP VERIFIER — 18 preset queries
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🔍 Relationship Verifier")
    st.markdown("Click any preset query below to verify the extracted relationships against the source manuals.")

    PRESETS = {
        # ── Original IPM presets ──
        "1. All Pests and their Chemical Controls": {
            "cypher": "MATCH (p:Pest)-[r:CONTROLLED_BY]->(c:Chemical) RETURN p.name AS Pest, c.name AS Chemical, r.beneficial_impact AS BeneficialImpact, r.resistance_status AS ResistanceStatus ORDER BY p.name, c.name",
            "description": "Shows every Pest→Chemical CONTROLLED_BY relationship. Cross-reference with CPMG 2025 Tables 7-18.",
        },
        "2. Chemicals by MoA Group": {
            "cypher": "MATCH (c:Chemical)-[r:BELONGS_TO]->(m:MoAGroup) RETURN c.name AS Chemical, m.group_code AS MoAGroup ORDER BY m.group_code, c.name",
            "description": "Chemical→MoAGroup BELONGS_TO relationships. Cross-reference with CPMG Table 5.",
        },
        "3. Green Mirid Controls": {
            "cypher": "MATCH (p:Pest {name: 'Green mirid'})-[r:CONTROLLED_BY]->(c:Chemical) RETURN c.name AS Chemical, r.beneficial_impact AS Impact, r.resistance_status AS Resistance, r.max_applications AS MaxApps ORDER BY c.name",
            "description": "All chemicals registered for Green Mirid control. Verify against CPMG 2025, Table 11.",
        },
        "4. Helicoverpa Controls": {
            "cypher": "MATCH (p:Pest {name: 'Helicoverpa'})-[r:CONTROLLED_BY]->(c:Chemical) RETURN c.name AS Chemical, r.beneficial_impact AS Impact, r.resistance_status AS Resistance ORDER BY c.name",
            "description": "All chemicals for Helicoverpa. Verify against CPMG 2025, Table 8.",
        },
        "5. Beneficial Insects → Pest Prey": {
            "cypher": "MATCH (b:Beneficial)-[r:PREDATES]->(p:Pest) RETURN b.name AS Beneficial, b.beneficial_type AS Type, p.name AS Prey ORDER BY b.name",
            "description": "All PREDATES links between beneficial organisms and pests. Source: IPM Guidelines.",
        },
        "6. All Diseases with Pathogens": {
            "cypher": "MATCH (d:Disease) RETURN d.name AS Disease, d.pathogen AS Pathogen, d.symptoms AS Symptoms, d.biosecurity_risk AS BiosecurityRisk ORDER BY d.name",
            "description": "All diseases with their causal pathogens. Includes biosecurity risk ratings where applicable.",
        },
        "7. Harvest Aid Chemicals": {
            "cypher": "MATCH (c:Chemical) WHERE c.chemical_type IN ['defoliant', 'boll opener', 'desiccant'] RETURN c.name AS Chemical, c.chemical_type AS Type, c.trade_names AS TradeNames ORDER BY c.chemical_type, c.name",
            "description": "All harvest aid chemicals. Verify against Defoliation Booklet 2024.",
        },
        # ── NEW: Weed presets ──
        "8. All Weeds → Herbicide Controls": {
            "cypher": "MATCH (w:Weed)-[:CONTROLLED_BY]->(c:Chemical) RETURN w.name AS Weed, w.weed_type AS Type, collect(c.name) AS Herbicides ORDER BY w.name",
            "description": "Every Weed and the herbicides that control it. Source: CPMG 2025 Key Weeds section.",
        },
        "9. Glyphosate-Resistant Weeds": {
            "cypher": "MATCH (w:Weed)-[:HAS_RESISTANCE_TO]->(c:Chemical) WHERE toLower(c.name) CONTAINS 'glyphosate' RETURN w.name AS Weed, w.scientific_name AS ScientificName, w.first_resistance_year AS FirstDocumented ORDER BY w.first_resistance_year",
            "description": "All weeds with confirmed glyphosate resistance. Source: CPMG Table 25.",
        },
        "10. All Weed Resistances": {
            "cypher": "MATCH (w:Weed)-[:HAS_RESISTANCE_TO]->(c:Chemical) RETURN w.name AS Weed, c.name AS ResistantTo ORDER BY w.name, c.name",
            "description": "Every confirmed herbicide resistance relationship. Source: CPMG Tables 25-27.",
        },
        # ── NEW: Variety presets ──
        "11. Cotton Varieties → Traits": {
            "cypher": "MATCH (v:Variety)-[:HAS_TRAIT]->(t:Trait) RETURN v.name AS Variety, v.company AS Company, collect(t.name) AS Traits, v.f_rank AS FRank, v.v_rank AS VRank ORDER BY v.name",
            "description": "All cotton varieties and their genetic traits (Bollgard 3, XtendFlex, etc.). Source: ACPM Ch 7.",
        },
        "12. Varieties → Suited Regions": {
            "cypher": "MATCH (v:Variety)-[:SUITED_TO]->(r:Region) RETURN v.name AS Variety, collect(r.name) AS Regions ORDER BY v.name",
            "description": "Which varieties suit which growing regions. Source: ACPM Ch 7.",
        },
        # ── NEW: Biosecurity presets ──
        "13. Exotic Biosecurity Threats": {
            "cypher": "MATCH (n) WHERE n.biosecurity_risk IS NOT NULL RETURN labels(n)[0] AS Type, n.name AS Threat, n.biosecurity_risk AS RiskRating, n.pathogen AS Pathogen, n.spread_mechanism AS SpreadMechanism, n.found_in AS FoundIn ORDER BY CASE n.biosecurity_risk WHEN 'EXTREME' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END",
            "description": "All 11 exotic threats from the Biosecurity Manual with risk ratings (EXTREME/HIGH/MEDIUM).",
        },
        # ── NEW: Threshold presets ──
        "14. Pest Control Thresholds": {
            "cypher": "MATCH (p:Pest)-[:HAS_THRESHOLD]->(th:Threshold) RETURN p.name AS Pest, th.value AS Threshold, th.crop_phase AS CropPhase, th.sampling_method AS SamplingMethod ORDER BY p.name",
            "description": "All pest thresholds from IPM Guidelines — the numbers growers use to decide when to spray.",
        },
        # ── NEW: Crop stages ──
        "15. Crop Growth Stages (Sequence)": {
            "cypher": "MATCH (cs1:CropStage)-[:PRECEDES]->(cs2:CropStage) RETURN cs1.name AS Stage, cs2.name AS NextStage, cs1.phase AS Phase ORDER BY cs1.name",
            "description": "Sequential crop growth stages with PRECEDES links.",
        },
        # ── NEW: Glossary/Acronym presets ──
        "16. All Glossary Terms (127)": {
            "cypher": "MATCH (t:Term) RETURN t.canonical_term AS Term, t.definition AS Definition ORDER BY t.canonical_term",
            "description": "All 127 glossary terms from the ACPM 2025 Glossary.",
        },
        "17. All Acronyms (61)": {
            "cypher": "MATCH (a:Acronym) RETURN a.acronym AS Acronym, a.expanded_form AS ExpandedForm ORDER BY a.acronym",
            "description": "All 61 acronyms from the ACPM 2025.",
        },
        "18. Fleabane: Full Control & Resistance Profile": {
            "cypher": "MATCH (w:Weed) WHERE toLower(w.name) CONTAINS 'fleabane' OPTIONAL MATCH (w)-[:CONTROLLED_BY]->(ctrl:Chemical) OPTIONAL MATCH (w)-[:HAS_RESISTANCE_TO]->(res:Chemical) RETURN w.name AS Weed, collect(DISTINCT ctrl.name) AS ControlledBy, collect(DISTINCT res.name) AS ResistantTo",
            "description": "Complete herbicide profile for Fleabane: what controls it and what it's resistant to.",
        },
    }

    selected = st.selectbox("Select a verification query:", list(PRESETS.keys()))

    preset = PRESETS[selected]
    st.info(f"**What this shows:** {preset['description']}")

    with st.expander("View Cypher Query"):
        st.code(preset["cypher"], language="cypher")

    if st.button("▶ Run Query", key="verify_btn"):
        with st.spinner("Querying Neo4j..."):
            records = run_q(preset["cypher"])

        st.success(f"Returned **{len(records)}** records")
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, hide_index=True, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: VISUAL EXPLORER — 9 views
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("🕸️ Interactive Graph Visualization")

    viz_preset = st.selectbox("Choose a view:", [
        "Pests → Chemical Controls",
        "Beneficial Insects → Prey",
        "Diseases → Crop",
        "Weeds → Herbicide Controls",
        "Weeds → Herbicide Resistance",
        "Varieties → Traits & Regions",
        "Biosecurity Threats",
        "Pest Thresholds",
        "Full Graph (all entities)",
    ])

    viz_queries = {
        "Pests → Chemical Controls": "MATCH (n:Pest)-[r:CONTROLLED_BY]->(m:Chemical) RETURN n, r, m LIMIT 150",
        "Beneficial Insects → Prey": "MATCH (n:Beneficial)-[r:PREDATES]->(m:Pest) RETURN n, r, m LIMIT 100",
        "Diseases → Crop": "MATCH (n:Disease)-[r:AFFECTS]->(m:Crop) RETURN n, r, m LIMIT 100",
        "Weeds → Herbicide Controls": "MATCH (n:Weed)-[r:CONTROLLED_BY]->(m:Chemical) RETURN n, r, m LIMIT 200",
        "Weeds → Herbicide Resistance": "MATCH (n:Weed)-[r:HAS_RESISTANCE_TO]->(m:Chemical) RETURN n, r, m LIMIT 100",
        "Varieties → Traits & Regions": "MATCH (v:Variety)-[r]->(t) WHERE t:Trait OR t:Region RETURN v AS n, r, t AS m LIMIT 100",
        "Biosecurity Threats": "MATCH (n)-[r:AFFECTS]->(m:Crop) WHERE n.biosecurity_risk IS NOT NULL RETURN n, r, m LIMIT 50",
        "Pest Thresholds": "MATCH (n:Pest)-[r:HAS_THRESHOLD]->(m:Threshold) RETURN n, r, m LIMIT 100",
        "Full Graph (all entities)": (
            "MATCH (n)-[r]->(m) "
            "WHERE NOT 'Chunk' IN labels(n) AND NOT '__Entity__' IN labels(n) "
            "AND NOT 'Chunk' IN labels(m) AND NOT '__Entity__' IN labels(m) "
            "AND NOT 'Document' IN labels(n) AND NOT 'Document' IN labels(m) "
            "AND NOT 'Term' IN labels(n) AND NOT 'Term' IN labels(m) "
            "AND NOT 'Acronym' IN labels(n) AND NOT 'Acronym' IN labels(m) "
            "RETURN n, r, m LIMIT 300"
        ),
    }

    if st.button("Generate Visualization", key="viz_btn"):
        with st.spinner("Building network..."):
            net = Network(notebook=False, height="650px", width="100%", directed=True, bgcolor="#0e1117", font_color="#ffffff")
            net.force_atlas_2based(gravity=-60, central_gravity=0.01, spring_length=120)

            records_raw = []
            with driver.session(database=DB) as session:
                result = session.run(viz_queries[viz_preset])
                records_raw = list(result)

            for record in records_raw:
                n = record.get("n")
                m = record.get("m")
                r = record.get("r")

                if n:
                    lbl = list(n.labels)[0] if n.labels else "Node"
                    name = n.get("name") or n.get("group_code") or n.get("canonical_term") or n.get("acronym") or n.get("value", "?")
                    color = COLOR_MAP.get(lbl, "#adb5bd")
                    # Build tooltip
                    tooltip_parts = [f"<b>{lbl}: {name}</b>"]
                    for prop_key in ["scientific_name", "definition", "expanded_form", "weed_type", "biosecurity_risk",
                                     "crop_phase", "sampling_method", "pathogen", "symptoms", "f_rank", "v_rank"]:
                        val = n.get(prop_key)
                        if val:
                            tooltip_parts.append(f"{prop_key}: {val}")
                    tooltip = "<br>".join(tooltip_parts)
                    size = 25 if lbl in ("Pest", "Weed", "Variety", "Disease") else 18
                    net.add_node(n.element_id, label=str(name)[:30], title=tooltip, color=color, size=size)

                if m:
                    lbl = list(m.labels)[0] if m.labels else "Node"
                    name = m.get("name") or m.get("group_code") or m.get("canonical_term") or m.get("acronym") or m.get("value", "?")
                    color = COLOR_MAP.get(lbl, "#adb5bd")
                    tooltip_parts = [f"<b>{lbl}: {name}</b>"]
                    for prop_key in ["scientific_name", "definition", "expanded_form", "weed_type", "biosecurity_risk",
                                     "crop_phase", "sampling_method", "pathogen", "symptoms", "f_rank", "v_rank"]:
                        val = m.get(prop_key)
                        if val:
                            tooltip_parts.append(f"{prop_key}: {val}")
                    tooltip = "<br>".join(tooltip_parts)
                    size = 25 if lbl in ("Pest", "Weed", "Variety", "Disease") else 18
                    net.add_node(m.element_id, label=str(name)[:30], title=tooltip, color=color, size=size)

                if r and n and m:
                    rel_type = r.type
                    title = rel_type
                    if r.get("beneficial_impact"):
                        title += f"\nImpact: {r['beneficial_impact']}"
                    if r.get("resistance_status"):
                        title += f"\nResistance: {r['resistance_status']}"
                    edge_color = "#e63946" if rel_type == "HAS_RESISTANCE_TO" else "#6c757d"
                    net.add_edge(n.element_id, m.element_id, label=rel_type, title=title, color=edge_color)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                net.save_graph(tmp.name)
                with open(tmp.name, "r", encoding="utf-8") as f:
                    html = f.read()
                st.components.v1.html(html, height=680)

    # Legend
    st.markdown("**Legend:**")
    # Show legend in rows of 5
    legend_items = [(label, color) for label, color in COLOR_MAP.items() if label not in {"Document"}]
    for i in range(0, len(legend_items), 5):
        row = legend_items[i : i + 5]
        cols = st.columns(len(row))
        for col, (label, color) in zip(cols, row):
            col.markdown(f'<span style="color:{color};font-size:24px;">●</span> {label}', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: ASK THE GRAPH (GraphQATool)
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("🤖 Ask the Graph (GraphQATool)")
    st.markdown("Natural Language → Gemini Cypher Generation → Neo4j → Synthesised Answer")

    st.markdown("**Try these example questions:**")
    examples = [
        "What chemicals can I use to control Green Mirids?",
        "Which beneficial insects prey on Helicoverpa?",
        "What does IPM stand for?",
        "What herbicides control fleabane?",
        "What cotton varieties are available and what traits do they have?",
        "What exotic pest threats have a HIGH biosecurity risk?",
        "What is the threshold for controlling Helicoverpa?",
        "What causes Fusarium wilt and how do I manage it?",
        "Which weeds are resistant to glyphosate?",
        "What harvest aid chemicals are available?",
        "What is the definition of 'cut-out'?",
    ]
    for ex in examples:
        st.caption(f"• {ex}")

    question = st.text_input("Your question:", placeholder="e.g. Which weeds are resistant to glyphosate?")

    if st.button("Search Graph", key="qa_btn"):
        if question:
            with st.spinner("Generating Cypher and querying graph..."):
                result = _qa_loop.run_until_complete(qa_service.query(question))

            st.success("Answer Generated")
            st.markdown(f"### Answer\n{result['answer']}")

            with st.expander("🔧 Under the hood"):
                st.markdown(f"**Explanation:** {result['explanation']}")
                st.code(result["cypher"], language="cypher")
                st.write(f"Returned **{result['record_count']}** records")
                if result["records"]:
                    df = pd.DataFrame(result["records"][:20])
                    st.dataframe(df, hide_index=True, width="stretch")
