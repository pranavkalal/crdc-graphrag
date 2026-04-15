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
    if key_name in st.secrets:
        return st.secrets[key_name]
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
    return GraphService(
        neo4j_client=client,
        gemini_api_key=get_secret("GEMINI_API_KEY"),
        gemini_model=get_secret("GEMINI_MODEL", "gemini-2.5-flash")
    )

driver = init_neo4j()
qa_service = init_gemini()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🌱 CRDC Cotton Knowledge Graph")
st.caption("Extracted from 5 core 2025 Cotton Industry Manuals using Gemini 2.5 Flash + LangChain + Neo4j")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview",
    "🔍 Relationship Verifier",
    "🕸️ Visual Explorer",
    "🤖 Ask the Graph"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Graph Statistics")

    with driver.session() as session:
        total_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Nodes", total_nodes)
    c2.metric("Total Relationships", total_rels)
    c3.metric("Source Documents", 5)
    c4.metric("Entity Types", 6)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Nodes by Label")
        with driver.session() as session:
            res = session.run("MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count ORDER BY Count DESC")
            df = pd.DataFrame([r.data() for r in res])
            df = df[~df['Label'].isin(['Chunk', '__Entity__', 'Document'])]
            st.dataframe(df, hide_index=True, use_container_width=True)

    with col2:
        st.subheader("Relationships by Type")
        with driver.session() as session:
            res = session.run("MATCH ()-[r]->() RETURN type(r) AS Type, count(r) AS Count ORDER BY Count DESC")
            df = pd.DataFrame([r.data() for r in res])
            df = df[~df['Type'].isin(['SIMILAR', 'PART_OF', 'NEXT_CHUNK', 'HAS_ENTITY', 'FIRST_CHUNK'])]
            st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("📄 Source Documents")
    st.markdown("""
    | # | Document | Entities Extracted |
    |---|---|---|
    | 1 | **Cotton Pest Management Guide 2025** | Pests, Chemicals, MoA Groups (9 control tables) |
    | 2 | **CPMG 2025 — Key Diseases Chapter** | 32 Diseases with pathogens & symptoms |
    | 3 | **IPM Guidelines + IPM Booklet 2024** | 18 Beneficial insects with PREDATES links |
    | 4 | **Defoliation Booklet 2024** | 8 Harvest aid chemicals |
    | 5 | **Tropical Cotton Guide 2025** | 6 region-specific diseases |
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: RELATIONSHIP VERIFIER — Preset queries for the client
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🔍 Relationship Verifier")
    st.markdown("Click any preset query below to verify the extracted relationships against the source manuals.")

    PRESETS = {
        "1. All Pests and their Chemical Controls": {
            "cypher": "MATCH (p:Pest)-[r:CONTROLLED_BY]->(c:Chemical) RETURN p.name AS Pest, c.name AS Chemical, r.beneficial_impact AS BeneficialImpact, r.resistance_status AS ResistanceStatus ORDER BY p.name, c.name",
            "description": "Shows every Pest→Chemical CONTROLLED_BY relationship (98 total). Cross-reference with CPMG 2025 Tables 7-18.",
            "expected": "98 rows"
        },
        "2. Chemicals by MoA Group": {
            "cypher": "MATCH (c:Chemical)-[r:BELONGS_TO]->(m:MoAGroup) RETURN c.name AS Chemical, m.group_code AS MoAGroup ORDER BY m.group_code, c.name",
            "description": "Chemical→MoAGroup BELONGS_TO relationships. Cross-reference with CPMG Table 5 and individual control tables.",
            "expected": "49 rows"
        },
        "3. Green Mirid Controls (Table 11)": {
            "cypher": "MATCH (p:Pest {name: 'Green mirid'})-[r:CONTROLLED_BY]->(c:Chemical) RETURN c.name AS Chemical, r.beneficial_impact AS Impact, r.resistance_status AS Resistance, r.max_applications AS MaxApps ORDER BY c.name",
            "description": "All 19 chemicals registered for Green Mirid control. Verify against CPMG 2025, Table 11, page 56.",
            "expected": "19 rows"
        },
        "4. Helicoverpa Controls (Table 8)": {
            "cypher": "MATCH (p:Pest {name: 'Helicoverpa'})-[r:CONTROLLED_BY]->(c:Chemical) RETURN c.name AS Chemical, r.beneficial_impact AS Impact, r.resistance_status AS Resistance ORDER BY c.name",
            "description": "All 22 chemicals for Helicoverpa. Verify against CPMG 2025, Table 8, pages 38-39.",
            "expected": "22 rows"
        },
        "5. Cotton Aphid Controls (Table 7)": {
            "cypher": "MATCH (p:Pest {name: 'Cotton aphid'})-[r:CONTROLLED_BY]->(c:Chemical) RETURN c.name AS Chemical, r.beneficial_impact AS Impact, r.resistance_status AS Resistance ORDER BY c.name",
            "description": "All 17 chemicals for Cotton Aphid. Verify against CPMG 2025, Table 7, pages 34-35.",
            "expected": "17 rows"
        },
        "6. Beneficial Insects → Pest Prey": {
            "cypher": "MATCH (b:Beneficial)-[r:PREDATES]->(p:Pest) RETURN b.name AS Beneficial, b.beneficial_type AS Type, p.name AS Prey ORDER BY b.name",
            "description": "All 26 PREDATES links between beneficial organisms and pests. Source: IPM Guidelines Section 3.3.",
            "expected": "26 rows"
        },
        "7. All Diseases with Pathogens": {
            "cypher": "MATCH (d:Disease)-[:AFFECTS]->(c:Crop) RETURN d.name AS Disease, d.pathogen AS Pathogen, d.symptoms AS Symptoms ORDER BY d.name",
            "description": "All 34 diseases with their causal pathogens. Verify against CPMG 2025, pages 112-127.",
            "expected": "34 rows"
        },
        "8. Harvest Aid Chemicals (Defoliants)": {
            "cypher": "MATCH (c:Chemical) WHERE c.chemical_type IN ['defoliant', 'boll opener', 'desiccant'] RETURN c.name AS Chemical, c.chemical_type AS Type, c.trade_names AS TradeNames, c.key_notes AS Notes ORDER BY c.chemical_type, c.name",
            "description": "All 8 harvest aid chemicals. Verify against Defoliation Booklet 2024, Table 2.",
            "expected": "8 rows"
        },
        "9. Low-Impact Chemicals for Aphid IPM": {
            "cypher": "MATCH (p:Pest {name: 'Cotton aphid'})-[r:CONTROLLED_BY]->(c:Chemical) WHERE r.beneficial_impact IN ['Very low', 'Low'] RETURN c.name AS Chemical, r.beneficial_impact AS Impact ORDER BY r.beneficial_impact",
            "description": "IPM-friendly aphid controls. These are chemicals a grower should prefer to conserve beneficials.",
            "expected": "~4-6 rows"
        },
        "10. Fusarium Wilt Detail": {
            "cypher": "MATCH (d:Disease) WHERE toLower(d.name) CONTAINS 'fusarium' RETURN d.name AS Disease, d.pathogen AS Pathogen, d.symptoms AS Symptoms, d.favoured_by AS FavouredBy, d.management AS Management",
            "description": "Detailed attributes for Fusarium wilt. Verify pathogen name and IDM tactics against CPMG p.117.",
            "expected": "1 row"
        },
    }

    selected = st.selectbox("Select a verification query:", list(PRESETS.keys()))

    preset = PRESETS[selected]
    st.info(f"**What this shows:** {preset['description']}")
    st.caption(f"Expected: {preset['expected']}")

    with st.expander("View Cypher Query"):
        st.code(preset['cypher'], language='cypher')

    if st.button("▶ Run Query", key="verify_btn"):
        with st.spinner("Querying Neo4j..."):
            with driver.session() as session:
                result = session.run(preset['cypher'])
                records = [r.data() for r in result]

        st.success(f"Returned **{len(records)}** records")
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, hide_index=True, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: VISUAL EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("🕸️ Interactive Graph Visualization")

    COLOR_MAP = {
        "Pest": "#e63946",
        "Chemical": "#2a9d8f",
        "MoAGroup": "#e9c46a",
        "Beneficial": "#457b9d",
        "Disease": "#f4a261",
        "Crop": "#264653",
    }

    viz_preset = st.selectbox("Choose a view:", [
        "Pests → Chemical Controls",
        "Beneficial Insects → Prey",
        "Diseases → Crop",
        "Harvest Aids",
        "Full Graph (all IPM entities)"
    ])

    viz_queries = {
        "Pests → Chemical Controls": "MATCH (n:Pest)-[r:CONTROLLED_BY]->(m:Chemical) RETURN n, r, m LIMIT 150",
        "Beneficial Insects → Prey": "MATCH (n:Beneficial)-[r:PREDATES]->(m:Pest) RETURN n, r, m LIMIT 100",
        "Diseases → Crop": "MATCH (n:Disease)-[r:AFFECTS]->(m:Crop) RETURN n, r, m LIMIT 100",
        "Harvest Aids": "MATCH (n:Chemical) WHERE n.chemical_type IN ['defoliant', 'boll opener', 'desiccant'] OPTIONAL MATCH (n)-[r:BELONGS_TO]->(m:MoAGroup) RETURN n, r, m LIMIT 100",
        "Full Graph (all IPM entities)": "MATCH (n)-[r]->(m) WHERE NOT 'Chunk' IN labels(n) AND NOT '__Entity__' IN labels(n) AND NOT 'Chunk' IN labels(m) AND NOT '__Entity__' IN labels(m) RETURN n, r, m LIMIT 200"
    }

    if st.button("Generate Visualization", key="viz_btn"):
        with st.spinner("Building network..."):
            net = Network(notebook=False, height="620px", width="100%", directed=True, bgcolor="#0e1117", font_color="#ffffff")
            net.force_atlas_2based(gravity=-60, central_gravity=0.01, spring_length=120)

            with driver.session() as session:
                result = session.run(viz_queries[viz_preset])
                for record in result:
                    n = record.get("n")
                    m = record.get("m")
                    r = record.get("r")

                    if n:
                        lbl = list(n.labels)[0] if n.labels else "Node"
                        name = n.get("name") or n.get("group_code") or "?"
                        color = COLOR_MAP.get(lbl, "#adb5bd")
                        net.add_node(n.element_id, label=name, title=f"{lbl}: {name}", color=color, size=20)

                    if m:
                        lbl = list(m.labels)[0] if m.labels else "Node"
                        name = m.get("name") or m.get("group_code") or "?"
                        color = COLOR_MAP.get(lbl, "#adb5bd")
                        net.add_node(m.element_id, label=name, title=f"{lbl}: {name}", color=color, size=20)

                    if r and n and m:
                        rel_type = r.type
                        title = rel_type
                        if r.get("beneficial_impact"):
                            title += f"\nImpact: {r['beneficial_impact']}"
                        net.add_edge(n.element_id, m.element_id, label=rel_type, title=title, color="#6c757d")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                net.save_graph(tmp.name)
                with open(tmp.name, 'r', encoding='utf-8') as f:
                    html = f.read()
                st.components.v1.html(html, height=650)

    st.markdown("**Legend:**")
    legend_cols = st.columns(len(COLOR_MAP))
    for col, (label, color) in zip(legend_cols, COLOR_MAP.items()):
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
        "What causes Fusarium wilt and how do I manage it?",
        "Which insecticides have the lowest impact on beneficials for aphid control?",
        "What harvest aid chemicals are available?",
    ]
    for ex in examples:
        st.caption(f"• {ex}")

    question = st.text_input("Your question:", placeholder="e.g. Which beneficial insects prey on Helicoverpa?")

    if st.button("Search Graph", key="qa_btn"):
        if question:
            with st.spinner("Generating Cypher and querying graph..."):
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(qa_service.query(question))

            st.success("Answer Generated")
            st.markdown(f"### Answer\n{result['answer']}")

            with st.expander("🔧 Under the hood"):
                st.markdown(f"**Explanation:** {result['explanation']}")
                st.code(result['cypher'], language='cypher')
                st.write(f"Returned **{result['record_count']}** records")
                if result['records']:
                    df = pd.DataFrame(result['records'][:20])
                    st.dataframe(df, hide_index=True, use_container_width=True)
