from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL CHECK (content_type IN ('movie', 'series')),
    canonical_key TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_type, canonical_key)
);

CREATE TABLE IF NOT EXISTS category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('live', 'movie', 'series')),
    quality TEXT,
    resolution TEXT,
    dynamic_range TEXT,
    audio TEXT,
    subtitles INTEGER,
    language_hint TEXT,
    UNIQUE(content_type, provider_category_id)
);

CREATE TABLE IF NOT EXISTS version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    language TEXT,
    quality TEXT,
    resolution TEXT,
    dynamic_range TEXT,
    audio TEXT,
    subtitles INTEGER,
    FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS stream (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    stream_url TEXT,
    container TEXT,
    external_ref TEXT,
    FOREIGN KEY (version_id) REFERENCES version(id) ON DELETE CASCADE,
    UNIQUE(version_id, source_id)
);

CREATE TABLE IF NOT EXISTS season (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL,
    season_number INTEGER NOT NULL,
    FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE,
    UNIQUE(content_id, season_number)
);

CREATE TABLE IF NOT EXISTS episode (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES season(id) ON DELETE CASCADE,
    UNIQUE(season_id, episode_number)
);

CREATE TABLE IF NOT EXISTS episode_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    language TEXT,
    quality TEXT,
    resolution TEXT,
    dynamic_range TEXT,
    audio TEXT,
    subtitles INTEGER,
    FOREIGN KEY (episode_id) REFERENCES episode(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS episode_stream (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_version_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    stream_url TEXT,
    container TEXT,
    external_ref TEXT,
    FOREIGN KEY (episode_version_id) REFERENCES episode_version(id) ON DELETE CASCADE,
    UNIQUE(episode_version_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_content_type ON content(content_type);
CREATE INDEX IF NOT EXISTS idx_content_canonical ON content(canonical_key);
CREATE INDEX IF NOT EXISTS idx_version_content ON version(content_id);
CREATE INDEX IF NOT EXISTS idx_stream_source ON stream(source_id);
CREATE INDEX IF NOT EXISTS idx_season_content ON season(content_id);
CREATE INDEX IF NOT EXISTS idx_episode_season ON episode(season_id);
CREATE INDEX IF NOT EXISTS idx_episode_version_episode ON episode_version(episode_id);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def table_names(path: str | Path) -> list[str]:
    with connect(path) as conn:
        return [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]


def schema_counts(path: str | Path) -> dict[str, int]:
    with connect(path) as conn:
        tables = table_names(path)
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
