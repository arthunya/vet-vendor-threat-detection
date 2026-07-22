# V.E.T. — Vendor Entity Threat Detection

**An AI-Powered Data Fusion Framework for U.S. Supply Chain Security**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![ResearchGate DOI](https://img.shields.io/badge/DOI-10.13140%2FRG.2.2.33961.76641-blue)](https://doi.org/10.13140/RG.2.2.33961.76641)
[![Status: Active Development](https://img.shields.io/badge/Status-Active%20Development-green.svg)](#project-status)

Repository created April 2026 · actively maintained.

---

## Overview

V.E.T. (Vendor Entity Threat Detection) is an open-source AI framework designed
to identify high-risk entities — including shell companies, sanctions-listed
organizations, and adversarial front companies — embedded within U.S.
commercial and government procurement supply chains.

This repository is the runnable **Phase-1 implementation** of the framework
described in:

> Kanoklertwongse, A. (2026). *V.E.T. — Vendor Entity Threat Detection: An
> AI-Powered Data Fusion Framework for Supply Chain Security*. ResearchGate
> Working Paper. DOI: [10.13140/RG.2.2.33961.76641](https://doi.org/10.13140/RG.2.2.33961.76641)

V.E.T. screens vendor entities against fused public data — OFAC SDN, BIS
Entity List, SEC EDGAR financials, FATF jurisdiction lists, and corporate
ownership structure — and produces a four-tier risk classification
(LOW / MEDIUM / HIGH / CRITICAL) with a full evidence chain: every score
traces back to a specific public source record.

## Project Status

This is an active research project, not a one-time upload. Development
continues alongside the accompanying White Paper:

| Component | Status |
|---|---|
| Data ingestion, entity graph, 5-feature deterministic risk engine | **Built & verified** (this repo) |
| REST API, audit log, evaluation harness, 8-test verification suite | **Built & verified** (this repo) |
| Interactive browser dashboard (`dashboard/VET_Dashboard.html`) | **Built — supplementary layer, under active refinement** |
| Trained ML ensemble (XGBoost + GraphSAGE) | **Phase 2 — not yet started** (White Paper §3.3, §4.2) |
| Expanded benchmark (500 entities incl. hard negatives) | **Phase 2 — planned** (tracked in `eval/`) |

## Honest Scope Statement

This repository is the **Phase-1 deterministic ensemble** (White Paper §3.3,
§4.1, §4.4). What it is and is not:

- **Is:** a runnable end-to-end system — ingestion, entity graph, 5-feature
  risk engine, REST API, interactive dashboard, evaluation harness,
  append-only audit log.
- **Is:** validated on **benchmark v0: 33 real entities** with publicly
  citable ground truth (OFAC/BIS designations vs. major SEC registrants).
  Current result: precision 1.0 / recall 1.0 — expected on this sanity-tier
  benchmark, since direct list membership is near-deterministic. The
  scientifically meaningful test is benchmark v1 (500 entities incl. shell
  structures and near-name hard negatives), tracked in `eval/`.
- **Is not:** the trained ML ensemble (XGBoost + GraphSAGE). Training a
  classifier on a benchmark this small would overfit; the ML layer is
  Phase 2, exactly as scoped in the paper.
- The financial-health module (`vet/features/financial_health.py`) was
  independently validated against live SEC EDGAR filings on June 30, 2026 —
  see White Paper §4.4 ("Financial Health Signal — Completed Validation")
  and Exhibit A-2c for full methodology, including a deliberately disclosed
  false-positive case (§6.5).
- One record in the seed data is synthetic and loudly labeled as such
  (`DEMO Trading Partners LLC [SYNTHETIC TEST FIXTURE]`) — it exists only to
  unit-test hop-1 ownership propagation and is excluded from all metrics.

## Quickstart

```bash
pip install -r requirements.txt
python -m vet.ingest.seed_data        # offline: hand-verified real records
# python -m vet.ingest.ofac_sdn       # online: full live OFAC SDN (~15k+)
python -m pytest tests/ -q            # 8 tests
PYTHONPATH=. python eval/run_eval.py  # writes eval/results_latest.json
uvicorn vet.api:app --port 8000       # REST API -> /docs for OpenAPI UI
```

## Interactive Dashboard (supplementary, under active development)

`dashboard/VET_Dashboard.html` — a single self-contained file (open in any
browser, no server needed). This is a **supplementary demonstration layer**
built on top of the verified Phase-1 engine, not a replacement for it:

- **1,261 real US companies** (S&P 500 + NASDAQ-listed small/mid caps, built
  from public datasets by `scripts/build_company_db.py`) and **68 real
  designated entities** (curated OFAC SDN / BIS Entity List subset).
- The screening step is **real computation, not simulation**: the JS port of
  the risk engine (`dashboard/engine.js`, verified against 9 Node test cases)
  runs fuzzy + affiliate-containment sanctions matching and the 5-domain
  weighted ensemble live in the browser. A full-database scan (~1,261
  companies) completes in ~100–300 ms with zero false positives.
- Per-domain dashboard cards explain **why** a vendor is risky or clean, with
  verification links (OFAC search, BIS list, SEC EDGAR, OpenCorporates,
  adverse-media news search) and tier-specific business recommendations.
- Shell-company fraud patterns are demonstrated ONLY via clearly labeled
  `[SYNTHETIC DEMO]` profiles — real companies are never assigned fraud
  labels without public evidence.
- This dashboard is being actively iterated on; expect incremental commits
  refining coverage, UI, and evidence-chain presentation.

Rebuild: `python scripts/build_company_db.py && python scripts/assemble_dashboard.py`

## Verify Independently

1. `python -m pytest tests/ -q` — all claims in the test docstring map to
   White Paper sections.
2. `PYTHONPATH=. python eval/run_eval.py` — recomputes precision/recall from
   scratch; compare with the committed `eval/results_latest.json`.
3. Pick any HIGH/CRITICAL result and follow `evidence.url` to the official
   OFAC/BIS source.
4. Every screening stores `model_version` = git commit hash: check out that
   commit and re-run to reproduce any historical score.

## Architecture

```
ingest (OFAC SDN · BIS EL · seed) ─► SQLite/PostgreSQL entity graph
                                        │
            ┌───────────────────────────┴────────────────────────────┐
            │  f1 sanctions_proximity   (exact/fuzzy/hop-1/hop-2)    │
            │  f2 financial_health      (SEC EDGAR equity/assets)    │
            │  f3 geographic_risk       (FATF lists)                 │
            │  f4 entity_opacity        (ownership depth, LEI/CIK)   │
            │  f5 industry_mismatch     (NAICS × jurisdiction)       │
            └───────────────┬────────────────────────────────────────┘
                            ▼
        weighted ensemble ─► tier + CRITICAL override ─► evidence chain
                            ▼
        FastAPI (/screen /runs/{id}/evidence /audit/export) · Dashboard
```

Production DDL: `schema/postgres_schema.sql`. The dev backend is SQLite with
an identical table layout; the audit log is append-only at the DB layer
(triggers in dev, revoked grants in production).

Target (Phase 2) architecture — the trained ML ensemble described in White
Paper §3.3 (XGBoost + GraphSAGE + Isolation Forest) — has not yet been built;
see Project Status above.

## Known Limitations (tracked)

- Buyback-driven negative equity fires the raw f2 signal (White Paper §6.5,
  Domino's case). The ensemble weighting contains it — verified by test T5 —
  and the Phase-2 remediation is a free-cash-flow gate.
- FATF lists in `context_signals.py` are a dated snapshot; refresh before any
  production run.
- Benchmark v0 has no hard negatives yet; v1 adds them.
- Dashboard sanctions subset (68 records) is curated for demonstration; the
  production ingester (`vet/ingest/ofac_sdn.py`) mirrors the full OFAC SDN
  list (~15,000+ records).

## Data Sources

| Domain | Source | Access |
|---|---|---|
| Sanctions lists | OFAC SDN, BIS Entity List | Public |
| Corporate registries | State registries, SEC EDGAR (CIK) | Public API |
| Financial health | SEC EDGAR XBRL CompanyFacts API | Public, no auth |
| Geographic risk | FATF jurisdiction lists | Public |
| Beneficial ownership (target) | FinCEN BOI (per 90 FR 13688) | Restricted — Phase 2 |

## Research Paper

This implementation accompanies:

**Kanoklertwongse, A. (2026).** V.E.T. — Vendor Entity Threat Detection: An
AI-Powered Data Fusion Framework for Supply Chain Security. *ResearchGate
Working Paper.*

- **DOI:** [10.13140/RG.2.2.33961.76641](https://doi.org/10.13140/RG.2.2.33961.76641)
- **License:** CC BY 4.0
- **Published:** April 9, 2026
- **SSRN:** <https://ssrn.com/abstract=6667278>

## Author

**Arthunya Kanoklertwongse**
M.S. Computer Science (AI Concentration) — Westcliff University, San Francisco
MSc Financial Technology (Merit) — University of the West of England, Bristol
14 years: financial analysis · vendor risk management · enterprise operations

## Contributing

Contributions welcome. Please open an issue before submitting a pull request.

Areas where contributions are especially needed:

- Benchmark v1 curation (hard negatives, shell-company structures)
- Phase 2 ML ensemble (XGBoost + GraphSAGE) implementation
- Additional data source connectors (international registries)
- Dashboard UI/coverage refinements

## License

MIT License — see [LICENSE](LICENSE) for details.

This project is intended for research and legitimate supply chain security
purposes. Users are responsible for compliance with applicable laws
regarding data access and use.

## Acknowledgments

This research was conducted as part of graduate studies in the M.S. Computer
Science (AI Concentration) program at Westcliff University, San Francisco.
The V.E.T. framework was initially developed as a course project in MIS 510
(IT Project Management).
