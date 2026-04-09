"""
V.E.T. Quick Demo — Run this to see the risk scorer in action.

Usage:
    python demo.py

This demonstrates the Phase 1 proof-of-concept risk scoring pipeline
using public data sources only (no FinCEN BOI or commercial APIs required).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from vet.models.risk_scorer import RiskScorer
from vet.config import VETConfig
import json


def run_demo():
    print("=" * 60)
    print("V.E.T. — Vendor Entity Threat Detection")
    print("Phase 1 Proof-of-Concept Demo")
    print(f"DOI: 10.13140/RG.2.2.33961.76641")
    print("=" * 60)
    print()

    # Initialize scorer
    config = VETConfig()
    scorer = RiskScorer(config=config)
    scorer.initialize()

    # Test cases demonstrating different risk profiles
    test_entities = [
        {
            "entity_name": "Apple Inc.",
            "country": "US",
            "industry": "technology",
            "description": "Well-known U.S. technology company — should score LOW",
        },
        {
            "entity_name": "Acme International Trading Holdings Ltd",
            "country": "IR",
            "industry": "electronics",
            "description": "Iran-based trading company with opaque name — should score HIGH/CRITICAL",
        },
        {
            "entity_name": "Singapore Semiconductor Ventures Pte Ltd",
            "country": "SG",
            "industry": "semiconductor",
            "description": "Semiconductor company in Singapore — should score MEDIUM",
        },
        {
            "entity_name": "Example Sanctioned Trading Company",
            "country": "IR",
            "industry": "trading",
            "description": "Name matches sanctioned entity in test dataset — should score CRITICAL",
        },
    ]

    for i, test in enumerate(test_entities, 1):
        print(f"Test {i}: {test['description']}")
        print(f"Entity: {test['entity_name']} [{test['country']}]")
        print("-" * 40)

        result = scorer.score_entity(
            entity_name=test["entity_name"],
            country=test["country"],
            industry=test["industry"],
        )

        # Display result
        tier_symbols = {
            "LOW": "✅",
            "MEDIUM": "⚠️ ",
            "HIGH": "🔴",
            "CRITICAL": "🚨",
        }
        symbol = tier_symbols.get(result.risk_tier, "?")

        print(f"Risk Tier:     {symbol} {result.risk_tier}")
        print(f"Risk Score:    {result.risk_score:.4f}")
        print(f"Confidence:    {result.confidence:.0%}")
        print()
        print("Component Scores:")
        for component, score in result.component_scores.items():
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {component:<28} {bar} {score:.2f}")
        print()
        print(f"Recommendation: {result.recommendation}")
        print(f"Human Review Required: {result.requires_human_review}")
        print()
        print("Evidence Chain:")
        for ev in result.evidence:
            severity_sym = {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "⚠️", "CLEAR": "✅"}.get(ev["severity"], "ℹ️")
            print(f"  {severity_sym} [{ev['type']}] {ev['detail']}")
        print()
        print("=" * 60)
        print()

    print("Demo complete.")
    print()
    print("To learn more about V.E.T.:")
    print("  White Paper: https://doi.org/10.13140/RG.2.2.33961.76641")
    print("  GitHub:      https://github.com/arthunya/vet-vendor-threat-detection")


if __name__ == "__main__":
    run_demo()
