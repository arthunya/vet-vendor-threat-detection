"""Seed dataset: hand-verified subset of REAL sanctions records.

Every record below corresponds to a real, publicly documented designation on
the OFAC SDN list or the BIS Entity List. This subset exists so the system is
runnable in offline/restricted environments; production ingestion uses
vet.ingest.ofac_sdn (full live list, ~15,000+ records).

Provenance policy: each record carries source_url pointing at the official
list. Designation years are stated per public press releases. If any record
is later delisted, live ingestion supersedes this file (list_version wins).

The ONLY synthetic record is `DEMO_SHELL` at the bottom — a test fixture used
to exercise hop-1 ownership propagation. It is explicitly labeled synthetic
and is excluded from all benchmark metrics.
"""
from __future__ import annotations

from vet import db

OFAC_URL = "https://sanctionssearch.ofac.treas.gov/"
BIS_URL = "https://www.bis.doc.gov/index.php/policy-guidance/lists-of-parties-of-concern/entity-list"
SEED_VERSION = "seed-2026-07-06"

# (list_name, listed_name, aliases, program, note)
SEED_SANCTIONS = [
    # --- OFAC SDN (entities) ---
    ("OFAC_SDN", "KALASHNIKOV CONCERN", ["CONCERN KALASHNIKOV", "KALASHNIKOV GROUP"],
     "UKRAINE-EO13661", "Designated July 2014"),
    ("OFAC_SDN", "ALMAZ-ANTEY", ["ALMAZ-ANTEY AIR AND SPACE DEFENCE CORPORATION"],
     "UKRAINE-EO13661", "Designated July 2014"),
    ("OFAC_SDN", "ROSOBORONEXPORT OAO", ["ROSOBORONEKSPORT OJSC"],
     "RUSSIA-RELATED", "State arms export intermediary; multiple designations"),
    ("OFAC_SDN", "SBERBANK OF RUSSIA", ["SBERBANK ROSSII PAO"],
     "RUSSIA-EO14024", "Full blocking April 2022"),
    ("OFAC_SDN", "VTB BANK PUBLIC JOINT STOCK COMPANY", ["VTB BANK PAO"],
     "RUSSIA-EO14024", "Full blocking February 2022"),
    ("OFAC_SDN", "PMC WAGNER", ["WAGNER GROUP", "CHVK WAGNER"],
     "RUSSIA-RELATED/TCO", "Designated 2017; TCO designation January 2023"),
    ("OFAC_SDN", "MAHAN AIR", ["MAHAN AIRLINES"],
     "SDGT/IRGC", "Designated October 2011"),
    ("OFAC_SDN", "ISLAMIC REPUBLIC OF IRAN SHIPPING LINES", ["IRISL"],
     "IRAN", "Shipping designations"),
    ("OFAC_SDN", "BANK MELLI IRAN", ["MELLI BANK"],
     "IRAN", "Iranian state bank designation"),
    ("OFAC_SDN", "KOREA MINING DEVELOPMENT TRADING CORPORATION", ["KOMID"],
     "DPRK", "Primary DPRK arms dealer designation"),
    ("OFAC_SDN", "GARANTEX EUROPE OU", ["GARANTEX"],
     "RUSSIA-RELATED/CYBER", "Virtual currency exchange, designated April 2022"),
    # --- BIS Entity List ---
    ("BIS_ENTITY_LIST", "HUAWEI TECHNOLOGIES CO., LTD.", ["HUAWEI"],
     "EAR Supp. No. 4 to Part 744", "Added May 2019"),
    ("BIS_ENTITY_LIST", "SEMICONDUCTOR MANUFACTURING INTERNATIONAL CORPORATION", ["SMIC"],
     "EAR Supp. No. 4 to Part 744", "Added December 2020"),
    ("BIS_ENTITY_LIST", "HANGZHOU HIKVISION DIGITAL TECHNOLOGY CO., LTD.", ["HIKVISION"],
     "EAR Supp. No. 4 to Part 744", "Added October 2019"),
    ("BIS_ENTITY_LIST", "ZHEJIANG DAHUA TECHNOLOGY CO., LTD.", ["DAHUA TECHNOLOGY"],
     "EAR Supp. No. 4 to Part 744", "Added October 2019"),
    ("BIS_ENTITY_LIST", "MEGVII TECHNOLOGY LIMITED", ["MEGVII"],
     "EAR Supp. No. 4 to Part 744", "Added October 2019"),
    ("BIS_ENTITY_LIST", "IFLYTEK CO., LTD.", ["IFLYTEK"],
     "EAR Supp. No. 4 to Part 744", "Added October 2019"),
]

