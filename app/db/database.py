from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import settings


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    provider_category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK(content_type IN ('live', 'movie', 'series')),
    provider_order INTEGER,
    updated_at TEXT NOT NULL,
    UNIQUE(provider_id, provider_category_id),
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_categories_type
ON categories(content_type);

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL CHECK(content_type IN ('channel', 'movie', 'series')),
    canonical_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    original_title TEXT,
    year INTEGER,
    overview TEXT,
    poster_url TEXT,
    backdrop_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_type
ON content(content_type);

CREATE INDEX IF NOT EXISTS idx_content_normalized_title
ON content(normalized_title);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL UNIQUE,
    overview TEXT,
    poster_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    collection_order INTEGER,
    PRIMARY KEY(collection_id, content_id),
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    season_number INTEGER NOT NULL,
    name TEXT,
    overview TEXT,
    poster_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(series_id, season_number),
    FOREIGN KEY(series_id) REFERENCES content(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    canonical_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    overview TEXT,
    air_date TEXT,
    poster_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(season_id, episode_number),
    FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER,
    episode_id INTEGER,
    quality TEXT,
    resolution TEXT,
    video_codec TEXT,
    audio_codec TEXT,
    dynamic_range TEXT,
    languages TEXT,
    subtitles TEXT,
    label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (content_id IS NOT NULL AND episode_id IS NULL)
        OR
        (content_id IS NULL AND episode_id IS NOT NULL)
    ),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_versions_content
ON versions(content_id);

CREATE INDEX IF NOT EXISTS idx_versions_episode
ON versions(episode_id);

CREATE TABLE IF NOT EXISTS streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    provider_stream_id TEXT,
    category_id INTEGER,
    stream_url TEXT NOT NULL,
    container_extension TEXT,
    original_name TEXT,
    raw_json TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(provider_id, provider_stream_id),
    FOREIGN KEY(version_id) REFERENCES versions(id) ON DELETE CASCADE,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_streams_provider
ON streams(provider_id);

CREATE INDEX IF NOT EXISTS idx_streams_version
ON streams(version_id);

CREATE TABLE IF NOT EXISTS content_categories (
    content_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY(content_id, category_id),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    live_count INTEGER DEFAULT 0,
    movie_count INTEGER DEFAULT 0,
    series_count INTEGER DEFAULT 0,
    season_count INTEGER DEFAULT 0,
    episode_count INTEGER DEFAULT 0,
    version_count INTEGER DEFAULT 0,
    stream_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    changed_count INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0,
    error TEXT,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS change_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_run_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    event_type TEXT NOT NULL CHECK(event_type IN ('added', 'changed', 'removed')),
    summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(sync_run_id) REFERENCES sync_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_change_events_run
ON change_events(sync_run_id);

CREATE INDEX IF NOT EXISTS idx_change_events_type
ON change_events(event_type);
"""


def connect() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
