"""
V.E.T. Layer 3b: Financial Health Signal (SEC XBRL)
=====================================================
Adds a NEW data domain to the V.E.T. data-fusion architecture: real,
structured financial-statement data for SEC-registered (U.S.-listed or
U.S.-reporting) vendor entities.

Rationale (ties directly to the V.E.T. mission):
  - Shell companies and fraudulent vendors often show financially
    inconsistent profiles: negative shareholders' equity, near-zero
    revenue relative to claimed scale, or rapid equity deterioration.
  - This is a classic, well-established financial-statement-fraud /
    going-concern screening technique used in real KYC/AML due
    diligence (the author's 14 years of practice, encoded here as a
    quantitative heuristic rather than manual review).

Data source: SEC EDGAR XBRL Frames / CompanyFacts API
  https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit-CIK}.json
  - Free, public, no API key required (SEC requires a descriptive
    User-Agent header identifying the requester).
  - Covers ~10,000+ SEC-registered companies.
  - Rate limit: 10 requests/second per IP (SEC-imposed).

Scope and limitation (stated honestly):
  This signal applies ONLY to entities with a U.S. SEC filing history
  (CIK). It does NOT apply to foreign private vendors, privately held
  U.S. companies that don't file with the SEC, or shell companies that
  by definition have no SEC presence (for those, the existing sanctions
  + geographic + industry + ownership signals remain primary). This
  module is a complementary signal, not a replacement for Layers 1-3.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

SEC_USER_AGENT = "V.E.T. Research Prototype (Kanoklertwongse, arthunya@gmail.com)"
SEC_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


@dataclass
class FinancialHealthResult:
    cik: Optional[str]
    found: bool
    equity_ratio: Optional[float] = None          # StockholdersEquity / Assets
    revenue_latest: Optional[float] = None
    assets_latest: Optional[float] = None
    negative_equity_flag: bool = False
    data_year: Optional[int] = None
    risk_score: float = 0.0                        # 0.0 (healthy) - 1.0 (distressed)
    note: str = ""


class FinancialHealthChecker:
    """
    Queries SEC XBRL CompanyFacts for a given CIK and derives a
    financial-distress risk signal.

    Usage:
        checker = FinancialHealthChecker()
        result = checker.check_cik("0000320193")  # Apple
        print(result.risk_score)
    """

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 10):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": SEC_USER_AGENT})
        self.timeout = timeout

    def check_cik(self, cik: str) -> FinancialHealthResult:
        cik_padded = str(int(cik)).zfill(10)
        url = SEC_BASE_URL.format(cik=cik_padded)

        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return FinancialHealthResult(
                    cik=cik_padded, found=False,
                    note=f"No SEC filing history found (HTTP {resp.status_code}). "
                         f"Entity is likely private/foreign — financial health signal "
                         f"not applicable; rely on Layers 1-3.",
                )
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"SEC XBRL lookup failed for CIK {cik_padded}: {e}")
            return FinancialHealthResult(cik=cik_padded, found=False,
                                          note=f"Lookup error: {e}")

        gaap = data.get("facts", {}).get("us-gaap", {})

        assets = self._latest_value(gaap.get("Assets"))
        liabilities = self._latest_value(gaap.get("Liabilities"))
        equity = self._latest_value(gaap.get("StockholdersEquity"))
        revenue = self._latest_value(
            gaap.get("Revenues") or gaap.get("RevenueFromContractWithCustomerExcludingAssessedTax")
        )

        if assets is None or equity is None:
            return FinancialHealthResult(
                cik=cik_padded, found=True,
                note="SEC filer found but core balance-sheet tags (Assets/"
                     "StockholdersEquity) not present in standard us-gaap taxonomy.",
            )

        equity_ratio = equity["val"] / assets["val"] if assets["val"] else None
        negative_equity = equity["val"] < 0

        # Simple, transparent distress heuristic (Phase 1 — not ML-trained):
        #   negative equity                -> strong distress signal
        #   equity ratio < 0.05 (highly leveraged) -> moderate signal
        #   otherwise                      -> healthy
        if negative_equity:
            risk_score = 0.85
            note = "Negative shareholders' equity — financial distress indicator."
        elif equity_ratio is not None and equity_ratio < 0.05:
            risk_score = 0.45
            note = "Very low equity-to-assets ratio — highly leveraged."
        else:
            risk_score = 0.05
            note = "Equity position within normal range."

        return FinancialHealthResult(
            cik=cik_padded,
            found=True,
            equity_ratio=round(equity_ratio, 4) if equity_ratio is not None else None,
            revenue_latest=revenue["val"] if revenue else None,
            assets_latest=assets["val"],
            negative_equity_flag=negative_equity,
            data_year=assets.get("fy"),
            risk_score=risk_score,
            note=note,
        )

    @staticmethod
    def _latest_value(concept: Optional[Dict]) -> Optional[Dict]:
        """Pull the most recent annual (10-K, fp='FY') data point for a us-gaap concept."""
        if not concept:
            return None
        usd_values = concept.get("units", {}).get("USD", [])
        annual = [v for v in usd_values if v.get("form") == "10-K" and v.get("fp") == "FY"]
        pool = annual or usd_values
        if not pool:
            return None
        return max(pool, key=lambda v: v.get("end", ""))
