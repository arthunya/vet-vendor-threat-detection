"""Build the V.E.T. demo company database (JSON) from real public datasets.

Inputs (fetched from public GitHub data repos, provenance in comments):
  data_build/sp500.csv  — S&P 500 constituents (datasets/s-and-p-500-companies)
                          columns: Symbol,Security,GICS Sector,GICS Sub-Industry,
                                   Headquarters Location,Date added,CIK,Founded
  data_build/nasdaq.csv — NASDAQ-listed securities (datasets/nasdaq-listings)
                          columns: Symbol,Security Name

Output: data_build/vet_db.json with three sections:
  companies  — real US companies (large caps + small/mid caps). NO fraud
               labels are ever attached to real companies; they are screened
               live on real attributes only.
  sanctions  — curated subset of REAL OFAC SDN / BIS Entity List designations
               (each publicly citable). Production uses the full live mirror
               via vet.ingest.ofac_sdn (~15k+ records).
  synthetic  — clearly labeled fictitious shell-company profiles used ONLY to
               demonstrate fraud-pattern detection heuristics. Every name
               carries the "[SYNTHETIC DEMO]" tag; excluded from all metrics.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data_build"

# ---------------------------------------------------------------- companies
EXCLUDE = re.compile(
    r"ETF|Fund|Trust|Warrant|Right(s)?\b|Unit(s)?\b|Notes? due|Preferred|"
    r"Depositary|Acquisition|Portfolio|Index|ETN\b", re.IGNORECASE)


def load_sp500() -> list[dict]:
    out = []
    with open(BUILD / "sp500.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            founded = re.search(r"\d{4}", row.get("Founded", "") or "")
            out.append({
                "name": row["Security"].strip(),
                "ticker": row["Symbol"].strip(),
                "sizeClass": "large",
                "sector": row.get("GICS Sector", "").strip() or None,
                "hq": row.get("Headquarters Location", "").strip() or None,
                "cik": str(int(row["CIK"])).zfill(10) if row.get("CIK") else None,
                "founded": int(founded.group()) if founded else None,
                "registryId": True,
                "src": "S&P 500 constituents (public dataset)",
            })
    return out


def load_nasdaq(limit: int = 760) -> list[dict]:
    seen, rows = set(), []
    with open(BUILD / "nasdaq.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("Security Name") or "").strip()
            if not raw or EXCLUDE.search(raw):
                continue
            name = raw.split(" - ")[0].strip().rstrip(".")
            if len(name) < 4 or name.upper() in seen:
                continue
            seen.add(name.upper())
            rows.append({
                "name": name,
                "ticker": (row.get("Symbol") or "").strip(),
                "sizeClass": "smallmid",
                "sector": None, "hq": "United States", "cik": None,
                "founded": None, "registryId": True,
                "src": "NASDAQ listed securities (public dataset snapshot)",
            })
    rows.sort(key=lambda r: r["name"])
    step = max(1, len(rows) // limit)
    return rows[::step][:limit]


# ---------------------------------------------------------------- sanctions
# Curated REAL designations. Format:
# (list, name, aliases, program/authority, year, note)
S = "OFAC_SDN"
B = "BIS_ENTITY_LIST"
SANCTIONS = [
    # --- Russia-related (OFAC SDN) ---
    (S, "Rosoboronexport OAO", ["ROSOBORONEKSPORT"], "Russia-related", 2015, "State arms export intermediary"),
    (S, "Kalashnikov Concern", ["CONCERN KALASHNIKOV", "KALASHNIKOV GROUP"], "UKRAINE-EO13661", 2014, "Defense manufacturer"),
    (S, "Almaz-Antey", ["ALMAZ-ANTEY AIR AND SPACE DEFENCE"], "UKRAINE-EO13661", 2014, "Air defense conglomerate"),
    (S, "Uralvagonzavod", [], "UKRAINE-EO13661", 2014, "Armored vehicle manufacturer"),
    (S, "Bank Rossiya", ["AB ROSSIYA"], "UKRAINE-EO13661", 2014, "First 2014 bank designation"),
    (S, "SMP Bank", [], "UKRAINE-EO13661", 2014, ""),
    (S, "Sberbank of Russia", ["SBERBANK ROSSII"], "RUSSIA-EO14024", 2022, "Full blocking April 2022"),
    (S, "VTB Bank Public Joint Stock Company", ["VTB BANK"], "RUSSIA-EO14024", 2022, ""),
    (S, "Alfa-Bank", ["ALFA BANK JSC"], "RUSSIA-EO14024", 2022, ""),
    (S, "Otkritie FC Bank", ["BANK OTKRITIE FINANCIAL CORPORATION"], "RUSSIA-EO14024", 2022, ""),
    (S, "Promsvyazbank", ["PSB"], "RUSSIA-EO14024", 2022, ""),
    (S, "Novikombank", [], "RUSSIA-EO14024", 2022, ""),
    (S, "Gazprombank", ["GPB"], "RUSSIA-EO14024", 2024, "Designated November 2024"),
    (S, "Sovcomflot", ["SCF GROUP"], "RUSSIA-EO14024", 2024, "State maritime shipping"),
    (S, "Alrosa", ["PJSC ALROSA"], "RUSSIA-EO14024", 2022, "Diamond mining"),
    (S, "PMC Wagner", ["WAGNER GROUP", "CHVK WAGNER"], "Russia-related / TCO", 2017, "TCO designation January 2023"),
    (S, "Internet Research Agency", ["IRA"], "CYBER-EO13694", 2018, "Influence operations"),
    (S, "Concord Management and Consulting", [], "CYBER-EO13694", 2018, ""),
    (S, "M-Invest", [], "Sudan/Wagner-linked", 2018, ""),
    (S, "Evro Polis", [], "Syria/Wagner-linked", 2018, ""),
    (S, "Positive Technologies", [], "CYBER-EO13694", 2021, "Designated April 2021"),
    # --- Iran (OFAC SDN) ---
    (S, "Mahan Air", ["MAHAN AIRLINES"], "SDGT / IRGC", 2011, ""),
    (S, "Islamic Republic of Iran Shipping Lines", ["IRISL"], "IRAN", 2008, ""),
    (S, "Bank Melli Iran", ["MELLI BANK"], "IRAN", 2018, "Re-designated 2018"),
    (S, "Bank Mellat", [], "IRAN", 2018, ""),
    (S, "Bank Saderat Iran", [], "IRAN / SDGT", 2007, ""),
    (S, "National Iranian Oil Company", ["NIOC"], "IRAN / SDGT", 2020, ""),
    (S, "Islamic Revolutionary Guard Corps", ["IRGC"], "SDGT / IRGC", 2017, ""),
    (S, "IRGC-Qods Force", ["QODS FORCE", "QUDS FORCE"], "SDGT", 2007, ""),
    # --- DPRK (OFAC SDN) ---
    (S, "Korea Mining Development Trading Corporation", ["KOMID"], "DPRK", 2005, "Primary arms dealer"),
    (S, "Air Koryo", [], "DPRK", 2016, ""),
    (S, "Foreign Trade Bank of the DPRK", ["FTB"], "DPRK", 2013, ""),
    (S, "Korea Kwangson Banking Corporation", ["KKBC"], "DPRK", 2009, ""),
    (S, "Lazarus Group", ["HIDDEN COBRA"], "DPRK-CYBER", 2019, "State cyber threat group"),
    (S, "Bluenoroff", [], "DPRK-CYBER", 2019, ""),
    (S, "Andariel", [], "DPRK-CYBER", 2019, ""),
    # --- Illicit finance / crypto (OFAC SDN) ---
    (S, "Garantex Europe OU", ["GARANTEX"], "RUSSIA / CYBER", 2022, "Virtual currency exchange"),
    (S, "Suex OTC", ["SUEX"], "CYBER-EO13694", 2021, "First crypto exchange designation"),
    (S, "Chatex", [], "CYBER-EO13694", 2021, ""),
    (S, "Hydra Market", ["HYDRA MARKETPLACE"], "RUSSIA / CYBER", 2022, "Darknet market"),
    (S, "Blender.io", ["BLENDER IO"], "DPRK-CYBER", 2022, "First mixer designation"),
    (S, "Sinbad.io", ["SINBAD IO"], "DPRK-CYBER", 2023, "Mixer"),
    (S, "Genesis Market", [], "CYBER-EO13694", 2023, "Credential marketplace"),
    # --- Other programs (OFAC SDN) ---
    (S, "Scientific Studies and Research Center", ["SSRC"], "SYRIA", 2005, "CW program entity"),
    (S, "Petroleos de Venezuela S.A.", ["PDVSA"], "VENEZUELA-EO13850", 2019, "State oil company"),
    (S, "Belaruskali", [], "BELARUS-EO14038", 2021, "State potash producer"),
    (S, "Sinaloa Cartel", ["CARTEL DE SINALOA"], "SDNTK / FTO", 2009, ""),
    (S, "Cartel de Jalisco Nueva Generacion", ["CJNG", "JALISCO NEW GENERATION CARTEL"], "SDNTK / FTO", 2015, ""),
    (S, "Tren de Aragua", [], "TCO / FTO", 2024, ""),
    (S, "Hizballah", ["HEZBOLLAH"], "SDGT / FTO", 1997, ""),
    (S, "Hamas", ["HARAKAT AL-MUQAWAMA AL-ISLAMIYA"], "SDGT / FTO", 1997, ""),
    # --- BIS Entity List ---
    (B, "Huawei Technologies Co., Ltd.", ["HUAWEI"], "EAR Part 744 Supp. 4", 2019, "Added May 2019 incl. affiliates"),
    (B, "Semiconductor Manufacturing International Corporation", ["SMIC"], "EAR Part 744 Supp. 4", 2020, ""),
    (B, "Hangzhou Hikvision Digital Technology Co., Ltd.", ["HIKVISION"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "Zhejiang Dahua Technology Co., Ltd.", ["DAHUA TECHNOLOGY"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "Megvii Technology Limited", ["MEGVII", "FACE++"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "iFLYTEK Co., Ltd.", ["IFLYTEK"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "Beijing SenseTime Technology Development Co., Ltd.", ["SENSETIME"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "Yitu Technologies", ["YITU"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "CloudWalk Technology", ["CLOUDWALK"], "EAR Part 744 Supp. 4", 2020, ""),
    (B, "SZ DJI Technology Co., Ltd.", ["DJI"], "EAR Part 744 Supp. 4", 2020, "Added December 2020"),
    (B, "Sugon", ["DAWNING INFORMATION INDUSTRY"], "EAR Part 744 Supp. 4", 2019, ""),
    (B, "Yangtze Memory Technologies Co., Ltd.", ["YMTC"], "EAR Part 744 Supp. 4", 2022, ""),
    (B, "Inspur Group", [], "EAR Part 744 Supp. 4", 2023, ""),
    (B, "Loongson Technology", [], "EAR Part 744 Supp. 4", 2023, ""),
    (B, "BGI Research", [], "EAR Part 744 Supp. 4", 2023, ""),
    (B, "NSO Group", ["NSO GROUP TECHNOLOGIES"], "EAR Part 744 Supp. 4", 2021, "Spyware vendor"),
    (B, "Candiru", [], "EAR Part 744 Supp. 4", 2021, "Spyware vendor"),
]

# ------------------------------------------------------- synthetic fixtures
# Fictitious profiles demonstrating shell-company / fraud-pattern heuristics.
# NEVER real companies. Names carry an explicit tag.
SYNTHETIC = [
    {"name": "Meridian Global Trade LLC [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "IR", "founded": 2026, "registryId": False,
     "naics": "334413", "sector": "Semiconductors (wholesale)",
     "pattern": "Weeks-old company, unverifiable ownership, dual-use electronics, beneficial owner traced to a sanctioned jurisdiction"},
    {"name": "Apex Freight Solutions Inc [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "RU", "founded": 2026, "registryId": False,
     "naics": "488510", "sector": "Freight forwarding",
     "pattern": "New freight forwarder with owner in a comprehensively sanctioned jurisdiction — classic transshipment cutout profile"},
    {"name": "Coastal Micro Components [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "HK", "founded": 2025, "registryId": False,
     "naics": "334418", "sector": "Electronic components",
     "pattern": "No registry identity, recent incorporation, component broker in an export-diversion-prone category"},
    {"name": "Northstar Procurement Group [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "AE", "founded": 2026, "registryId": False,
     "naics": "423610", "sector": "Electrical equipment wholesale",
     "pattern": "Aggregator with opaque ownership chain routed through an intermediary jurisdiction"},
    {"name": "Blue Harbor Logistics LLC [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "BY", "founded": 2026, "registryId": False,
     "naics": "488510", "sector": "Freight forwarding",
     "pattern": "Shell-pattern logistics entity; owner jurisdiction on comprehensive sanctions list"},
    {"name": "Quantum Edge Instruments [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "MM", "founded": 2025, "registryId": False,
     "naics": "334516", "sector": "Analytical instruments",
     "pattern": "Dual-use instrumentation reseller, no verifiable registry identity"},
    {"name": "Silverline Trading Partners [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "VN", "founded": 2026, "registryId": False,
     "naics": "423690", "sector": "Electronic parts wholesale",
     "pattern": "Recent incorporation + FATF-grey-list ownership + broker category"},
    {"name": "Summit Bridge Ventures LLC [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "LB", "founded": 2026, "registryId": False,
     "naics": "541614", "sector": "Logistics consulting",
     "pattern": "Consulting wrapper with grey-list beneficial ownership and no operating footprint"},
    {"name": "Pacific Rim Components Co [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "KP", "founded": 2026, "registryId": False,
     "naics": "334419", "sector": "Electronic components",
     "pattern": "Textbook front-company profile: sanctioned-jurisdiction ownership of a US components broker"},
    {"name": "Ironwood Supply Chain LLC [SYNTHETIC DEMO]", "jurisdiction": "US",
     "ownerJurisdiction": "US", "founded": 2026, "registryId": False,
     "naics": "493110", "sector": "Warehousing",
     "pattern": "Domestic but weeks old with no registry identity — flags for verification, not accusation"},
]


def main() -> None:
    companies = load_sp500() + load_nasdaq()
    seen = set()
    deduped = []
    for c in companies:
        k = c["name"].upper()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)

    sanctions = [
        {"list": l, "name": n, "aliases": a, "program": p, "year": y, "note": t}
        for l, n, a, p, y, t in SANCTIONS
    ]
    db = {
        "meta": {
            "built": "2026-07-06",
            "companies": len(deduped),
            "sanctions_records": len(sanctions),
            "synthetic_profiles": len(SYNTHETIC),
            "provenance": {
                "companies": ["datasets/s-and-p-500-companies (GitHub)",
                              "datasets/nasdaq-listings (GitHub snapshot)"],
                "sanctions": "Curated subset of public OFAC SDN / BIS Entity List "
                             "designations; production uses full live mirror",
            },
        },
        "companies": deduped,
        "sanctions": sanctions,
        "synthetic": SYNTHETIC,
    }
    out = BUILD / "vet_db.json"
    out.write_text(json.dumps(db, ensure_ascii=False))
    print(f"companies={len(deduped)} (large={sum(1 for c in deduped if c['sizeClass']=='large')}, "
          f"smallmid={sum(1 for c in deduped if c['sizeClass']=='smallmid')}) "
          f"sanctions={len(sanctions)} synthetic={len(SYNTHETIC)} -> {out} "
          f"({out.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
