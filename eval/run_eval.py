"""Benchmark evaluation — produces eval/results_latest.json + markdown report.

Benchmark v0 (seed): 33 real entities.
  HIGH-RISK ground truth (17): entities on OFAC SDN or BIS Entity List —
    each label is a public, citable government designation.
  LOW-RISK ground truth (16): major SEC registrants with no sanctions
    exposure, including Domino's Pizza — the documented false-positive
    stressor from Working Paper §6.5 (negative equity, financially healthy).
The synthetic DEMO fixture is excluded from all metrics.

Metric definitions:
  positive prediction = risk_tier in {HIGH, CRITICAL}
  precision = TP / (TP + FP)   recall = TP / (TP + FN)

Honest-scale note: this is benchmark v0 (n=33). The 500-entity benchmark of
Sprint Week 2 extends this file; the metric pipeline is identical.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vet import db, engine

HIGH_RISK = [
    "Huawei Technologies Co., Ltd.",
    "Semiconductor Manufacturing International Corporation",
    "Hangzhou Hikvision Digital Technology Co., Ltd.",
    "Zhejiang Dahua Technology Co., Ltd.",
    "Megvii Technology Limited",
    "iFLYTEK Co., Ltd.",
    "Kalashnikov Concern",
    "Almaz-Antey",
    "Rosoboronexport OAO",
    "Sberbank of Russia",
    "VTB Bank Public Joint Stock Company",
    "PMC Wagner",
    "Mahan Air",
    "Islamic Republic of Iran Shipping Lines",
    "Bank Melli Iran",
    "Korea Mining Development Trading Corporation",
    "Garantex Europe OU",
]
LOW_RISK = [
    "Apple Inc.", "Microsoft Corporation", "Cisco Systems, Inc.",
    "Intel Corporation", "Honeywell International Inc.", "FedEx Corporation",
    "United Parcel Service, Inc.", "Oracle Corporation",
    "International Business Machines Corporation", "Caterpillar Inc.",
    "Deere & Company", "Texas Instruments Incorporated",
    "The Procter & Gamble Company", "Johnson & Johnson", "PepsiCo, Inc.",
    "Domino's Pizza, Inc.",  # §6.5 false-positive stressor
]


def run(live_network: bool = False) -> dict:
    conn = db.connect()
    name_to_id = {r["canonical_name"]: r["entity_id"]
                  for r in conn.execute("SELECT entity_id, canonical_name FROM entities")}
    conn.close()

    results, tp = [], 0
    fp = fn = tn = 0
    for name, truth in [(n, "HIGH") for n in HIGH_RISK] + [(n, "LOW") for n in LOW_RISK]:
        if name not in name_to_id:
            results.append({"name": name, "error": "not in DB — run seed first"})
            continue
        r = engine.screen(name_to_id[name], requested_by="eval",
                          live_network=live_network)
        predicted_pos = r["risk_tier"] in ("HIGH", "CRITICAL")
        actual_pos = truth == "HIGH"
        if predicted_pos and actual_pos:
            tp += 1
        elif predicted_pos and not actual_pos:
            fp += 1
        elif not predicted_pos and actual_pos:
            fn += 1
        else:
            tn += 1
        results.append({"name": name, "ground_truth": truth,
                        "predicted_tier": r["risk_tier"],
                        "composite": r["composite_score"],
                        "critical_override": r["critical_override"]})

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    summary = {
        "benchmark": "v0-seed (n=33 real entities)",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": engine.model_version(),
        "confusion": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision_high_critical": round(precision, 4),
        "recall_high_critical": round(recall, 4),
        "results": results,
    }
    out = Path(__file__).parent / "results_latest.json"
    out.write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    s = run()
    print(json.dumps({k: v for k, v in s.items() if k != "results"}, indent=2))
    print(f"\nPer-entity results written to eval/results_latest.json")
    misses = [r for r in s["results"]
              if r.get("ground_truth") == "HIGH" and r["predicted_tier"] in ("LOW", "MEDIUM")]
    fps = [r for r in s["results"]
           if r.get("ground_truth") == "LOW" and r["predicted_tier"] in ("HIGH", "CRITICAL")]
    if misses:
        print("MISSED HIGH-RISK:", [m["name"] for m in misses])
    if fps:
        print("FALSE POSITIVES:", [m["name"] for m in fps])
