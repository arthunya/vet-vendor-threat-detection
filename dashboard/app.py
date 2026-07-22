"""V.E.T. screening dashboard (Streamlit).

Run:  pip install streamlit && streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from vet import db, engine  # noqa: E402

st.set_page_config(page_title="V.E.T. — Vendor Entity Threat Detection",
                   layout="wide")

TIER_BADGE = {"LOW": "🟢 LOW", "MEDIUM": "🟡 MEDIUM",
              "HIGH": "🟠 HIGH", "CRITICAL": "🔴 CRITICAL"}

st.title("V.E.T. — Vendor Entity Threat Detection")
st.caption("Phase-1 proof of concept · every score traces to a public source record")

tab_screen, tab_history, tab_audit = st.tabs(
    ["Screen a vendor", "Screening history", "Audit trail"])

with tab_screen:
    conn = db.connect()
    names = [r["canonical_name"] for r in
             conn.execute("SELECT canonical_name FROM entities ORDER BY canonical_name")]
    conn.close()

    col1, col2 = st.columns([2, 1])
    with col1:
        choice = st.selectbox("Registered entities", names)
        new_name = st.text_input("…or screen a new vendor by name")
    with col2:
        juris = st.text_input("Jurisdiction (ISO-2)", value="US")
        live = st.checkbox("Query SEC EDGAR live", value=True)

    if st.button("Run screening", type="primary"):
        conn = db.connect()
        if new_name.strip():
            eid = db.upsert_entity(conn, canonical_name=new_name.strip(),
                                   jurisdiction=juris or None,
                                   source_refs=[{"source": "dashboard"}])
        else:
            eid = conn.execute("SELECT entity_id FROM entities WHERE canonical_name=?",
                               (choice,)).fetchone()["entity_id"]
        conn.close()
        result = engine.screen(eid, requested_by="dashboard", live_network=live)

        st.subheader(f"{result['canonical_name']} — {TIER_BADGE[result['risk_tier']]}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Composite score", f"{result['composite_score']:.4f}")
        m2.metric("Critical override", str(result["critical_override"]))
        m3.metric("Model version", result["model_version"])

        st.markdown("#### Evidence chain")
        for s in result["signals"]:
            shown = "n/a (no coverage)" if s["score"] is None else f"{s['score']:.4f}"
            with st.expander(f"{s['feature']} — score {shown}"):
                st.json({"raw_value": s["raw_value"], "evidence": s["evidence"]})

with tab_history:
    conn = db.connect()
    rows = conn.execute(
        "SELECT r.started_at, e.canonical_name, r.risk_tier, r.composite_score, "
        "r.model_version, r.requested_by FROM screening_runs r "
        "JOIN entities e ON e.entity_id = r.entity_id "
        "ORDER BY r.started_at DESC LIMIT 200").fetchall()
    conn.close()
    st.dataframe([dict(r) for r in rows], use_container_width=True)

with tab_audit:
    conn = db.connect()
    rows = conn.execute("SELECT ts, actor, action, payload FROM audit_log "
                        "ORDER BY log_id DESC LIMIT 300").fetchall()
    conn.close()
    st.caption("Append-only log — UPDATE/DELETE rejected at the database layer.")
    st.dataframe([{**dict(r), "payload": json.loads(r["payload"] or "{}")}
                  for r in rows], use_container_width=True)
