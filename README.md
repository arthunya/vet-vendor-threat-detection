# V.E.T. — Vendor Entity Threat Detection

**An AI-Powered Data Fusion Framework for U.S. Supply Chain Security**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![ResearchGate DOI](https://img.shields.io/badge/DOI-10.13140%2FRG.2.2.33961.76641-blue)](https://doi.org/10.13140/RG.2.2.33961.76641)
[![Status: Active Development](https://img.shields.io/badge/Status-Active%20Development-green.svg)](#project-status)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Dashboard-orange.svg)](https://arthunya.github.io/vet-vendor-threat-detection/dashboard/VET_Dashboard.html)

Repository created April 2026 · actively maintained.

---

## Overview

V.E.T. (Vendor Entity Threat Detection) is an open-source AI framework designed to identify high-risk entities — including shell companies, sanctions-listed organizations, and adversarial front companies — embedded within U.S. commercial and government procurement supply chains.

This repository contains the runnable **Phase-1 implementation** of the V.E.T. data fusion architecture described in:

> Kanoklertwongse, A. (2026). *V.E.T. — Vendor Entity Threat Detection: An AI-Powered Data Fusion Framework for Supply Chain Security*. ResearchGate Working Paper. DOI: [10.13140/RG.2.2.33961.76641](https://doi.org/10.13140/RG.2.2.33961.76641)

---

## The Problem

Current U.S. vendor vetting methodologies share three critical failures:

1. **Manual and reactive** — periodic document review is easily circumvented by sophisticated adversaries
2. **Siloed data sources** — risk signals across corporate registries, sanctions databases, and logistics records are never analyzed together
3. **Binary outputs** — pass/fail classification provides no probabilistic nuance for procurement decision-makers

The [2020 SolarWinds compromise](https://www.cisa.gov/news-events/cybersecurity-advisories/aa20-352a) demonstrated the scale of vendor risk: approximately 18,000 organizations downloaded the compromised update, and nine U.S. federal agencies were confirmed breached.

**Policy alignment:** V.E.T. directly addresses requirements under [Executive Order 13873](https://www.federalregister.gov/documents/2019/05/17/2019-10538/securing-the-information-and-communications-technology-and-services-supply-chain) (ICT Supply Chain Security), [NIST SP 800-161 Rev. 1](https://csrc.nist.gov/publications/detail/sp/800-161/rev-1/final), and the [FinCEN Beneficial Ownership Information reporting framework](https://www.fincen.gov/boi) (90 FR 13688, March 26, 2025).

---

## Project Status

This is an active research project, not a one-time upload. Development continues alongside the accompanying White Paper:

| Component | Status |
|---|---|
| Data ingestion, entity graph, 5-feature deterministic risk engine | **Built & verified** (this repo) |
| REST API, audit log, evaluation harness, 10-test verification suite | **Built & verified** (this repo) |
| Interactive browser dashboard (`dashboard/VET_Dashboard.html`) | **Built — supplementary layer, under active refinement** |
| Trained ML ensemble (XGBoost + GraphSAGE) | **Phase 2 — not yet started** (White Paper §3.3, §4.2) |
| Expanded benchmark (500 entities incl. hard negatives) | **Phase 2 — planned** (tracked in `eval/`) |

## Honest Scope Statement

This repository is the **Phase-1 deterministic ensemble** (White Paper §3.3, §4.1, §4.4). What it is and is not:

- **Is:** a runnable end-to-end system — ingestion, entity graph, 5-feature risk engine, REST API, interactive dashboard, evaluation harness, append-only audit log.
- **Is:** validated on **benchmark v0: 33 real entities** with publicly citable ground truth (OFAC/BIS designations vs. major SEC registrants). Current result: precision 1.0 / recall 1.0 — expected on this sanity-tier benchmark, since direct list membership is near-deterministic. The scientifically meaningful test is benchmark v1 (500 entities incl. shell structures and near-name hard negatives), tracked in `eval/`.
- **Is not:** the trained ML ensemble (XGBoost + GraphSAGE). Training a classifier on a benchmark this small would overfit. The White Paper's Phase 1 plan (§4.1) includes an XGBoost baseline trained on a 5,000-entity benchmark; because benchmark v0 currently has 33 entities, this repository deliberately defers the trained ML layer from the original Phase 1 plan to Phase 2 and implements a deterministic weighted ensemble in its place.
- The financial-health module (`vet/features/financial_health.py`) was validated against live SEC EDGAR filings on June 30, 2026 — see White Paper §4.4 ("Financial Health Signal — Completed Validation") and the accompanying validation report for full methodology, including a deliberately disclosed false-positive case (§6.5).
- One record in the seed data is synthetic and loudly labeled as such (`DEMO Trading Partners LLC [SYNTHETIC TEST FIXTURE]`) — it exists only to unit-test hop-1 ownership propagation and is excluded from all metrics.

---

## Architecture

### Target architecture (full research vision — White Paper §3.3)

V.E.T.'s target design is a four-layer data fusion architecture:

```
Layer 1: Data Ingestion & Normalization
  Corporate registries, Sanctions (OFAC/BIS/CAATSA),
  FinCEN BOI, Logistics APIs, OSINT feeds
        |
Layer 2: Entity Resolution & Knowledge Graph
  Fuzzy name matching, Ownership chain traversal,
  Cross-jurisdictional entity deduplication
        |
Layer 3: Risk Feature Extraction
  200+ engineered features per entity
  Sanctions proximity, Geographic risk, Financial
  anomaly indicators, Network centrality metrics
        |
Layer 4: Ensemble Classifier & Risk Output
  XGBoost + GraphSAGE + Isolation Forest ensemble
  Output: LOW / MEDIUM / HIGH / CRITICAL risk tier
  + evidence chain for human review
```

**Target performance:** >85% precision on HIGH/CRITICAL risk tier classification (Phase 2, once the trained ensemble above is built — see Project Status).

### What is actually built and verified right now (Phase 1, this repo)

```
ingest (OFAC SDN, BIS EL, seed) -> SQLite/PostgreSQL entity graph
        |
  f1 sanctions_proximity   (exact/fuzzy/hop-1/hop-2)
  f2 financial_health      (SEC EDGAR equity/assets)
  f3 geographic_risk       (FATF lists)
  f4 entity_opacity        (ownership depth, LEI/CIK)
  f5 industry_mismatch     (NAICS x jurisdiction)
        |
  weighted ensemble -> tier + CRITICAL override -> evidence chain
        |
  FastAPI (/screen /runs/{id}/evidence /audit/export) + Dashboard
```

Production DDL: `schema/postgres_schema.sql`. The dev backend is SQLite with an identical table layout; the audit log is append-only at the DB layer (triggers in dev, revoked grants in production). The Layer 4 trained ensemble shown above has not yet been built — see Project Status.

---

## Repository Structure

This tree reflects the files that actually exist in this repository (not an aspirational structure):

```
vet-vendor-threat-detection/
├── README.md                      # This file
├── LICENSE                        # MIT License
├── requirements.txt               # Python dependencies
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions: pytest + eval on every push
│
├── vet/                           # Core package
│   ├── __init__.py
│   ├── engine.py                  # Phase-1 weighted deterministic ensemble
│   ├── api.py                     # FastAPI REST interface
│   ├── db.py                      # SQLite/PostgreSQL schema + append-only audit log
│   │
│   ├── features/                  # Risk feature modules (f1-f5)
│   │   ├── __init__.py
│   │   ├── sanctions_proximity.py # f1: exact/fuzzy/hop-1/hop-2 sanctions matching
│   │   ├── financial_health.py    # f2: SEC EDGAR XBRL equity/assets signal
│   │   └── context_signals.py     # f3-f5: geographic, opacity, industry mismatch
│   │
│   └── ingest/                    # Data ingestion pipelines
│       ├── __init__.py
│       ├── ofac_sdn.py            # Live OFAC SDN list loader
│       └── seed_data.py           # Offline hand-verified seed records
│
├── schema/
│   └── postgres_schema.sql        # Production DDL
│
├── tests/
│   └── test_vet.py                # 10-test verification suite (T1-T10)
│
├── eval/
│   ├── run_eval.py                # Recomputes precision/recall from scratch
│   └── results_latest.json        # Committed benchmark v0 results
│
├── scripts/
│   ├── build_company_db.py        # Builds the 1,261-company dashboard dataset
│   └── assemble_dashboard.py      # Assembles dashboard/VET_Dashboard.html
│
├── dashboard/
│   ├── VET_Dashboard.html         # Self-contained interactive dashboard (open directly)
│   ├── engine.js                  # JS port of the risk engine (9 Node tests)
│   ├── app.py                     # Streamlit alternative viewer
│   └── vet_dashboard_template.html # Pre-data-injection template
│
└── data_build/
    ├── vet_db.json                # 1,261-company dashboard database
    ├── sp500.csv                  # Source data: S&P 500 constituents
    └── nasdaq.csv                 # Source data: NASDAQ-listed companies
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/arthunya/vet-vendor-threat-detection.git
cd vet-vendor-threat-detection
pip install -r requirements.txt
```

### Run the verification suite

```bash
python -m vet.ingest.seed_data        # offline: hand-verified real records
python -m pytest tests/ -q            # 10 tests
```

```bash
# macOS / Linux
PYTHONPATH=. python eval/run_eval.py
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="."; python eval/run_eval.py
```

```cmd
:: Windows CMD
set PYTHONPATH=. && python eval/run_eval.py
```

### Run the API and score a real request

```bash
uvicorn vet.api:app --port 8000
```

```bash
curl -s -X POST http://127.0.0.1:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme International Trading Ltd", "jurisdiction": "SG"}'
```

Verified example response (captured from a live local run of this exact codebase):

```json
{
  "run_id": "552ab861-ae2c-43c4-aae0-2743e181cdc3",
  "entity_id": "2c10b4a1-99cb-4301-8332-16f9c7438bef",
  "canonical_name": "Acme International Trading Ltd",
  "risk_tier": "LOW",
  "composite_score": 0.0941,
  "critical_override": false,
  "model_version": "2b899be",
  "signals": [
    {"feature": "sanctions_proximity", "score": 0.0, "direct_hit": false,
     "evidence": {"source": "sanctions_records", "result": "no match at threshold >= 0.90"}},
    {"feature": "financial_health", "score": null,
     "evidence": {"source": "SEC_EDGAR", "result": "entity outside data coverage"}},
    {"feature": "geographic_risk", "score": 0.0,
     "evidence": {"source": "FATF", "category": "no listed jurisdiction exposure"}},
    {"feature": "entity_opacity", "score": 0.4,
     "evidence": {"source": "entity_graph", "note": "depth via ownership_edges BFS; identity via LEI/CIK presence"}},
    {"feature": "industry_mismatch", "score": 0.0,
     "evidence": {"source": "NAICS+FATF cross-reference", "result": "no rule triggered"}}
  ]
}
```

Every score returns a full evidence chain — no black-box output. Fields returning `score: null` mean the entity is outside that feature's data coverage and were excluded (not penalized) from the composite, per the out-of-coverage principle in White Paper §4.4.

Full endpoint reference: start the API and open `http://127.0.0.1:8000/docs` (auto-generated OpenAPI UI).

### Interactive Dashboard (supplementary, under active development)

`dashboard/VET_Dashboard.html` — a single self-contained file (open directly in any browser, no server needed; **or view it live via GitHub Pages** — see Live Demo below). This is a supplementary demonstration layer built on top of the verified Phase-1 engine, not a replacement for it:

- **1,261 real US companies** (S&P 500 + NASDAQ-listed small/mid caps, built from public datasets by `scripts/build_company_db.py`) and **68 real designated entities** (curated OFAC SDN / BIS Entity List subset).
- The screening step is **real computation, not simulation**: the JS port of the risk engine (`dashboard/engine.js`, verified against 9 Node test cases) runs fuzzy + affiliate-containment sanctions matching and the 5-domain weighted ensemble live in the browser. A full-database scan (~1,261 companies) completes in ~100-300 ms with zero false positives.
- Per-domain dashboard cards explain **why** a vendor is risky or clean, with verification links (OFAC search, BIS list, SEC EDGAR, OpenCorporates, adverse-media news search) and tier-specific business recommendations.
- Shell-company fraud patterns are demonstrated ONLY via clearly labeled `[SYNTHETIC DEMO]` profiles — real companies are never assigned fraud labels without public evidence.
- This dashboard is being actively iterated on; expect incremental commits refining coverage, UI, and evidence-chain presentation.

Rebuild: `python scripts/build_company_db.py && python scripts/assemble_dashboard.py`

### Live Demo

GitHub does not render HTML files inline. To view the dashboard without downloading:
- **[Open the live interactive dashboard →](https://arthunya.github.io/vet-vendor-threat-detection/dashboard/VET_Dashboard.html)** (hosted via GitHub Pages)

---

## Verify Independently

1. `python -m pytest tests/ -q` — all claims in the test docstring map to White Paper sections.
2. `PYTHONPATH=. python eval/run_eval.py` — recomputes precision/recall from scratch; compare with the committed `eval/results_latest.json`.
3. Pick any HIGH/CRITICAL result and follow `evidence.url` (or `evidence.source`) to the official OFAC/BIS/SEC source.
4. Every screening stores `model_version` = git commit hash: check out that commit and re-run to reproduce any historical score.

---

## Known Limitations (tracked)

- Buyback-driven negative equity fires the raw f2 signal (White Paper §6.5, Domino's case). The ensemble weighting contains it — verified by test T5 — and the Phase-2 remediation is a free-cash-flow gate.
- FATF lists in `context_signals.py` are a dated snapshot; refresh before any production run.
- Benchmark v0 has no hard negatives yet; v1 adds them.
- Dashboard sanctions subset (68 records) is curated for demonstration; the production ingester (`vet/ingest/ofac_sdn.py`) mirrors the full OFAC SDN list (~15,000+ records).

---

## Data Sources

V.E.T. integrates six primary data domains:

| Domain | Source | Access |
|--------|--------|--------|
| Sanctions lists | OFAC SDN, BIS Entity List, CAATSA, UN SC | Public |
| Corporate registries | OpenCorporates API, state registries, SEC EDGAR (CIK) | Public API |
| Beneficial ownership | FinCEN BOI (per 90 FR 13688, March 2025) | Restricted — Phase 2 |
| Financial health | SEC EDGAR XBRL CompanyFacts API | Public, no auth (**built & verified**) |
| Logistics/shipping | CBP import records, maritime APIs | Public + Commercial — Phase 2 |
| OSINT | Adverse media, domain registration | Public — Phase 2 |

FinCEN BOI access is currently restricted to authorized government agencies and financial institutions. V.E.T.'s Phase-1 implementation operates on publicly accessible data only.

---

## Regulatory Alignment

| Federal Mandate | V.E.T. Capability |
|----------------|-------------------|
| EO 13873 — ICT Supply Chain | AI-automated adversarial vendor detection |
| NIST SP 800-161 Rev. 1 | Continuous risk scoring + evidence chain |
| FAR 4.21 | Beneficial ownership cross-reference |
| FinCEN BOI Rule (90 FR 13688, March 2025) | BOI data integration in entity graph |
| CHIPS Act §9902 | Semiconductor supply chain screening |

---

## Research Paper

This implementation accompanies the following working paper:

**Kanoklertwongse, A. (2026).** V.E.T. — Vendor Entity Threat Detection: An AI-Powered Data Fusion Framework for Supply Chain Security. *ResearchGate Working Paper.*

- **DOI:** [10.13140/RG.2.2.33961.76641](https://doi.org/10.13140/RG.2.2.33961.76641)
- **License:** CC BY 4.0
- **Published:** April 9, 2026
- **SSRN:** https://ssrn.com/abstract=6667278
- **SSRN Abstract ID:** 6667278 (posted May 8, 2026)

---

## Author

**Arthunya Kanoklertwongse**
M.S. Computer Science (AI Concentration) — Westcliff University, San Francisco
MSc Financial Technology (Merit; partial merit scholarship) — University of the West of England, Bristol
14 years: Financial analysis · Internal audit · Cross-border counterparty coordination

**Background:** The V.E.T. framework draws on 14 years of practitioner experience in financial analysis, internal audit, and cross-border counterparty coordination — translated into a machine-learnable architecture through graduate-level AI research. The feature engineering design reflects analytical heuristics developed through years of professional experience in financial services and multinational enterprise operations.

---

## Contributing

Contributions welcome. Please open an issue before submitting a pull request.

Areas where contributions are especially needed:
- Benchmark v1 curation (hard negatives, shell-company structures)
- Phase 2 ML ensemble (XGBoost + GraphSAGE) implementation
- Additional data source connectors (international registries)
- Dashboard UI/coverage refinements

---

## License

MIT License — see [LICENSE](LICENSE) for details.

This project is intended for research and legitimate supply chain security purposes. Users are responsible for compliance with applicable laws regarding data access and use.

---

## Acknowledgments

This research was conducted as part of graduate studies in the M.S. Computer Science (AI Concentration) program at Westcliff University, San Francisco. The V.E.T. framework was initially developed as a course project in MIS 510 (IT Project Management), achieving a final grade of 99/100.
