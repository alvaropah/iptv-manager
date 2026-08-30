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
        names = tuple(row[2] for row in info)
        unique_pairs.add(names)

    return (
        ("content_id", "external_source") not in unique_pairs
        or ("episode_id", "external_source") not in unique_pairs
    )


def _ensure_metadata_links_schema(conn: sqlite3.Connection) -> None:
    """Upgrade any pre-episode metadata_links schema to the canonical model."""
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

    def value_or_default(column: str, default: str) -> str:
        return column if column in legacy_columns else default

    content_expr = value_or_default("content_id", "NULL")
    episode_expr = value_or_default("episode_id", "NULL")
    provider_expr = value_or_default("provider_title", "NULL")
    created_expr = value_or_default("created_at", "CURRENT_TIMESTAMP")
    updated_expr = value_or_default("updated_at", "CURRENT_TIMESTAMP")
    status_expr = value_or_default("match_status", "'matched'")
    score_expr = value_or_default("match_score", "NULL")
    matched_by_expr = value_or_default("matched_by", "NULL")

    conn.execute(f"""INSERT OR IGNORE INTO metadata_links
        (id, content_id, episode_id, provider_title, external_source, external_id,
         match_status, match_score, matched_by, created_at, updated_at)
        SELECT id, {content_expr}, {episode_expr}, {provider_expr}, external_source, external_id,
               {status_expr}, {score_expr}, {matched_by_expr}, {created_expr}, {updated_expr}
        FROM metadata_links_legacy
        WHERE external_source IS NOT NULL AND external_id IS NOT NULL""")
    conn.execute("DROP TABLE metadata_links_legacy")
    conn.execute("PRAGMA foreign_keys=ON")


def init_metadata_db(conn: sqlite3.Connection) -> None:
    _ensure_metadata_links_schema(conn)
    conn.executescript(METADATA_SCHEMA)


def json_value(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
