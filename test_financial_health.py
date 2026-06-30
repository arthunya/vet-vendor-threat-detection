"""
Test suite for vet.features.financial_health
================================================
Run this on a machine with normal internet access (NOT inside a
network-restricted sandbox) — it makes live calls to data.sec.gov.

Usage:
    pip install requests
    python test_financial_health.py

What this proves (for evidence/exhibit purposes):
    - The module successfully queries real SEC XBRL data for real companies
    - Negative-equity detection works correctly on real filings
    - The module correctly identifies non-SEC-filers (foreign/private
      vendors) and returns found=False rather than crashing
    - An honest, documented limitation: companies with large share
      buyback programs can show negative book equity while being
      financially healthy (NOT a distress signal in those cases) —
      included here as a known false-positive case, not hidden.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vet.features.financial_health import FinancialHealthChecker


TEST_CASES = [
    {
        "name": "Apple Inc.",
        "cik": "320193",
        "expectation": "Healthy — strong positive equity, should score LOW risk.",
    },
    {
        "name": "Domino's Pizza, Inc.",
        "cik": "1286681",
        "expectation": (
            "KNOWN EDGE CASE — Domino's has run large share-buyback programs "
            "for years and typically reports NEGATIVE book equity despite "
            "being financially healthy and highly profitable. Expect this "
            "module to flag it as distressed (risk_score ~0.85), which is "
            "a FALSE POSITIVE. Documented here intentionally — this is "
            "exactly the kind of honest limitation that belongs in the "
            "white paper's Section 6 (Limitations and Future Work), not "
            "something to hide. Phase 2 should combine this signal with "
            "free cash flow / profitability data to avoid penalizing "
            "buyback-driven negative equity."
        ),
    },
    {
        "name": "Acme Shell Trading Ltd (fictitious — not SEC-registered)",
        "cik": "9999999999",
        "expectation": "No SEC filing history — found=False, module correctly "
                        "defers to Layers 1-3 (sanctions/geo/industry/ownership) "
                        "rather than guessing.",
    },
    {
        "name": "Bed Bath & Beyond Inc.",
        "cik": "886158",
        "expectation": (
            "TRUE POSITIVE CASE — Bed Bath & Beyond filed for Chapter 11 "
            "bankruptcy on April 23, 2023. Independent financial reporting "
            "confirms shareholders' equity of approximately -$2.8 billion "
            "against total assets of approximately $2.2 billion in its final "
            "reporting period — a genuine, severe financial distress signal "
            "(equity eroded from +$2.72 billion in FY2017 to deeply negative "
            "by FY2022), unlike the Domino's buyback case above. Expect this "
            "module to correctly flag HIGH/CRITICAL risk on a real distress "
            "event, demonstrating the module catches genuine cases, not just "
            "the false-positive edge case."
        ),
    },
]


def run():
    checker = FinancialHealthChecker()
    print("=" * 78)
    print("V.E.T. Financial Health Module — Live SEC XBRL Test")
    print("=" * 78)

    for case in TEST_CASES:
        print(f"\n{case['name']}  (CIK {case['cik']})")
        print(f"Expectation: {case['expectation']}")
        print("-" * 78)
        result = checker.check_cik(case["cik"])
        print(f"  found:                {result.found}")
        if result.found and result.equity_ratio is not None:
            print(f"  equity_ratio:         {result.equity_ratio}")
            print(f"  negative_equity_flag: {result.negative_equity_flag}")
            print(f"  data_year (FY):       {result.data_year}")
            print(f"  risk_score:           {result.risk_score}")
        print(f"  note:                 {result.note}")

    print("\n" + "=" * 78)
    print("Test complete. Compare actual output above against the stated "
          "expectations to confirm the module behaves honestly, including "
          "on its known false-positive case (Domino's-style buyback equity).")
    print("=" * 78)


if __name__ == "__main__":
    run()
