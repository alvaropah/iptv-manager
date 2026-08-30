from __future__ import annotations

import json
import sqlite3

METADATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER,
    episode_id INTEGER,
    provider_title TEXT,
    external_source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    match_status TEXT NOT NULL DEFAULT 'matched' CHECK(match_status IN ('matched','review','rejected')),
    match_score REAL,
    matched_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_id, external_source),
    UNIQUE(episode_id, external_source),
    CHECK ((content_id IS NOT NULL AND episode_id IS NULL) OR (content_id IS NULL AND episode_id IS NOT NULL)),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metadata_links_content ON metadata_links(content_id);
CREATE INDEX IF NOT EXISTS idx_metadata_links_episode ON metadata_links(episode_id);
CREATE INDEX IF NOT EXISTS idx_metadata_links_status ON metadata_links(match_status);
CREATE INDEX IF NOT EXISTS idx_metadata_links_external ON metadata_links(external_source, external_id);

CREATE TABLE IF NOT EXISTS content_metadata (
    content_id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT,
    original_title TEXT,
    overview TEXT,
    year INTEGER,
    runtime INTEGER,
    genres_json TEXT,
    director TEXT,
    creators_json TEXT,
    cast_json TEXT,
    poster_url TEXT,
    backdrop_url TEXT,
    rating REAL,
    raw_json TEXT,
    language TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS episode_metadata (
    episode_id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT,
    overview TEXT,
    air_date TEXT,
    runtime INTEGER,
    still_url TEXT,
    raw_json TEXT,
    language TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS person_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    character TEXT,
    profile_url TEXT,
    UNIQUE(source, external_id, role, character)
);
"""


def _metadata_links_needs_rebuild(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA table_info(metadata_links)").fetchall()
    if not rows:
        return False
    columns = {row[1] for row in rows}
    if "episode_id" not in columns:
        return True
    unique_pairs: set[tuple[str, ...]] = set()
    for idx in conn.execute("PRAGMA index_list(metadata_links)").fetchall():
        if not idx[2] or not idx[3]:
            continue
        info = conn.execute(f'PRAGMA index_info("{idx[1]}")').fetchall()
        unique_pairs.add(tuple(row[2] for row in info))
    return (("content_id", "external_source") not in unique_pairs
            or ("episode_id", "external_source") not in unique_pairs)


def _ensure_metadata_links_schema(conn: sqlite3.Connection) -> None:
    if not _metadata_links_needs_rebuild(conn):
        return
    rows = conn.execute("PRAGMA table_info(metadata_links)").fetchall()
    if not rows:
        return
    legacy_columns = {row[1] for row in rows}
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("ALTER TABLE metadata_links RENAME TO metadata_links_legacy")
    conn.execute("""CREATE TABLE metadata_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_id INTEGER,
        episode_id INTEGER,
        provider_title TEXT,
        external_source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        match_status TEXT NOT NULL DEFAULT 'matched' CHECK(match_status IN ('matched','review','rejected')),
        match_score REAL,
        matched_by TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(content_id, external_source),
        UNIQUE(episode_id, external_source),
        CHECK ((content_id IS NOT NULL AND episode_id IS NULL) OR (content_id IS NULL AND episode_id IS NOT NULL)),
        FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
        FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_content ON metadata_links(content_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_episode ON metadata_links(episode_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_status ON metadata_links(match_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_external ON metadata_links(external_source, external_id)")

    def col(name: str, default: str) -> str:
        return name if name in legacy_columns else default

    conn.execute(f"""INSERT OR IGNORE INTO metadata_links
        (id, content_id, episode_id, provider_title, external_source, external_id,
         match_status, match_score, matched_by, created_at, updated_at)
        SELECT id, {col('content_id','NULL')}, {col('episode_id','NULL')}, {col('provider_title','NULL')},
               external_source, external_id, {col('match_status',"'matched'")}, {col('match_score','NULL')},
               {col('matched_by','NULL')}, {col('created_at','CURRENT_TIMESTAMP')}, {col('updated_at','CURRENT_TIMESTAMP')}
        FROM metadata_links_legacy
        WHERE external_source IS NOT NULL AND external_id IS NOT NULL""")
    conn.execute("DROP TABLE metadata_links_legacy")
    conn.execute("PRAGMA foreign_keys=ON")


def _episode_metadata_needs_rebuild(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA table_info(episode_metadata)").fetchall()
    if not rows:
        return False
    # episode_id must be the actual SQLite PRIMARY KEY because the enrichment
    # script uses ON CONFLICT(episode_id). Older restored catalogs may have the
    # column but not the constraint.
    episode_pk = any(row[1] == "episode_id" and row[5] == 1 for row in rows)
    required = {"episode_id", "source", "external_id", "title", "overview", "air_date",
                "runtime", "still_url", "raw_json", "language", "updated_at"}
    return not episode_pk or not required.issubset({row[1] for row in rows})


def _ensure_episode_metadata_schema(conn: sqlite3.Connection) -> None:
    if not _episode_metadata_needs_rebuild(conn):
        return
    rows = conn.execute("PRAGMA table_info(episode_metadata)").fetchall()
    if not rows:
        return
    legacy = {row[1] for row in rows}
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("ALTER TABLE episode_metadata RENAME TO episode_metadata_legacy")
    conn.execute("""CREATE TABLE episode_metadata (
        episode_id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        title TEXT,
        overview TEXT,
        air_date TEXT,
        runtime INTEGER,
        still_url TEXT,
        raw_json TEXT,
        language TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
    )""")
    cols = [name for name in (
        "episode_id", "source", "external_id", "title", "overview", "air_date",
        "runtime", "still_url", "raw_json", "language", "updated_at"
    ) if name in legacy]
    if "episode_id" in cols and "source" in cols and "external_id" in cols:
        names = ",".join(cols)
        conn.execute(f"INSERT OR IGNORE INTO episode_metadata ({names}) SELECT {names} FROM episode_metadata_legacy")
    conn.execute("DROP TABLE episode_metadata_legacy")
    conn.execute("PRAGMA foreign_keys=ON")


def init_metadata_db(conn: sqlite3.Connection) -> None:
    _ensure_metadata_links_schema(conn)
    _ensure_episode_metadata_schema(conn)
    conn.executescript(METADATA_SCHEMA)


def json_value(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
