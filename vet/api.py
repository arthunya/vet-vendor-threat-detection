"""V.E.T. REST API (FastAPI).

Endpoints
  POST /screen                 body: {"name": ...} or {"entity_id": ...}
                               unknown names are registered then screened
  GET  /entity/{entity_id}     entity record
  GET  /runs/{run_id}/evidence full evidence chain for a screening run
  GET  /audit/export           append-only audit log (usage evidence)
  GET  /health                 liveness + record counts

Run:  uvicorn vet.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vet import db, engine

app = FastAPI(
    title="V.E.T. — Vendor Entity Threat Detection",
    version="0.1.0",
    description="AI-powered data fusion framework for supply chain security. "
                "Phase-1 proof of concept per Kanoklertwongse (2026).",
)


class ScreenRequest(BaseModel):
    entity_id: str | None = None
    name: str | None = None
    jurisdiction: str | None = None
    cik: str | None = None
    naics_code: str | None = None
    requested_by: str = "api"
    live_network: bool = True


@app.get("/health")
def health():
    conn = db.connect()
    counts = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
              for t in ("entities", "sanctions_records", "screening_runs", "audit_log")}
    conn.close()
    return {"status": "ok", "model_version": engine.model_version(), "counts": counts}


@app.post("/screen")
def screen(req: ScreenRequest):
    if not req.entity_id and not req.name:
        raise HTTPException(422, "provide entity_id or name")
    entity_id = req.entity_id
    if entity_id is None:
        conn = db.connect()
        entity_id = db.upsert_entity(
            conn, canonical_name=req.name, jurisdiction=req.jurisdiction,
            cik=req.cik, naics_code=req.naics_code,
            source_refs=[{"source": "api_submission", "fetched_at": db.now_iso()}])
        db.audit(conn, actor=req.requested_by, action="ENTITY_REGISTERED",
                 payload={"entity_id": entity_id, "name": req.name})
        conn.close()
    try:
        return engine.screen(entity_id, requested_by=req.requested_by,
                             live_network=req.live_network)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/entity/{entity_id}")
def get_entity(entity_id: str):
    conn = db.connect()
    row = conn.execute("SELECT * FROM entities WHERE entity_id = ?",
                       (entity_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "entity not found")
    d = dict(row)
    d["name_variants"] = json.loads(d["name_variants"])
    d["source_refs"] = json.loads(d["source_refs"])
    return d


@app.get("/runs/{run_id}/evidence")
def run_evidence(run_id: str):
    conn = db.connect()
    run = conn.execute("SELECT * FROM screening_runs WHERE run_id = ?",
                       (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise HTTPException(404, "run not found")
    signals = [dict(s) for s in conn.execute(
        "SELECT feature, raw_value, score, weight, evidence "
        "FROM risk_signals WHERE run_id = ?", (run_id,))]
    conn.close()
    for s in signals:
        s["raw_value"] = json.loads(s["raw_value"])
        s["evidence"] = json.loads(s["evidence"])
    return {"run": dict(run), "signals": signals}


@app.get("/audit/export")
def audit_export(limit: int = 1000):
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM audit_log ORDER BY log_id DESC LIMIT ?", (limit,))]
    conn.close()
    return {"entries": rows}
