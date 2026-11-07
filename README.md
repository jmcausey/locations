# Locations database

A normalized worldwide geographic reference database for **continent → country → state/province → county/district → city/locality** lookups, coordinates, population, elevation, and time zones.

This repository contains a reproducible schema and import tool. The generated database is built locally from the daily GeoNames extracts and is not committed.

## Data source and attribution

Source: [GeoNames downloads](https://download.geonames.org/export/dump/) and [GeoNames terms](https://www.geonames.org/export/).

**Attribution:** Geographic data © [GeoNames](https://www.geonames.org/), licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). GeoNames data is provided “as is”, without warranty of accuracy, timeliness, or completeness. Preserve attribution when redistributing generated databases.

## Data model

- **Continent:** code and normalized continent name.
- **Country/territory:** ISO alpha-2, ISO alpha-3, ISO numeric, FIPS, name, capital, languages, currency, neighbours.
- **Admin1:** first-level state/province/region source code and names.
- **Admin2:** second-level county/district source code and names.
- **Place:** GeoNames ID, names, feature code, coordinates, population, elevation, timezone and source modification date.

Admin1/admin2 identifiers are retained as GeoNames source codes; they vary by country and are not incorrectly forced into a universal subdivision standard. ISO 3166-2 mappings can be layered on when sourced and validated.

## Build

Python 3.10+; no third-party packages are required.

```bash
python3 scripts/build_database.py
```

Default is `cities1000.zip` (places with population > 1000 or administrative seats), plus `countryInfo.txt`, `admin1CodesASCII.txt`, and `admin2Codes.txt`. Creates `data/locations.sqlite3`; downloads are cached in `.cache/geonames/`.

```bash
python3 scripts/build_database.py --dataset cities5000
python3 scripts/build_database.py --dataset cities500
python3 scripts/build_database.py --dataset allCountries
python3 scripts/build_database.py --force-download
python3 scripts/build_database.py --output /path/to/locations.sqlite3
```

The full `allCountries` source is much larger. Only GeoNames feature class `P` (populated places) is imported, not every mountain, road, stream, or other physical feature.

## Query examples

The database includes a convenience view, `location_hierarchy`.

```sql
-- Country and continent list
SELECT DISTINCT continent, country_code, country
FROM location_hierarchy ORDER BY continent, country;

-- Cascading hierarchy filter
SELECT city, country, state_province, county_district,
       latitude, longitude, population, timezone
FROM location_hierarchy
WHERE continent = 'North America'
  AND country_code = 'US'
  AND state_province = 'Texas'
  AND city LIKE 'Malakoff%'
ORDER BY population DESC;

-- Search by city
SELECT * FROM location_hierarchy
WHERE city LIKE '%Seattle%' ORDER BY population DESC;
```

Python:

```python
import sqlite3

db = sqlite3.connect("data/locations.sqlite3")
db.row_factory = sqlite3.Row
rows = db.execute(
    """SELECT city, country, state_province, latitude, longitude
       FROM location_hierarchy
       WHERE country_code = ? AND state_province = ?
       ORDER BY city""",
    ("US", "Texas"),
).fetchall()
for row in rows:
    print(dict(row))
```

## Design notes

- Coordinates are WGS84 latitude/longitude as supplied by GeoNames.
- Country codes are ISO 3166-1 alpha-2/alpha-3 where supplied.
- Admin1/admin2 codes are source identifiers and may be country-specific.
- Continent names are derived from GeoNames continent codes.
- Re-running the builder refreshes a daily snapshot; incremental sync is not yet implemented.
- SQLite provides a portable reference database; the same model can be adapted to PostgreSQL for service integration.

## License

Repository software/schema: GPL-3.0. Imported GeoNames data retains its separate CC BY 4.0 attribution requirements.
