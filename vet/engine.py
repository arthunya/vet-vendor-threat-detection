"""V.E.T. risk engine — Phase-1 weighted deterministic ensemble.

Design decisions (documented for scientific review):
1. Deterministic weighted ensemble, not a trained classifier. With a benchmark
   in the hundreds of records, a trained XGBoost model would overfit and be
   scientifically indefensible; a calibrated rule ensemble yields measurable,
   reproducible precision. The Working Paper's Phase 1 plan (§4.1) includes an
   XGBoost baseline; this implementation defers the trained ML ensemble
   (XGBoost + GraphSAGE, §3.3 / §4.2) to Phase 2 until a larger benchmark exists.
2. Features returning score=None (no data coverage) are EXCLUDED and the
   remaining weights renormalized — an entity is never penalized or cleared
   on data that does not exist (Working Paper §4.4 out-of-coverage principle).
3. Hard override: a direct sanctions-list match is CRITICAL regardless of the
   composite — no weighting scheme may dilute a designated entity.
4. model_version = git commit hash: every screening run is reproducible.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

from vet import db
from vet.features import context_signals, financial_health, sanctions_proximity

FEATURE_WEIGHTS = {
    "sanctions_proximity": 0.35,
    "financial_health":    0.15,
    "geographic_risk":     0.15,
    "entity_opacity":      0.20,
    "industry_mismatch":   0.15,
}

TIERS = [(0.60, "CRITICAL"), (0.40, "HIGH"), (0.20, "MEDIUM"), (0.0, "LOW")]


def model_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent, text=True).strip()
    except Exception:
        return "untracked"


def tier_from(score: float) -> str:
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "LOW"


def screen(entity_id: str, requested_by: str = "api",
           live_network: bool = True) -> dict:
    conn = db.connect()
    ent = conn.execute("SELECT * FROM entities WHERE entity_id = ?",
                       (entity_id,)).fetchone()
    if ent is None:
        conn.close()
        raise KeyError(f"entity {entity_id} not found")

    variants = json.loads(ent["name_variants"])
    owner_juris = [r["jurisdiction"] or "" for r in conn.execute(
        "SELECT e.jurisdiction FROM ownership_edges oe "
        "JOIN entities e ON e.entity_id = oe.owner_id WHERE oe.owned_id = ?",
        (entity_id,))]

    signals = [
        sanctions_proximity.compute(conn, entity_id, ent["canonical_name"], variants),
        financial_health.compute(ent["cik"], live=live_network),
        context_signals.geographic_risk(ent["jurisdiction"], owner_juris),
        context_signals.entity_opacity(conn, entity_id, ent["lei"], ent["cik"]),
        context_signals.industry_mismatch(ent["naics_code"], ent["jurisdiction"]),
    ]

    # Weighted composite with renormalization over covered features only.
    covered = [s for s in signals if s["score"] is not None]
    total_w = sum(FEATURE_WEIGHTS[s["feature"]] for s in covered)
    composite = sum(s["score"] * FEATURE_WEIGHTS[s["feature"]] for s in covered) / total_w

    direct_hit = any(s.get("direct_hit") for s in signals)
    risk_tier = "CRITICAL" if direct_hit else tier_from(composite)

    # Persist run + full evidence chain.
    run_id, mv, ts = str(uuid.uuid4()), model_version(), db.now_iso()
    conn.execute(
        "INSERT INTO screening_runs (run_id, entity_id, requested_by, model_version,"
        " started_at, completed_at, risk_tier, composite_score) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, entity_id, requested_by, mv, ts, db.now_iso(),
         risk_tier, round(composite, 4)))
    for s in signals:
        conn.execute(
            "INSERT INTO risk_signals (signal_id, run_id, feature, raw_value, score,"
            " weight, evidence) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), run_id, s["feature"], json.dumps(s["raw_value"]),
             -1.0 if s["score"] is None else s["score"],
             FEATURE_WEIGHTS[s["feature"]], json.dumps(s["evidence"])))
    conn.commit()
    db.audit(conn, actor=requested_by, action="SCREENING_RUN",
             payload={"run_id": run_id, "entity_id": entity_id,
                      "risk_tier": risk_tier, "model_version": mv})
    conn.close()

    return {
        "run_id": run_id,
        "entity_id": entity_id,
        "canonical_name": ent["canonical_name"],
        "risk_tier": risk_tier,
        "composite_score": round(composite, 4),
        "critical_override": direct_hit,
        "model_version": mv,
        "signals": signals,
    }
