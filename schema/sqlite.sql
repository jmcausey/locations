PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS countries (
    iso2 TEXT PRIMARY KEY, iso3 TEXT, iso_numeric TEXT, fips_code TEXT,
    name TEXT NOT NULL, capital TEXT, continent_code TEXT, languages TEXT,
    population INTEGER, area_sq_km REAL, currency_code TEXT, tld TEXT,
    neighbours TEXT, geoname_id INTEGER
);
CREATE TABLE IF NOT EXISTS admin1 (
    country_iso2 TEXT NOT NULL, admin1_code TEXT NOT NULL, name TEXT NOT NULL,
    ascii_name TEXT, geoname_id INTEGER,
    PRIMARY KEY (country_iso2, admin1_code),
    FOREIGN KEY (country_iso2) REFERENCES countries(iso2)
);
CREATE TABLE IF NOT EXISTS admin2 (
    country_iso2 TEXT NOT NULL, admin1_code TEXT NOT NULL, admin2_code TEXT NOT NULL,
    name TEXT NOT NULL, ascii_name TEXT, geoname_id INTEGER,
    PRIMARY KEY (country_iso2, admin1_code, admin2_code),
    FOREIGN KEY (country_iso2, admin1_code) REFERENCES admin1(country_iso2, admin1_code)
);
CREATE TABLE IF NOT EXISTS places (
    geoname_id INTEGER PRIMARY KEY, name TEXT NOT NULL, ascii_name TEXT,
    latitude REAL NOT NULL, longitude REAL NOT NULL, feature_code TEXT,
    country_iso2 TEXT NOT NULL, admin1_code TEXT, admin2_code TEXT,
    admin3_code TEXT, admin4_code TEXT, population INTEGER NOT NULL DEFAULT 0,
    elevation_m INTEGER, dem_m INTEGER, timezone TEXT, modified_date TEXT,
    FOREIGN KEY (country_iso2) REFERENCES countries(iso2)
);
CREATE INDEX IF NOT EXISTS idx_places_name ON places(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_places_country ON places(country_iso2);
CREATE INDEX IF NOT EXISTS idx_places_admin1 ON places(country_iso2, admin1_code);
CREATE INDEX IF NOT EXISTS idx_places_admin2 ON places(country_iso2, admin1_code, admin2_code);
CREATE INDEX IF NOT EXISTS idx_places_population ON places(population DESC);
CREATE INDEX IF NOT EXISTS idx_admin1_name ON admin1(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_admin2_name ON admin2(name COLLATE NOCASE);

CREATE VIEW IF NOT EXISTS location_hierarchy AS
SELECT p.geoname_id, p.name AS city, p.ascii_name, p.latitude, p.longitude,
       p.feature_code, p.population, p.elevation_m, p.timezone, p.modified_date,
       c.iso2 AS country_code, c.iso3 AS country_code_3, c.name AS country,
       c.continent_code,
       CASE c.continent_code
         WHEN 'AF' THEN 'Africa' WHEN 'AS' THEN 'Asia'
         WHEN 'EU' THEN 'Europe' WHEN 'NA' THEN 'North America'
         WHEN 'OC' THEN 'Oceania' WHEN 'SA' THEN 'South America'
         WHEN 'AN' THEN 'Antarctica' ELSE NULL END AS continent,
       p.admin1_code AS state_province_code, a1.name AS state_province,
       p.admin2_code AS county_district_code, a2.name AS county_district,
       p.admin3_code, p.admin4_code
FROM places p JOIN countries c ON c.iso2 = p.country_iso2
LEFT JOIN admin1 a1 ON a1.country_iso2 = p.country_iso2 AND a1.admin1_code = p.admin1_code
LEFT JOIN admin2 a2 ON a2.country_iso2 = p.country_iso2
 AND a2.admin1_code = p.admin1_code AND a2.admin2_code = p.admin2_code;
