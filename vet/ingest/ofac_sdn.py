"""OFAC SDN list ingestion (live, full list).

Downloads the official Specially Designated Nationals list published by the
U.S. Treasury Office of Foreign Assets Control and loads all ENTITY-type
records into sanctions_records.

Official source (public, no authentication):
  https://www.treasury.gov/ofac/downloads/sdn.csv        (main records)
  https://www.treasury.gov/ofac/downloads/alt.csv        (aliases / AKAs)

SDN.CSV columns (fixed positions, per OFAC file spec):
  0 ent_num | 1 SDN_Name | 2 SDN_Type | 3 Program | ... ("-0-" = null)

Usage:
    python -m vet.ingest.ofac_sdn            # download + load
    python -m vet.ingest.ofac_sdn sdn.csv    # load from a local copy

Note: requires internet access to treasury.gov. In restricted environments,
use vet.ingest.seed_data for a hand-verified subset of real records.
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
from datetime import date

from vet import db

SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
ALT_URL = "https://www.treasury.gov/ofac/downloads/alt.csv"
NULL = "-0-"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "VET-Framework/0.1 (research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def _load_aliases(alt_text: str) -> dict[str, list[str]]:
    """alt.csv: 0 ent_num | 1 alt_num | 2 alt_type | 3 alt_name"""
    out: dict[str, list[str]] = {}
    for row in csv.reader(io.StringIO(alt_text)):
        if len(row) >= 4 and row[3] != NULL:
            out.setdefault(row[0].strip(), []).append(row[3].strip())
    return out


def ingest(sdn_text: str, alt_text: str | None = None, list_version: str | None = None) -> int:
    conn = db.connect()
    aliases = _load_aliases(alt_text) if alt_text else {}
    version = list_version or date.today().isoformat()
    n = 0
    for row in csv.reader(io.StringIO(sdn_text)):
        if len(row) < 4:
            continue
        ent_num, name, sdn_type, program = (c.strip() for c in row[:4])
        if name == NULL or not name:
            continue
        db.insert_sanctions_record(
            conn,
            list_name="OFAC_SDN",
            listed_name=name,
            aliases=aliases.get(ent_num, []),
            program=None if program == NULL else program,
            list_version=version,
            source_url=SDN_URL,
            raw_record={"ent_num": ent_num, "sdn_type": sdn_type, "program": program},
        )
        n += 1
    db.audit(conn, actor="ingest.ofac_sdn", action="INGEST_COMPLETE",
             payload={"records": n, "list_version": version, "source": SDN_URL})
    conn.close()
    return n


def main() -> None:
    if len(sys.argv) > 1:
        sdn_text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
        alt_text = open(sys.argv[2], encoding="utf-8", errors="replace").read() if len(sys.argv) > 2 else None
    else:
        print(f"Downloading {SDN_URL} ...")
        sdn_text = _fetch(SDN_URL)
        print(f"Downloading {ALT_URL} ...")
        alt_text = _fetch(ALT_URL)
    n = ingest(sdn_text, alt_text)
    print(f"Ingested {n} OFAC SDN records.")


if __name__ == "__main__":
    main()
