CREATE TABLE IF NOT EXISTS wetlands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_fa TEXT,
    name_en TEXT,
    ris_no TEXT,
    area_ha REAL,
    latitude REAL,
    longitude REAL,
    montreux_status INTEGER DEFAULT 0,
    min_elev REAL,
    max_elev REAL,
    admin_region TEXT
);
CREATE INDEX IF NOT EXISTS idx_wetland_name ON wetlands(name_en);
