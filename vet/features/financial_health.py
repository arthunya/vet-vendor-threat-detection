"""f2 — Financial health (SEC EDGAR XBRL CompanyFacts).

Per Working Paper §4.4 / §6.5: shareholders'-equity-to-assets ratio as a
distress indicator, with the documented buyback-driven-negative-equity
confound. Score mapping (distress score, higher = riskier):
  ratio >= 0.15        -> 0.0
  0.0 <= ratio < 0.15  -> 0.3
  ratio < 0.0          -> 0.8   (known FP class per §6.5 — Phase 2 gates
                                 this with free-cash-flow)
  no coverage          -> None  (excluded from weighting, never a fake score)

Live mode queries https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
(free, no auth). Offline mode falls back to CACHE below — values recorded
from the live validation run of 2026-06-30 documented in the validation report
accompanying Working Paper §4.4. Cached entries are marked mode="cached" in evidence.
"""
from __future__ import annotations

import json
import urllib.request

EDGAR_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
UA = "VET-Framework research contact-via-westcliff"

# Values from the documented live validation (validation report, 2026-06-30).
CACHE: dict[str, dict] = {
    "0000320193": {"name": "Apple Inc.", "ratio": 0.21, "fy": "FY2025"},
    "0001286681": {"name": "Domino's Pizza, Inc.", "ratio": -2.27, "fy": "FY2025"},
    # Bed Bath & Beyond (validation case; Chapter 11 filed April 2023)
    "0000886158": {"name": "Bed Bath & Beyond Inc.", "ratio": -1.26, "fy": "FY2022"},
}


def _ratio_from_facts(facts: dict) -> tuple[float | None, str | None]:
    try:
        gaap = facts["facts"]["us-gaap"]
        eq = gaap["StockholdersEquity"]["units"]["USD"]
        at = gaap["Assets"]["units"]["USD"]
        eq_annual = [x for x in eq if x.get("form") == "10-K" and x.get("fy")]
        at_annual = [x for x in at if x.get("form") == "10-K" and x.get("fy")]
        if not eq_annual or not at_annual:
            return None, None
        eq_latest = max(eq_annual, key=lambda x: (x["fy"], x.get("end", "")))
        at_match = [x for x in at_annual if x["fy"] == eq_latest["fy"]]
        if not at_match:
            return None, None
        return eq_latest["val"] / at_match[0]["val"], f"FY{eq_latest['fy']}"
    except (KeyError, ZeroDivisionError, TypeError):
        return None, None


def _score(ratio: float) -> float:
    if ratio >= 0.15:
        return 0.0
    if ratio >= 0.0:
        return 0.3
    return 0.8


def compute(cik: str | None, live: bool = True) -> dict:
    base = {"feature": "financial_health"}
    if not cik:
        return {**base, "score": None,
                "raw_value": {"coverage": "none", "reason": "no SEC CIK"},
                "evidence": {"source": "SEC_EDGAR",
                             "result": "entity outside data coverage"}}
    cik10 = cik.zfill(10)
    if live:
        try:
            req = urllib.request.Request(EDGAR_URL.format(cik=cik10),
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                facts = json.loads(r.read())
            ratio, fy = _ratio_from_facts(facts)
            if ratio is not None:
                return {**base, "score": _score(ratio),
                        "raw_value": {"equity_to_assets": round(ratio, 4),
                                      "fiscal_year": fy, "mode": "live"},
                        "evidence": {"source": "SEC_EDGAR",
                                     "url": EDGAR_URL.format(cik=cik10),
                                     "mode": "live"}}
        except Exception:
            pass  # network unavailable -> fall through to cache
    if cik10 in CACHE:
        c = CACHE[cik10]
        return {**base, "score": _score(c["ratio"]),
                "raw_value": {"equity_to_assets": c["ratio"], "fiscal_year": c["fy"],
                              "mode": "cached"},
                "evidence": {"source": "SEC_EDGAR", "mode": "cached",
                             "provenance": "live validation 2026-06-30, validation report",
                             "url": EDGAR_URL.format(cik=cik10)}}
    return {**base, "score": None,
            "raw_value": {"coverage": "none", "mode": "offline, not in cache"},
            "evidence": {"source": "SEC_EDGAR",
                         "result": "no data available in this run"}}