# Vendor entities to register in the entity graph.
# (name, jurisdiction, cik or None)
SEED_ENTITIES = [
    # Low-risk benchmark side (major SEC registrants, no sanctions exposure)
    ("Apple Inc.", "US", "0000320193"),
    ("Microsoft Corporation", "US", "0000789019"),
    ("Cisco Systems, Inc.", "US", "0000858877"),
    ("Intel Corporation", "US", "0000050863"),
    ("Honeywell International Inc.", "US", "0000773840"),
    ("FedEx Corporation", "US", "0001048911"),
    ("United Parcel Service, Inc.", "US", "0001090727"),
    ("Oracle Corporation", "US", "0001341439"),
    ("International Business Machines Corporation", "US", "0000051143"),
    ("Caterpillar Inc.", "US", "0000018230"),
    ("Deere & Company", "US", "0000315189"),
    ("Texas Instruments Incorporated", "US", "0000097476"),
    ("The Procter & Gamble Company", "US", "0000080424"),
    ("Johnson & Johnson", "US", "0000200406"),
    ("PepsiCo, Inc.", "US", "0000077476"),
    # Known false-positive stressor from Working Paper §6.5 (buyback-driven
    # negative equity, financially healthy). Ground truth: LOW risk.
    ("Domino's Pizza, Inc.", "US", "0001286681"),
    # High-risk side registered as graph entities (names mirror listings)
    ("Huawei Technologies Co., Ltd.", "CN", None),
    ("Semiconductor Manufacturing International Corporation", "CN", None),
    ("Hangzhou Hikvision Digital Technology Co., Ltd.", "CN", None),
    ("Zhejiang Dahua Technology Co., Ltd.", "CN", None),
    ("Megvii Technology Limited", "CN", None),
    ("iFLYTEK Co., Ltd.", "CN", None),
    ("Kalashnikov Concern", "RU", None),
    ("Almaz-Antey", "RU", None),
    ("Rosoboronexport OAO", "RU", None),
    ("Sberbank of Russia", "RU", None),
    ("VTB Bank Public Joint Stock Company", "RU", None),
    ("PMC Wagner", "RU", None),
    ("Mahan Air", "IR", None),
    ("Islamic Republic of Iran Shipping Lines", "IR", None),
    ("Bank Melli Iran", "IR", None),
    ("Korea Mining Development Trading Corporation", "KP", None),
    ("Garantex Europe OU", "EE", None),
]


def load() -> dict:
    conn = db.connect()
    n_sanc = 0
    for list_name, name, aliases, program, note in SEED_SANCTIONS:
        url = OFAC_URL if list_name == "OFAC_SDN" else BIS_URL
        db.insert_sanctions_record(
            conn, list_name=list_name, listed_name=name, aliases=aliases,
            program=program, list_version=SEED_VERSION, source_url=url,
            raw_record={"note": note, "seed": True},
        )
        n_sanc += 1

    ids: dict[str, str] = {}
    for name, juris, cik in SEED_ENTITIES:
        ids[name] = db.upsert_entity(
            conn, canonical_name=name, jurisdiction=juris, cik=cik,
            source_refs=[{"source": "seed", "note": "public registry identity",
                          "fetched_at": db.now_iso()}],
        )

    # --- SYNTHETIC TEST FIXTURE (clearly labeled, excluded from benchmark) ---
    demo_id = db.upsert_entity(
        conn, canonical_name="DEMO Trading Partners LLC [SYNTHETIC TEST FIXTURE]",
        jurisdiction="AE",
        source_refs=[{"source": "test_fixture", "synthetic": True}],
    )
    db.add_ownership_edge(
        conn, owner_id=ids["Kalashnikov Concern"], owned_id=demo_id,
        edge_type="beneficial_owner", pct=60.0,
        source_ref={"source": "test_fixture", "synthetic": True,
                    "purpose": "hop-1 sanctions propagation unit test"},
    )
    ids["DEMO Trading Partners LLC [SYNTHETIC TEST FIXTURE]"] = demo_id

    db.audit(conn, actor="ingest.seed_data", action="SEED_LOADED",
             payload={"sanctions_records": n_sanc, "entities": len(ids),
                      "list_version": SEED_VERSION})
    conn.close()
    return {"sanctions_records": n_sanc, "entities": len(ids)}


if __name__ == "__main__":
    print(load())
