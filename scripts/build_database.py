#!/usr/bin/env python3
"""Build a normalized SQLite location database from GeoNames daily extracts."""
from __future__ import annotations
import argparse
import csv
import io
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://download.geonames.org/export/dump/"
DATASETS = {"cities500": "cities500.zip", "cities1000": "cities1000.zip",
            "cities5000": "cities5000.zip", "allCountries": "allCountries.zip"}
SUPPORT = ("countryInfo.txt", "admin1CodesASCII.txt", "admin2Codes.txt")
COLUMNS = """geonameid name asciiname alternatenames latitude longitude feature_class
feature_code country_code cc2 admin1_code admin2_code admin3_code admin4_code
population elevation dem timezone modification_date""".split()

def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size:
        return
    temp = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "locations-db-builder/1.0"})
    print(f"Downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=180) as response, temp.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    temp.replace(target)

def tsv(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        yield from csv.reader(f, delimiter="\t")

def as_int(value):
    try: return int(value) if value else None
    except (ValueError, TypeError): return None

def as_float(value):
    try: return float(value) if value else None
    except (ValueError, TypeError): return None

def countries_from(path):
    result = {}
    for r in tsv(path):
        if not r or r[0].startswith("#") or len(r) < 19 or r[0] == "ISO":
            continue
        result[r[0]] = (r[0], r[1] or None, r[2] or None, r[3] or None,
            r[4], r[5] or None, r[8] or None, r[15] or None,
            as_int(r[7]), as_float(r[6]), r[10] or None, r[9] or None,
            r[17] or None, as_int(r[16]))
    return result

def admin1_from(path):
    result = {}
    for r in tsv(path):
        if len(r) < 4 or "." not in r[0]: continue
        country, code = r[0].split(".", 1)
        result[(country, code)] = (country, code, r[1], r[2] or None, as_int(r[3]))
    return result

def admin2_from(path):
    result = {}
    for r in tsv(path):
        if len(r) < 4: continue
        parts = r[0].split(".", 2)
        if len(parts) != 3: continue
        country, a1, a2 = parts
        result[(country, a1, a2)] = (country, a1, a2, r[1], r[2] or None, as_int(r[3]))
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=DATASETS, default="cities1000")
    parser.add_argument("--output", type=Path, default=Path("data/locations.sqlite3"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/geonames"))
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    files = [DATASETS[args.dataset], *SUPPORT]
    for filename in files:
        target = args.cache_dir / filename
        if args.force_download: target.unlink(missing_ok=True)
        download(BASE + filename, target)

    countries = countries_from(args.cache_dir / SUPPORT[0])
    admin1 = admin1_from(args.cache_dir / SUPPORT[1])
    admin2 = admin2_from(args.cache_dir / SUPPORT[2])
    schema = Path(__file__).resolve().parents[1] / "schema" / "sqlite.sql"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.output)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(schema.read_text(encoding="utf-8"))
    try:
        with db:
            db.executemany("""INSERT OR REPLACE INTO countries
              (iso2,iso3,iso_numeric,fips_code,name,capital,continent_code,languages,
               population,area_sq_km,currency_code,tld,neighbours,geoname_id)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", countries.values())
            db.executemany("INSERT OR REPLACE INTO admin1 VALUES (?,?,?,?,?)", admin1.values())
            db.executemany("INSERT OR REPLACE INTO admin2 VALUES (?,?,?,?,?,?)", admin2.values())
            zip_path = args.cache_dir / DATASETS[args.dataset]
            imported = 0
            with zipfile.ZipFile(zip_path) as zf:
                member = next(n for n in zf.namelist() if n.endswith(".txt"))
                with zf.open(member) as raw:
                    stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                    batch = []
                    for row in csv.reader(stream, delimiter="\t"):
                        if len(row) != len(COLUMNS): continue
                        r = dict(zip(COLUMNS, row))
                        # Only populated-place records, not rivers, roads, peaks, etc.
                        if r["feature_class"] != "P" or r["country_code"] not in countries:
                            continue
                        lat, lon, gid = as_float(r["latitude"]), as_float(r["longitude"]), as_int(r["geonameid"])
                        if lat is None or lon is None or gid is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            continue
                        batch.append((gid, r["name"], r["asciiname"] or None, lat, lon,
                            r["feature_code"] or None, r["country_code"], r["admin1_code"] or None,
                            r["admin2_code"] or None, r["admin3_code"] or None, r["admin4_code"] or None,
                            as_int(r["population"]) or 0, as_int(r["elevation"]), as_int(r["dem"]),
                            r["timezone"] or None, r["modification_date"] or None))
                        if len(batch) == 5000:
                            db.executemany("""INSERT OR REPLACE INTO places
                              (geoname_id,name,ascii_name,latitude,longitude,feature_code,country_iso2,
                               admin1_code,admin2_code,admin3_code,admin4_code,population,elevation_m,
                               dem_m,timezone,modified_date)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
                            imported += len(batch); batch.clear()
                    if batch:
                        db.executemany("""INSERT OR REPLACE INTO places
                          (geoname_id,name,ascii_name,latitude,longitude,feature_code,country_iso2,
                           admin1_code,admin2_code,admin3_code,admin4_code,population,elevation_m,
                           dem_m,timezone,modified_date)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
                        imported += len(batch)
        print(f"Created {args.output}: {imported:,} places, {len(countries):,} countries/territories, "
              f"{len(admin1):,} first-level and {len(admin2):,} second-level divisions.")
        print("Use SQL view: location_hierarchy")
    finally:
        db.close()

if __name__ == "__main__":
    main()
