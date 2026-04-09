"""
V.E.T. Configuration Management
Centralizes all configurable parameters for the data fusion pipeline.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VETConfig:
    """
    Central configuration for the V.E.T. pipeline.

    All thresholds and parameters are based on the risk-scoring
    methodology described in the V.E.T. technical white paper
    (DOI: 10.13140/RG.2.2.33961.76641).
    """

    # ── Risk tier thresholds ──────────────────────────────────────────
    # Calibrated to achieve >85% precision on HIGH/CRITICAL tier
    # per the target performance specification in the white paper.
    threshold_low: float = 0.25
    threshold_medium: float = 0.50
    threshold_high: float = 0.75
    # Scores above threshold_high are classified as CRITICAL

    # ── Ensemble model weights ────────────────────────────────────────
    # XGBoost: primary model for structured tabular features
    # GNN: captures risk propagation through corporate ownership graphs
    # Isolation Forest: anomaly detection for profile inconsistencies
    weight_xgboost: float = 0.50
    weight_gnn: float = 0.35
    weight_isolation_forest: float = 0.15

    # ── Feature engineering parameters ───────────────────────────────
    # Ownership depth: how many levels of beneficial ownership to traverse
    max_ownership_depth: int = 5

    # Sanctions proximity: flag entities within N hops of a designated entity
    sanctions_proximity_hops: int = 2

    # Geographic risk: high-risk jurisdictions per FATF grey/black list
    high_risk_jurisdictions: List[str] = field(default_factory=lambda: [
        "IR", "KP", "SY", "CU", "BY", "RU", "MM",  # OFAC primary
        "YE", "LY", "SD", "VE", "ZW",               # OFAC secondary
        "PK", "TR", "AE",                            # FATF grey list (illustrative)
    ])

    # ── Data source configuration ─────────────────────────────────────
    ofac_sdn_url: str = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    bis_entity_list_url: str = "https://www.bis.doc.gov/index.php/policy-guidance/lists-of-parties-of-concern"
    opencorporates_api_base: str = "https://api.opencorporates.com/v0.4"

    # ── API configuration ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_rate_limit_per_minute: int = 60

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_audit_trail: bool = True  # Required for federal procurement contexts

    # ── Phase 1 constraints ───────────────────────────────────────────
    # Phase 1 (proof-of-concept) operates on public data sources only.
    # FinCEN BOI access requires authorized government/financial institution
    # partnership — see white paper Section 4.2 for Phase 2 plan.
    phase1_public_data_only: bool = True

    @classmethod
    def from_env(cls) -> "VETConfig":
        """Load configuration from environment variables."""
        return cls(
            threshold_high=float(os.getenv("VET_THRESHOLD_HIGH", "0.75")),
            max_ownership_depth=int(os.getenv("VET_MAX_OWNERSHIP_DEPTH", "5")),
            log_level=os.getenv("VET_LOG_LEVEL", "INFO"),
        )
