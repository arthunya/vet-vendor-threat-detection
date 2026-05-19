# V.E.T. — Vendor Entity Threat Detection

**An AI-Powered Data Fusion Framework for U.S. Supply Chain Security**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![ResearchGate DOI](https://img.shields.io/badge/DOI-10.13140%2FRG.2.2.33961.76641-blue)](https://doi.org/10.13140/RG.2.2.33961.76641)
[![Status: Active Development](https://img.shields.io/badge/Status-Active%20Development-green.svg)]()

---

## Overview

V.E.T. (Vendor Entity Threat Detection) is an open-source AI framework designed to identify high-risk entities — including shell companies, sanctions-listed organizations, and adversarial front companies — embedded within U.S. commercial and government procurement supply chains.

This repository contains the **proof-of-concept implementation** of the V.E.T. data fusion architecture described in:

> Kanoklertwongse, A. (2026). *V.E.T. — Vendor Entity Threat Detection: An AI-Powered Data Fusion Framework for Supply Chain Security*. ResearchGate Working Paper. DOI: [10.13140/RG.2.2.33961.76641](https://doi.org/10.13140/RG.2.2.33961.76641)

---

## The Problem

Current U.S. vendor vetting methodologies share three critical failures:

1. **Manual and reactive** — periodic document review is easily circumvented by sophisticated adversaries
2. **Siloed data sources** — risk signals across corporate registries, sanctions databases, and logistics records are never analyzed together
3. **Binary outputs** — pass/fail classification provides no probabilistic nuance for procurement decision-makers

The [2020 SolarWinds compromise](https://www.cisa.gov/news-events/alerts/2020/12/17/active-exploitation-solarwinds-software) demonstrated that a single compromised vendor relationship can cascade into breaches affecting hundreds of federal agencies.

**Policy alignment:** V.E.T. directly addresses requirements under [Executive Order 13873](https://www.federalregister.gov/documents/2019/05/17/2019-10538/securing-the-information-and-communications-technology-and-services-supply-chain) (ICT Supply Chain Security), [NIST SP 800-161 Rev. 1](https://csrc.nist.gov/publications/detail/sp/800-161/rev-1/final), and the [FinCEN Beneficial Ownership Rule](https://www.fincen.gov/boi) (31 C.F.R. §1010.380, effective January 2024).

---

## Architecture

V.E.T. uses a four-layer data fusion architecture:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Data Ingestion & Normalization                │
│  Corporate registries · Sanctions (OFAC/BIS/CAATSA)    │
│  FinCEN BOI · Logistics APIs · OSINT feeds              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Layer 2: Entity Resolution & Knowledge Graph           │
│  Fuzzy name matching · Ownership chain traversal        │
│  Cross-jurisdictional entity deduplication              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Layer 3: Risk Feature Extraction                       │
│  200+ engineered features per entity                    │
│  Sanctions proximity · Geographic risk · Financial      │
│  anomaly indicators · Network centrality metrics        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Layer 4: Ensemble Classifier & Risk Output             │
│  XGBoost + GraphSAGE + Isolation Forest ensemble        │
│  Output: LOW / MEDIUM / HIGH / CRITICAL risk tier       │
│  + evidence chain for human review                      │
└─────────────────────────────────────────────────────────┘
```

**Target performance:** >85% precision on HIGH/CRITICAL risk tier classification.

---

## Repository Structure

```
vet-vendor-threat-detection/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── requirements.txt             # Python dependencies
├── setup.py                     # Package setup
│
├── vet/                         # Core package
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   │
│   ├── ingestion/               # Layer 1: Data ingestion
│   │   ├── __init__.py
│   │   ├── sanctions_loader.py  # OFAC, BIS Entity List, CAATSA
│   │   ├── registry_loader.py   # Corporate registry data
│   │   ├── boi_loader.py        # FinCEN BOI data connector
│   │   └── osint_loader.py      # Open-source intelligence feeds
│   │
│   ├── resolution/              # Layer 2: Entity resolution
│   │   ├── __init__.py
│   │   ├── entity_resolver.py   # Fuzzy matching & deduplication
│   │   └── graph_builder.py     # Knowledge graph construction
│   │
│   ├── features/                # Layer 3: Feature engineering
│   │   ├── __init__.py
│   │   ├── sanctions_features.py
│   │   ├── financial_features.py
│   │   └── network_features.py
│   │
│   ├── models/                  # Layer 4: Risk classification
│   │   ├── __init__.py
│   │   ├── ensemble.py          # XGBoost + GNN ensemble
│   │   ├── anomaly_detector.py  # Isolation Forest
│   │   └── risk_scorer.py       # Final risk tier output
│   │
│   └── api/                     # REST API interface
│       ├── __init__.py
│       └── endpoints.py         # FastAPI endpoints
│
├── data/                        # Sample data (public sources only)
│   ├── sample_entities.csv      # Anonymized test entities
│   └── sanctions_snapshot/      # Public OFAC SDN list sample
│
├── notebooks/                   # Jupyter exploration notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_entity_resolution_demo.ipynb
│   └── 03_risk_scoring_demo.ipynb
│
├── tests/                       # Unit tests
│   ├── test_sanctions_loader.py
│   ├── test_entity_resolver.py
│   └── test_risk_scorer.py
│
└── docs/                        # Documentation
    ├── architecture.md
    ├── data_sources.md
    └── policy_alignment.md
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/arthunya/vet-vendor-threat-detection.git
cd vet-vendor-threat-detection
pip install -r requirements.txt
```

### Basic Usage

```python
from vet import VETScorer

# Initialize the scorer
scorer = VETScorer()

# Score a vendor entity by name and country
result = scorer.score_entity(
    entity_name="Acme International Trading Ltd",
    country="SG",
    industry="technology"
)

print(result)
# {
#   "entity": "Acme International Trading Ltd",
#   "risk_tier": "MEDIUM",
#   "risk_score": 0.42,
#   "evidence": {
#     "sanctions_proximity": 0.1,
#     "ownership_depth_score": 0.6,
#     "geographic_risk_index": 0.4,
#     "financial_anomaly": 0.2
#   },
#   "recommendation": "Enhanced due diligence recommended"
# }
```

### Run Demo Notebook

```bash
jupyter notebook notebooks/02_entity_resolution_demo.ipynb
```

---

## Data Sources

V.E.T. integrates six primary data domains:

| Domain | Source | Access |
|--------|--------|--------|
| Sanctions lists | OFAC SDN, BIS Entity List, CAATSA, UN SC | Public |
| Corporate registries | OpenCorporates API, state registries | Public API |
| Beneficial ownership | FinCEN BOI (post-Jan 2024) | Restricted* |
| Financial patterns | Commercial financial health APIs | Commercial |
| Logistics/shipping | CBP import records, maritime APIs | Public + Commercial |
| OSINT | Adverse media, domain registration | Public |

*FinCEN BOI access is currently restricted to authorized government agencies and financial institutions. V.E.T.'s Phase 1 proof-of-concept operates on publicly accessible data only.

---

## Regulatory Alignment

| Federal Mandate | V.E.T. Capability |
|----------------|-------------------|
| EO 13873 — ICT Supply Chain | AI-automated adversarial vendor detection |
| NIST SP 800-161 Rev. 1 | Continuous risk scoring + evidence chain |
| FAR 4.21 | Beneficial ownership cross-reference |
| FinCEN BOI Rule (2024) | BOI data integration in entity graph |
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
MSc Financial Technology (Merit, academic merit scholarship) — University of the West of England, Bristol
14 years: Financial analysis · KYC/AML compliance · Enterprise operations

**Background:** The V.E.T. framework draws on 14 years of practitioner experience in financial crime detection and KYC/AML compliance — translated into a machine-learnable architecture through graduate-level AI research. The feature engineering design reflects analytical heuristics developed through years of manual financial due diligence at YLG Bullion Group (Singapore/Malaysia) and ASUSTeK Computer (Thailand).

---

## Contributing

Contributions welcome. Please open an issue before submitting a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where contributions are especially needed:
- Additional data source connectors (international registries)
- GNN implementation improvements
- Benchmark dataset curation methodology
- API documentation

---

## License

MIT License — see [LICENSE](LICENSE) for details.

This project is intended for research and legitimate supply chain security purposes. Users are responsible for compliance with applicable laws regarding data access and use.

---

## Acknowledgments

This research was conducted as part of graduate studies in the M.S. Computer Science (AI Concentration) program at Westcliff University, San Francisco. The V.E.T. framework was initially developed as a course project in MIS 510 (IT Project Management), achieving a final grade of 99/100.
