"""V.E.T. database layer.

Development/PoC backend: SQLite (zero-config, file-based).
Production backend: PostgreSQL 16 (see schema/postgres_schema.sql).
The table structure is kept 1:1 so migration is a connection-string change
plus type widening, not a rewrite.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "vet.db"

DDL = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id      TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    name_variants  TEXT NOT NULL DEFAULT '[]',   -- JSON array
    jurisdiction   TEXT,
    lei            TEXT,
    cik            TEXT,
    naics_code     TEXT,
    incorp_date    TEXT,
    source_refs    TEXT NOT NULL,                -- JSON array
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ownership_edges (
    edge_id    TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL REFERENCES entities(entity_id),
    owned_id   TEXT NOT NULL REFERENCES entities(entity_id),
    pct        REAL,
    edge_type  TEXT NOT NULL CHECK (edge_type IN
               ('beneficial_owner','shareholder','officer','shared_address')),
    source_ref TEXT NOT NULL,
    valid_from TEXT,
    valid_to   TEXT
);

CREATE TABLE IF NOT EXISTS sanctions_records (
    record_id    TEXT PRIMARY KEY,
    list_name    TEXT NOT NULL CHECK (list_name IN
                 ('OFAC_SDN','BIS_ENTITY_LIST','UN_CONSOLIDATED','CAATSA')),
    listed_name  TEXT NOT NULL,
    aliases      TEXT NOT NULL DEFAULT '[]',
    program      TEXT,
    list_version TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    raw_record   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_runs (
    run_id          TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    requested_by    TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    risk_tier       TEXT CHECK (risk_tier IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    composite_score REAL
);

CREATE TABLE IF NOT EXISTS risk_signals (
    signal_id TEXT PRIMARY KEY,
    run_id    TEXT NOT NULL REFERENCES screening_runs(run_id),
    feature   TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    score     REAL NOT NULL,
    weight    REAL NOT NULL,
    evidence  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    payload TEXT
);

-- Append-only enforcement for the audit log.
CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def audit(conn: sqlite3.Connection, actor: str, action: str, payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, payload) VALUES (?,?,?,?)",
        (now_iso(), actor, action, json.dumps(payload or {})),
    )
    conn.commit()


def upsert_entity(conn: sqlite3.Connection, *, canonical_name: str,
                  name_variants: list[str] | None = None, jurisdiction: str | None = None,
                  lei: str | None = None, cik: str | None = None,
                  naics_code: str | None = None, incorp_date: str | None = None,
                  source_refs: list[dict] | None = None) -> str:
    row = conn.execute(
        "SELECT entity_id FROM entities WHERE canonical_name = ?", (canonical_name,)
    ).fetchone()
    if row:
        return row["entity_id"]
    eid = str(uuid.uuid4())
    ts = now_iso()
    conn.execute(
        """INSERT INTO entities (entity_id, canonical_name, name_variants, jurisdiction,
           lei, cik, naics_code, incorp_date, source_refs, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, canonical_name, json.dumps(name_variants or []), jurisdiction,
         lei, cik, naics_code, incorp_date, json.dumps(source_refs or []), ts, ts),
    )
    conn.commit()
    return eid


def insert_sanctions_record(conn: sqlite3.Connection, *, list_name: str, listed_name: str,
                            aliases: list[str] | None = None, program: str | None = None,
                            list_version: str, source_url: str, raw_record: dict) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO sanctions_records
           (record_id, list_name, listed_name, aliases, program, list_version, source_url, raw_record)
           VALUES (?,?,?,?,?,?,?,?)""",
        (rid, list_name, listed_name, json.dumps(aliases or []), program,
         list_version, source_url, json.dumps(raw_record)),
    )
    conn.commit()
    return rid


def add_ownership_edge(conn: sqlite3.Connection, *, owner_id: str, owned_id: str,
                       edge_type: str, pct: float | None = None,
                       source_ref: dict | None = None) -> str:
    edge_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO ownership_edges (edge_id, owner_id, owned_id, pct, edge_type, source_ref)
           VALUES (?,?,?,?,?,?)""",
        (edge_id, owner_id, owned_id, pct, edge_type, json.dumps(source_ref or {})),
    )
    conn.commit()
    return edge_id
