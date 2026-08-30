from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import settings

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id INTEGER NOT NULL, provider_category_id TEXT NOT NULL, name TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK(content_type IN ('live','movie','series')), provider_order INTEGER, selected INTEGER NOT NULL DEFAULT 0,
    quality TEXT, resolution TEXT, dynamic_range TEXT, audio TEXT, subtitles INTEGER, language_hint TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_id, provider_category_id), FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_categories_type ON categories(content_type);
CREATE INDEX IF NOT EXISTS idx_categories_selected ON categories(selected, content_type);
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id INTEGER NOT NULL, content_type TEXT NOT NULL CHECK(content_type IN ('movie','series')),
    canonical_title TEXT NOT NULL, normalized_title TEXT NOT NULL, original_title TEXT, year INTEGER, overview TEXT, poster_url TEXT, backdrop_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1, first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_detail_sync_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_id, content_type, normalized_title, year), FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_content_type ON content(content_type);
CREATE INDEX IF NOT EXISTS idx_content_normalized_title ON content(normalized_title);
CREATE INDEX IF NOT EXISTS idx_content_active ON content(is_active);
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, series_id INTEGER NOT NULL, season_number INTEGER NOT NULL, name TEXT, overview TEXT, poster_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1, first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(series_id, season_number), FOREIGN KEY(series_id) REFERENCES content(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, season_id INTEGER NOT NULL, episode_number INTEGER NOT NULL, canonical_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL, overview TEXT, air_date TEXT, poster_url TEXT, is_active INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(season_id, episode_number), FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER, episode_id INTEGER, category_id INTEGER NOT NULL, source_key TEXT NOT NULL,
    quality TEXT, resolution TEXT, video_codec TEXT, audio_codec TEXT, dynamic_range TEXT, languages TEXT, subtitles TEXT, label TEXT,
    is_active INTEGER NOT NULL DEFAULT 1, first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((content_id IS NOT NULL AND episode_id IS NULL) OR (content_id IS NULL AND episode_id IS NOT NULL)),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE, FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT, UNIQUE(content_id, episode_id, category_id, source_key)
);
CREATE INDEX IF NOT EXISTS idx_versions_content ON versions(content_id);
CREATE INDEX IF NOT EXISTS idx_versions_episode ON versions(episode_id);
CREATE TABLE IF NOT EXISTS streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT, version_id INTEGER NOT NULL, provider_id INTEGER NOT NULL, provider_stream_id TEXT NOT NULL,
    stream_url TEXT, container_extension TEXT, original_name TEXT, raw_json TEXT, fingerprint TEXT, is_active INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_id, version_id, provider_stream_id), FOREIGN KEY(version_id) REFERENCES versions(id) ON DELETE CASCADE, FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_streams_version ON streams(version_id);
CREATE INDEX IF NOT EXISTS idx_streams_active ON streams(is_active);
CREATE TABLE IF NOT EXISTS content_categories (
    content_id INTEGER NOT NULL, category_id INTEGER NOT NULL, PRIMARY KEY(content_id, category_id),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE, FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS stream_categories (
    provider_stream_id TEXT NOT NULL, category_id INTEGER NOT NULL, PRIMARY KEY(provider_stream_id, category_id),
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS series_sources (
    content_id INTEGER NOT NULL, provider_series_id TEXT NOT NULL, category_id INTEGER NOT NULL, fingerprint TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_detail_sync_at TEXT, is_active INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(content_id, provider_series_id, category_id), FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_series_sources_provider_id ON series_sources(provider_series_id);
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
    status TEXT NOT NULL, live_count INTEGER DEFAULT 0, movie_count INTEGER DEFAULT 0, series_count INTEGER DEFAULT 0, season_count INTEGER DEFAULT 0,
    episode_count INTEGER DEFAULT 0, version_count INTEGER DEFAULT 0, stream_count INTEGER DEFAULT 0, new_count INTEGER DEFAULT 0, changed_count INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0, detail_requests INTEGER DEFAULT 0, skipped_detail_requests INTEGER DEFAULT 0, error TEXT,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS change_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sync_run_id INTEGER NOT NULL, entity_type TEXT NOT NULL, entity_id INTEGER,
    event_type TEXT NOT NULL CHECK(event_type IN ('added','changed','removed')), summary TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sync_run_id) REFERENCES sync_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_change_events_run ON change_events(sync_run_id);
CREATE INDEX IF NOT EXISTS idx_change_events_type ON change_events(event_type);
CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- v0.6: metadatos editoriales externos (TMDB inicialmente).
CREATE TABLE IF NOT EXISTS metadata_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, provider_title TEXT, external_source TEXT NOT NULL,
    external_id TEXT NOT NULL, match_status TEXT NOT NULL CHECK(match_status IN ('matched','review','rejected')), match_score REAL,
    matched_by TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(external_source, external_id), UNIQUE(content_id, external_source),
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metadata_links_content ON metadata_links(content_id);
CREATE INDEX IF NOT EXISTS idx_metadata_links_status ON metadata_links(match_status);
CREATE TABLE IF NOT EXISTS content_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL UNIQUE, source TEXT NOT NULL, external_id TEXT NOT NULL,
    title TEXT, original_title TEXT, overview TEXT, year INTEGER, runtime INTEGER, genres_json TEXT, director TEXT, creators_json TEXT,
    cast_json TEXT, poster_url TEXT, backdrop_url TEXT, rating REAL, raw_json TEXT, language TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_content_metadata_external ON content_metadata(source, external_id);
CREATE TABLE IF NOT EXISTS episode_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER NOT NULL UNIQUE, source TEXT NOT NULL, external_id TEXT, title TEXT,
    overview TEXT, air_date TEXT, runtime INTEGER, still_url TEXT, rating REAL, raw_json TEXT, language TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_episode_metadata_external ON episode_metadata(source, external_id);
CREATE TABLE IF NOT EXISTS person_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT NOT NULL, name TEXT NOT NULL, profile_url TEXT,
    known_for_department TEXT, raw_json TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_person_metadata_name ON person_metadata(name);
"""


def connect() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 120000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
