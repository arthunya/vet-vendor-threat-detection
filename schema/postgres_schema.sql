-- V.E.T. — Vendor Entity Threat Detection
-- Production PostgreSQL 16 schema (reference DDL).
-- Development/PoC uses an equivalent SQLite schema (vet/db.py).

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE entities (
    entity_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    name_variants  TEXT[] NOT NULL DEFAULT '{}',
    jurisdiction   CHAR(2),                 -- ISO 3166-1 alpha-2
    lei            CHAR(20),                -- GLEIF LEI, if any
    cik            TEXT,                    -- SEC CIK, if any
    naics_code     TEXT,
    incorp_date    DATE,
    source_refs    JSONB NOT NULL,          -- [{source, source_id, url, fetched_at}]
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_entities_name_trgm
    ON entities USING gin (canonical_name gin_trgm_ops);

CREATE TABLE ownership_edges (
    edge_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID NOT NULL REFERENCES entities(entity_id),
    owned_id    UUID NOT NULL REFERENCES entities(entity_id),
    pct         NUMERIC(5,2),
    edge_type   TEXT NOT NULL CHECK (edge_type IN
                ('beneficial_owner','shareholder','officer','shared_address')),
    source_ref  JSONB NOT NULL,
    valid_from  DATE,
    valid_to    DATE
);
CREATE INDEX idx_edges_owner ON ownership_edges(owner_id);
CREATE INDEX idx_edges_owned ON ownership_edges(owned_id);

CREATE TABLE sanctions_records (
    record_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_name    TEXT NOT NULL CHECK (list_name IN
                 ('OFAC_SDN','BIS_ENTITY_LIST','UN_CONSOLIDATED','CAATSA')),
    listed_name  TEXT NOT NULL,
    aliases      TEXT[] NOT NULL DEFAULT '{}',
    program      TEXT,
    list_version DATE NOT NULL,             -- version of the source list
    source_url   TEXT NOT NULL,             -- evidence-chain requirement
    raw_record   JSONB NOT NULL
);
CREATE INDEX idx_sanctions_name_trgm
    ON sanctions_records USING gin (listed_name gin_trgm_ops);

CREATE TABLE screening_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    requested_by    TEXT NOT NULL,
    model_version   TEXT NOT NULL,          -- git commit hash of the engine
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    risk_tier       TEXT CHECK (risk_tier IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    composite_score NUMERIC(6,4)
);

CREATE TABLE risk_signals (
    signal_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID NOT NULL REFERENCES screening_runs(run_id),
    feature     TEXT NOT NULL,
    raw_value   JSONB NOT NULL,
    score       NUMERIC(6,4) NOT NULL,
    weight      NUMERIC(5,3) NOT NULL,
    evidence    JSONB NOT NULL              -- {source, record_id, matched_text, url}
);
CREATE INDEX idx_signals_run ON risk_signals(run_id);

-- Append-only audit log: application role gets INSERT/SELECT only.
CREATE TABLE audit_log (
    log_id  BIGSERIAL PRIMARY KEY,
    ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    payload JSONB
);
-- REVOKE UPDATE, DELETE ON audit_log FROM vet_app_role;
