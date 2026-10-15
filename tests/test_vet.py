"""V.E.T. test suite.

Covers the claims the Working Paper makes:
  T1  direct sanctions match -> CRITICAL override (engine §3.3)
  T2  fuzzy alias match still detected ("Huawei Technologies Ltd" variant)
  T3  hop-1 ownership propagation flags the synthetic shell fixture
  T4  clean US registrant scores LOW
  T5  Domino's (§6.5 buyback negative-equity) is NOT classified HIGH/CRITICAL
      by the ensemble — financial FP contained by weighting
  T6  out-of-coverage financial data returns None, never a fake score
  T7  audit_log is append-only (UPDATE/DELETE rejected)
  T8  API contract: /screen, /runs/{id}/evidence round-trip with evidence
  T9  affiliate-style name variant is still flagged for human review
  T10 affiliate containment produces no false positive on clean names
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from vet import db, engine
from vet.api import app
from vet.features import financial_health
from vet.ingest import seed_data


@pytest.fixture(scope="session", autouse=True)
def seeded():
    seed_data.load()


def _eid(name: str) -> str:
    conn = db.connect()
    row = conn.execute("SELECT entity_id FROM entities WHERE canonical_name = ?",
                       (name,)).fetchone()
    conn.close()
    assert row, f"{name} missing"
    return row["entity_id"]


def test_t1_direct_match_critical():
    r = engine.screen(_eid("Kalashnikov Concern"), live_network=False)
    assert r["risk_tier"] == "CRITICAL"
    assert r["critical_override"] is True
    sanc = next(s for s in r["signals"] if s["feature"] == "sanctions_proximity")
    assert sanc["evidence"]["source"] == "OFAC_SDN"


def test_t2_fuzzy_variant_detected():
    conn = db.connect()
    eid = db.upsert_entity(conn, canonical_name="Huawei Technologies Ltd",
                           jurisdiction="CN", source_refs=[{"source": "test"}])
    conn.close()
    r = engine.screen(eid, live_network=False)
    sanc = next(s for s in r["signals"] if s["feature"] == "sanctions_proximity")
    assert sanc["score"] >= 0.85
    assert r["risk_tier"] in ("HIGH", "CRITICAL")


def test_t3_hop1_propagation():
    r = engine.screen(_eid("DEMO Trading Partners LLC [SYNTHETIC TEST FIXTURE]"),
                      live_network=False)
    sanc = next(s for s in r["signals"] if s["feature"] == "sanctions_proximity")
    assert sanc["raw_value"]["network"] == pytest.approx(0.7, abs=0.01)
    assert "owner:Kalashnikov Concern" in sanc["evidence"]["path"]
    assert r["risk_tier"] in ("HIGH", "CRITICAL")


def test_t4_clean_registrant_low():
    r = engine.screen(_eid("Microsoft Corporation"), live_network=False)
    assert r["risk_tier"] == "LOW"


def test_t5_dominos_fp_contained():
    r = engine.screen(_eid("Domino's Pizza, Inc."), live_network=False)
    fin = next(s for s in r["signals"] if s["feature"] == "financial_health")
    assert fin["score"] == 0.8  # the raw §6.5 signal fires as documented...
    assert r["risk_tier"] not in ("HIGH", "CRITICAL")  # ...ensemble contains it


def test_t6_out_of_coverage_none():
    res = financial_health.compute(None, live=False)
    assert res["score"] is None
    res2 = financial_health.compute("0009999999", live=False)
    assert res2["score"] is None


def test_t7_audit_append_only():
    conn = db.connect()
    db.audit(conn, actor="test", action="PROBE")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_log SET action='tampered' WHERE action='PROBE'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_log WHERE action='PROBE'")
    conn.close()


def test_t8_api_roundtrip():
    client = TestClient(app)
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["counts"]["sanctions_records"] > 0

    r = client.post("/screen", json={"name": "Mahan Air", "jurisdiction": "IR",
                                     "live_network": False}).json()
    assert r["risk_tier"] == "CRITICAL"

    ev = client.get(f"/runs/{r['run_id']}/evidence").json()
    feats = {s["feature"] for s in ev["signals"]}
    assert feats == {"sanctions_proximity", "financial_health", "geographic_risk",
                     "entity_opacity", "industry_mismatch"}
    sanc = next(s for s in ev["signals"] if s["feature"] == "sanctions_proximity")
    assert "url" in sanc["evidence"]  # evidence chain traces to source


def test_t9_affiliate_containment_flagged():
    """Regression for live finding 2026-07-06: subsidiary-style name variant
    'Huawei Technologies (Thailand) Ltd' previously scored LOW because the
    geographic qualifier depressed token_sort_ratio below threshold."""
    conn = db.connect()
    eid = db.upsert_entity(conn, canonical_name="Huawei Technologies (Thailand) Ltd",
                           jurisdiction="TH", source_refs=[{"source": "test"}])
    conn.close()
    r = engine.screen(eid, live_network=False)
    sanc = next(s for s in r["signals"] if s["feature"] == "sanctions_proximity")
    assert sanc["score"] >= 0.85
    assert r["risk_tier"] in ("MEDIUM", "HIGH", "CRITICAL")  # human-review path


def test_t10_containment_no_false_positive_on_clean_names():
    r = engine.screen(_eid("Apple Inc."), live_network=False)
    sanc = next(s for s in r["signals"] if s["feature"] == "sanctions_proximity")
    assert sanc["score"] == 0.0
