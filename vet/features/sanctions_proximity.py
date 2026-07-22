"""f1 — Sanctions proximity.

Scoring:
  direct exact/alias match          -> 1.00
  direct fuzzy match (>= 0.90 sim)  -> 0.90 * similarity
  hop-1 owner/officer listed        -> 0.70 * owner_score   (OFAC 50% rule logic)
  hop-2                             -> 0.40 * ancestor_score
Every non-zero score carries an evidence dict pointing at the matched
sanctions record (record_id, list, source_url).
"""
from __future__ import annotations

import json
import sqlite3

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 90.0

# Corporate suffixes stripped before fuzzy comparison — standard sanctions-
# screening normalization so "Huawei Technologies Ltd" matches
# "HUAWEI TECHNOLOGIES CO., LTD.". Exact (score 1.0) still requires equality
# of the RAW normalized strings; suffix-stripped equality scores 0.90.
CORP_SUFFIXES = {"CO", "LTD", "INC", "CORP", "CORPORATION", "COMPANY", "LLC",
                 "PLC", "OAO", "PAO", "OJSC", "PJSC", "AO", "OU", "GMBH",
                 "SA", "AG", "PTE", "SDN", "BHD", "LIMITED", "INCORPORATED"}


def _normalize(s: str) -> str:
    for ch in ",.()[]":
        s = s.replace(ch, " ")
    return " ".join(s.upper().split())


def _strip_suffixes(s: str) -> str:
    toks = [t for t in s.split() if t not in CORP_SUFFIXES]
    return " ".join(toks) if toks else s


def _match_name(conn: sqlite3.Connection, name: str) -> tuple[float, dict | None]:
    """Return (score in [0,1], evidence) for the best sanctions match of one name."""
    target = _normalize(name)
    target_core = _strip_suffixes(target)
    best_score, best_ev = 0.0, None
    for row in conn.execute(
        "SELECT record_id, list_name, listed_name, aliases, program, source_url, list_version "
        "FROM sanctions_records"
    ):
        candidates = [row["listed_name"]] + json.loads(row["aliases"])
        for cand in candidates:
            cand_norm = _normalize(cand)
            cand_core = _strip_suffixes(cand_norm)
            if target == cand_norm:
                score, sim = 1.0, 100.0
            else:
                sim = fuzz.token_sort_ratio(target_core, cand_core)
                if sim >= FUZZY_THRESHOLD:
                    score = 0.9 * (sim / 100.0)
                else:
                    # Affiliate-containment heuristic: listed core name fully
                    # contained in the target ("HUAWEI TECHNOLOGIES (THAILAND)"
                    # contains "HUAWEI TECHNOLOGIES"). Scores 0.85 -> routes to
                    # human review rather than auto-CRITICAL, matching standard
                    # screening practice for possible-affiliate hits.
                    sim = fuzz.token_set_ratio(target_core, cand_core)
                    meaningful = (len(cand_core.split()) >= 2
                                  or len(cand_core) >= 6)
                    if sim >= 95.0 and meaningful:
                        score = 0.85
                    else:
                        continue
            if score > best_score:
                best_score = score
                best_ev = {
                    "source": row["list_name"],
                    "record_id": row["record_id"],
                    "matched_text": cand,
                    "similarity": sim,
                    "program": row["program"],
                    "list_version": row["list_version"],
                    "url": row["source_url"],
                }
    return best_score, best_ev


def _owners(conn: sqlite3.Connection, entity_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT e.entity_id, e.canonical_name FROM ownership_edges oe "
        "JOIN entities e ON e.entity_id = oe.owner_id WHERE oe.owned_id = ?",
        (entity_id,),
    ).fetchall()


def compute(conn: sqlite3.Connection, entity_id: str, canonical_name: str,
            name_variants: list[str]) -> dict:
    # Direct match on all known names
    direct_best, direct_ev = 0.0, None
    for nm in [canonical_name, *name_variants]:
        s, ev = _match_name(conn, nm)
        if s > direct_best:
            direct_best, direct_ev = s, ev

    # Hop-1 / hop-2 through the ownership graph
    hop_best, hop_ev = 0.0, None
    for owner in _owners(conn, entity_id):
        s1, ev1 = _match_name(conn, owner["canonical_name"])
        if s1 * 0.7 > hop_best:
            hop_best = s1 * 0.7
            hop_ev = {**(ev1 or {}), "path": f"owner:{owner['canonical_name']}", "hop": 1}
        for gp in _owners(conn, owner["entity_id"]):
            s2, ev2 = _match_name(conn, gp["canonical_name"])
            if s2 * 0.4 > hop_best:
                hop_best = s2 * 0.4
                hop_ev = {**(ev2 or {}), "path": f"owner-of-owner:{gp['canonical_name']}", "hop": 2}

    score = max(direct_best, hop_best)
    evidence = direct_ev if direct_best >= hop_best else hop_ev
    return {
        "feature": "sanctions_proximity",
        "score": round(score, 4),
        "raw_value": {"direct": round(direct_best, 4), "network": round(hop_best, 4)},
        "evidence": evidence or {"source": "sanctions_records",
                                 "result": "no match at threshold >= 0.90"},
        "direct_hit": direct_best == 1.0,
    }
