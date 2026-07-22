"""f3 / f4 / f5 — contextual risk signals.

f3 geographic_risk : FATF list membership + comprehensively sanctioned
                     jurisdictions. The FATF grey list changes at each
                     plenary (Feb/Jun/Oct); AS_OF marks the snapshot date.
                     Refresh from https://www.fatf-gafi.org before any
                     production run — this is config data, not code.
f4 entity_opacity  : ownership-chain depth + registry-identity coverage.
f5 industry_mismatch: declared NAICS vs. observed signal conflicts.
                      Phase-1 implements the rule for high-risk-jurisdiction
                      dual-use categories; logistics-pattern input arrives
                      with the CBP connector in Phase 2.
"""
from __future__ import annotations

import sqlite3

FATF_AS_OF = "2026-02 plenary snapshot — REFRESH BEFORE PRODUCTION USE"

# Call-for-action ("black list") + comprehensively sanctioned jurisdictions.
HIGH_RISK_JURISDICTIONS = {"IR", "KP", "SY", "CU", "RU", "BY", "MM"}
# Increased-monitoring ("grey list") snapshot — verify against fatf-gafi.org.
GREY_LIST = {"DZ", "AO", "CI", "CD", "HT", "KE", "LB", "MC", "MZ",
             "NA", "NP", "NG", "ZA", "SS", "VE", "VN", "YE", "LA", "BG"}

DUAL_USE_NAICS_PREFIXES = ("3341", "3344", "3345", "3364", "3329")  # computers,
# semiconductors, navigation/instruments, aerospace, ordnance-adjacent metalwork


def geographic_risk(jurisdiction: str | None, owner_jurisdictions: list[str]) -> dict:
    juris = (jurisdiction or "").upper()
    all_j = {juris, *(j.upper() for j in owner_jurisdictions if j)}
    if all_j & HIGH_RISK_JURISDICTIONS:
        score, hit = 0.9, sorted(all_j & HIGH_RISK_JURISDICTIONS)
        cat = "FATF call-for-action / comprehensively sanctioned"
    elif all_j & GREY_LIST:
        score, hit = 0.5, sorted(all_j & GREY_LIST)
        cat = "FATF increased monitoring (grey list)"
    else:
        score, hit, cat = 0.0, [], "no listed jurisdiction exposure"
    return {"feature": "geographic_risk", "score": score,
            "raw_value": {"jurisdictions_evaluated": sorted(all_j - {""}),
                          "hits": hit, "as_of": FATF_AS_OF},
            "evidence": {"source": "FATF", "category": cat,
                         "url": "https://www.fatf-gafi.org"}}


def entity_opacity(conn: sqlite3.Connection, entity_id: str,
                   lei: str | None, cik: str | None) -> dict:
    depth, frontier, seen = 0, {entity_id}, {entity_id}
    while frontier and depth < 5:
        rows = conn.execute(
            f"SELECT owner_id FROM ownership_edges WHERE owned_id IN "
            f"({','.join('?' * len(frontier))})", list(frontier)).fetchall()
        nxt = {r["owner_id"] for r in rows} - seen
        if not nxt:
            break
        depth += 1
        seen |= nxt
        frontier = nxt

    depth_score = min(depth / 4.0, 1.0) * 0.6      # deep chains are opaque
    identity_score = 0.0 if (lei or cik) else 0.4  # no verifiable registry ID
    score = round(min(depth_score + identity_score, 1.0), 4)
    return {"feature": "entity_opacity", "score": score,
            "raw_value": {"ownership_depth": depth,
                          "has_lei": bool(lei), "has_cik": bool(cik)},
            "evidence": {"source": "entity_graph",
                         "note": "depth via ownership_edges BFS; identity via LEI/CIK presence"}}


def industry_mismatch(naics_code: str | None, jurisdiction: str | None) -> dict:
    juris = (jurisdiction or "").upper()
    if naics_code and naics_code.startswith(DUAL_USE_NAICS_PREFIXES) \
            and juris in HIGH_RISK_JURISDICTIONS:
        return {"feature": "industry_mismatch", "score": 0.7,
                "raw_value": {"naics": naics_code, "jurisdiction": juris,
                              "rule": "dual-use sector in high-risk jurisdiction"},
                "evidence": {"source": "NAICS+FATF cross-reference"}}
    return {"feature": "industry_mismatch", "score": 0.0,
            "raw_value": {"naics": naics_code, "jurisdiction": juris,
                          "note": "logistics-pattern input lands in Phase 2 (CBP connector)"},
            "evidence": {"source": "NAICS+FATF cross-reference", "result": "no rule triggered"}}
