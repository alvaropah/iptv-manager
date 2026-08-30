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
    UNIQUE(external_source, external_id),
    CHECK ((content_id IS NOT NULL AND episode_id IS NULL) OR (content_id IS NULL AND episode_id IS NOT NULL)),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metadata_links_content ON metadata_links(content_id);
CREATE INDEX IF NOT EXISTS idx_metadata_links_episode ON metadata_links(episode_id);
CREATE INDEX IF NOT EXISTS idx_metadata_links_status ON metadata_links(match_status);

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


def init_metadata_db(conn: sqlite3.Connection) -> None:
    conn.executescript(METADATA_SCHEMA)


def json_value(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
