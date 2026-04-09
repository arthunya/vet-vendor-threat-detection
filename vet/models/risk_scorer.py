"""
V.E.T. Layer 4: Risk Scorer — Main Interface

The RiskScorer is the primary interface for the V.E.T. system.
It orchestrates all four layers of the data fusion pipeline and
produces a final probabilistic risk tier with an evidence chain
for human review.

Risk Tiers:
    LOW      — Standard procurement process
    MEDIUM   — Enhanced due diligence recommended
    HIGH     — Escalation to compliance team required
    CRITICAL — Procurement hold pending investigation

Target performance: >85% precision on HIGH/CRITICAL tier
(per White Paper DOI: 10.13140/RG.2.2.33961.76641, Section 3.3)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..config import VETConfig
from ..ingestion.sanctions_loader import SanctionsLoader
from ..resolution.entity_resolver import EntityResolver, EntityNode

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """
    Complete risk assessment output for a single vendor entity.

    Designed to support human-in-the-loop review workflows:
    all HIGH and CRITICAL assessments include an evidence chain
    that procurement officers can review before making final
    vendor decisions.
    """

    # Entity identification
    entity_name: str
    country: Optional[str]
    industry: Optional[str]

    # Risk output
    risk_tier: str           # LOW / MEDIUM / HIGH / CRITICAL
    risk_score: float        # 0.0 - 1.0 composite score
    confidence: float        # Model confidence in the assessment

    # Component scores (feature transparency)
    component_scores: Dict[str, float] = field(default_factory=dict)

    # Evidence chain for human review
    evidence: List[Dict] = field(default_factory=list)

    # Recommendation
    recommendation: str = ""
    requires_human_review: bool = False

    # Metadata
    assessed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    vet_version: str = "0.1.0-alpha"
    model_version: str = "phase1-poc"

    def to_dict(self) -> Dict:
        return {
            "entity_name": self.entity_name,
            "country": self.country,
            "industry": self.industry,
            "risk_tier": self.risk_tier,
            "risk_score": round(self.risk_score, 4),
            "confidence": round(self.confidence, 4),
            "component_scores": {k: round(v, 4) for k, v in self.component_scores.items()},
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "requires_human_review": self.requires_human_review,
            "assessed_at": self.assessed_at,
            "vet_version": self.vet_version,
        }


class RiskScorer:
    """
    V.E.T. primary interface — orchestrates the full risk scoring pipeline.

    Phase 1 (proof-of-concept) implementation uses:
    - Sanctions screening via fuzzy name matching (Layer 1)
    - Ownership depth scoring via graph traversal (Layer 2)
    - Heuristic feature scoring based on practitioner KYC/AML knowledge (Layer 3)
    - Weighted ensemble combining component scores (Layer 4)

    Phase 2 will replace heuristic features with trained ML models
    (XGBoost for tabular features, GraphSAGE for ownership graph).

    Usage:
        scorer = RiskScorer()
        result = scorer.score_entity("Acme International Trading Ltd", country="SG")
        print(result.risk_tier)  # "MEDIUM"
        print(result.evidence)   # [{"type": "sanctions_check", ...}, ...]
    """

    # Human-readable recommendations by risk tier
    RECOMMENDATIONS = {
        "LOW": "Standard procurement process. No additional screening required.",
        "MEDIUM": "Enhanced due diligence recommended. Verify beneficial ownership and request financial references.",
        "HIGH": "Escalate to compliance team before proceeding. Do not execute contract until cleared.",
        "CRITICAL": "Procurement hold. Refer to legal and compliance immediately. Do not communicate contract details to vendor.",
    }

    def __init__(self, config: Optional[VETConfig] = None):
        self.config = config or VETConfig()
        self._sanctions_loader = SanctionsLoader()
        self._entity_resolver = EntityResolver(
            max_depth=self.config.max_ownership_depth
        )
        self._initialized = False

    def initialize(self) -> None:
        """
        Load all data sources. Call before scoring.
        In Phase 1 this loads sample/public data.
        In Phase 2 this will connect to live API feeds.
        """
        logger.info("Initializing V.E.T. Risk Scorer (Phase 1 — public data only)")
        self._sanctions_loader.load_sample_data()
        self._initialized = True
        logger.info("V.E.T. initialized successfully")

    def score_entity(
        self,
        entity_name: str,
        country: Optional[str] = None,
        industry: Optional[str] = None,
        registration_number: Optional[str] = None,
    ) -> RiskAssessment:
        """
        Score a vendor entity and return a complete risk assessment.

        Args:
            entity_name: Legal name of the vendor entity
            country: ISO 3166-1 alpha-2 country code (e.g., "SG", "CN")
            industry: Industry classification (e.g., "technology", "chemicals")
            registration_number: Company registration number if available

        Returns:
            RiskAssessment with risk tier, score, and evidence chain
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"Scoring entity: '{entity_name}' [{country or 'unknown'}]")
        evidence = []
        component_scores = {}

        # ── Component 1: Sanctions screening ─────────────────────────
        sanctions_result = self._sanctions_loader.check_entity(
            entity_name, country=country
        )
        sanctions_score = self._compute_sanctions_score(sanctions_result)
        component_scores["sanctions_screening"] = sanctions_score

        if sanctions_result["is_sanctioned"]:
            evidence.append({
                "type": "sanctions_match",
                "severity": "CRITICAL" if sanctions_score > 0.9 else "HIGH",
                "detail": f"Matched {sanctions_result['match_count']} sanctioned entity/entities. "
                         f"Highest similarity: {sanctions_result['highest_similarity']}",
                "sources": sanctions_result["list_sources_checked"],
            })
        else:
            evidence.append({
                "type": "sanctions_check",
                "severity": "CLEAR",
                "detail": f"No sanctions matches found across {len(sanctions_result['list_sources_checked'])} lists.",
                "sources": sanctions_result["list_sources_checked"],
            })

        # ── Component 2: Geographic risk ──────────────────────────────
        geo_score = self._compute_geographic_risk(country)
        component_scores["geographic_risk"] = geo_score

        if geo_score > 0.5:
            evidence.append({
                "type": "geographic_risk",
                "severity": "HIGH" if geo_score > 0.7 else "MEDIUM",
                "detail": f"Entity domiciled in elevated-risk jurisdiction. "
                         f"Geographic risk index: {geo_score:.2f}",
                "country": country,
            })

        # ── Component 3: Industry risk ────────────────────────────────
        industry_score = self._compute_industry_risk(industry)
        component_scores["industry_risk"] = industry_score

        if industry_score > 0.5:
            evidence.append({
                "type": "industry_risk",
                "severity": "MEDIUM",
                "detail": f"Industry classification presents elevated supply chain risk. "
                         f"Industry risk index: {industry_score:.2f}",
                "industry": industry,
            })

        # ── Component 4: Ownership depth (Phase 1 heuristic) ─────────
        # In Phase 2 this uses the graph resolver with real BOI data
        ownership_score = self._compute_ownership_heuristic(
            entity_name, country, registration_number
        )
        component_scores["ownership_depth"] = ownership_score

        if ownership_score > 0.4:
            evidence.append({
                "type": "ownership_complexity",
                "severity": "MEDIUM",
                "detail": "Ownership structure complexity warrants beneficial ownership verification. "
                         "Phase 2 will provide graph-based analysis using FinCEN BOI data.",
                "note": "Phase 1 heuristic — full ownership graph analysis available in Phase 2",
            })

        # ── Ensemble: weighted combination ────────────────────────────
        composite_score = (
            component_scores["sanctions_screening"] * 0.45 +
            component_scores["geographic_risk"] * 0.25 +
            component_scores["industry_risk"] * 0.15 +
            component_scores["ownership_depth"] * 0.15
        )
        composite_score = min(composite_score, 1.0)

        # ── Map to risk tier ──────────────────────────────────────────
        risk_tier = self._score_to_tier(composite_score)
        requires_review = risk_tier in ("HIGH", "CRITICAL")

        # ── Confidence ────────────────────────────────────────────────
        # Phase 1 confidence is lower due to heuristic (not trained ML) models
        confidence = 0.65 if not sanctions_result["is_sanctioned"] else 0.85

        assessment = RiskAssessment(
            entity_name=entity_name,
            country=country,
            industry=industry,
            risk_tier=risk_tier,
            risk_score=round(composite_score, 4),
            confidence=confidence,
            component_scores=component_scores,
            evidence=evidence,
            recommendation=self.RECOMMENDATIONS[risk_tier],
            requires_human_review=requires_review,
        )

        logger.info(
            f"Assessment complete: {entity_name} → {risk_tier} "
            f"(score={composite_score:.3f}, confidence={confidence:.2f})"
        )
        return assessment

    def _compute_sanctions_score(self, sanctions_result: Dict) -> float:
        """Convert sanctions check result to 0.0-1.0 score."""
        if not sanctions_result["is_sanctioned"]:
            return 0.0
        # Direct match = critical; fuzzy match = proportional to similarity
        return min(sanctions_result["highest_similarity"] * 1.1, 1.0)

    def _compute_geographic_risk(self, country: Optional[str]) -> float:
        """
        Score geographic risk based on FATF lists and OFAC country programs.

        High-risk countries per OFAC country programs and FATF grey/black lists.
        This heuristic encodes the geographic risk framework used in
        KYC/AML assessment at YLG Bullion Group (2012-2016).
        """
        if not country:
            return 0.3  # Unknown country = moderate uncertainty risk

        country = country.upper()
        if country in self.config.high_risk_jurisdictions:
            return 0.9
        # Moderate risk jurisdictions (illustrative)
        moderate_risk = {"CN", "HK", "MX", "BR", "NG", "UA", "KZ"}
        if country in moderate_risk:
            return 0.45
        return 0.1  # Standard risk

    def _compute_industry_risk(self, industry: Optional[str]) -> float:
        """
        Score industry-specific supply chain risk.

        High-risk industries per BIS Export Control Classification Numbers
        and CISA critical infrastructure sector analysis.
        """
        if not industry:
            return 0.2

        industry = industry.lower()
        high_risk_keywords = [
            "semiconductor", "defense", "chemicals", "nuclear",
            "weapons", "encryption", "aerospace", "telecom",
        ]
        medium_risk_keywords = [
            "technology", "electronics", "software", "biotech",
            "pharmaceutical", "energy", "mining",
        ]

        for keyword in high_risk_keywords:
            if keyword in industry:
                return 0.8

        for keyword in medium_risk_keywords:
            if keyword in industry:
                return 0.4

        return 0.15

    def _compute_ownership_heuristic(
        self,
        entity_name: str,
        country: Optional[str],
        registration_number: Optional[str],
    ) -> float:
        """
        Phase 1 heuristic for ownership complexity.

        In Phase 2, this is replaced by the full EntityResolver graph
        analysis using live FinCEN BOI data. For Phase 1, we use
        signals available from the entity name and registration data.
        """
        score = 0.0

        # Indicators of potential shell company structure
        shell_indicators = [
            "holdings", "international", "global", "trading",
            "ventures", "capital", "investment", "enterprise",
            "resources", "group",
        ]
        name_lower = entity_name.lower()
        indicator_count = sum(1 for ind in shell_indicators if ind in name_lower)
        score += min(indicator_count * 0.1, 0.3)

        # High-risk country + opaque name = elevated ownership risk
        if country and country.upper() in self.config.high_risk_jurisdictions:
            score += 0.2

        # No registration number = less transparency
        if not registration_number:
            score += 0.1

        return min(score, 1.0)

    def _score_to_tier(self, score: float) -> str:
        """Map composite score to risk tier."""
        if score >= self.config.threshold_high:
            return "CRITICAL"
        elif score >= self.config.threshold_medium:
            return "HIGH"
        elif score >= self.config.threshold_low:
            return "MEDIUM"
        else:
            return "LOW"
