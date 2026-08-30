from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.metadata import init_metadata_db
from app.services.metadata import classify_match, score_candidate


def test_provider_suffix_matching():
    candidate = {
        'id': 123,
        'name': 'Arpo',
        'original_name': 'Arpo',
        'first_air_date': '2019-10-29',
        'origin_country': ['US'],
    }
    score = score_candidate('AMZ - Arpo (2022) (PT)', 2022, candidate, 'PT')
    assert score >= 0.96, score
    assert classify_match(score) == 'matched'


def test_expanded_tmdb_title_matching():
    candidate = {
        'id': 478009,
        'name': 'ARPO: Robot Babysitter',
        'original_name': 'ARPO: Robot Babysitter',
        'first_air_date': '2021-11-01',
        'origin_country': ['US'],
    }
    score = score_candidate('AMZ - Arpo (2022) (PT)', 2022, candidate, 'PT')
    assert score >= 0.90, score
    assert classify_match(score) == 'matched'


def test_wrong_installment_still_rejected():
    candidate = {
        'id': 456,
        'name': 'Example Show 2',
        'original_name': 'Example Show 2',
        'first_air_date': '2022-01-01',
    }
    score = score_candidate('Example Show 1', 2022, candidate)
    assert score < 0.62, score


def main():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_metadata_db(conn)
    conn.executescript("""
    CREATE TABLE content (id INTEGER PRIMARY KEY, content_type TEXT, canonical_title TEXT, original_title TEXT, year INTEGER, overview TEXT, poster_url TEXT, backdrop_url TEXT, first_seen_at TEXT, last_seen_at TEXT, last_detail_sync_at TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE seasons (id INTEGER PRIMARY KEY, series_id INTEGER, season_number INTEGER, name TEXT, overview TEXT, poster_url TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE episodes (id INTEGER PRIMARY KEY, season_id INTEGER, episode_number INTEGER, canonical_title TEXT, overview TEXT, air_date TEXT, poster_url TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, provider_category_id TEXT, quality TEXT, resolution TEXT, dynamic_range TEXT, audio TEXT, subtitles TEXT, language_hint TEXT, content_type TEXT, selected INTEGER DEFAULT 1, provider_order INTEGER DEFAULT 0);
    CREATE TABLE versions (id INTEGER PRIMARY KEY, content_id INTEGER, episode_id INTEGER, category_id INTEGER, languages TEXT, quality TEXT, resolution TEXT, video_codec TEXT, audio_codec TEXT, dynamic_range TEXT, subtitles TEXT, label TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE streams (id INTEGER PRIMARY KEY, version_id INTEGER, provider_stream_id TEXT, stream_url TEXT, container_extension TEXT, original_name TEXT, is_active INTEGER DEFAULT 1);
    INSERT INTO content VALUES (1,'series','Provider Show','Original Show',2024,NULL,NULL,NULL,NULL,NULL,NULL,1);
    INSERT INTO seasons VALUES (10,1,1,'Season 1',NULL,NULL,1);
    INSERT INTO episodes VALUES (100,10,1,'Provider Episode','Provider overview','2024-01-01',NULL,1);
    INSERT INTO categories VALUES (1,'HD','1','1080p','1920x1080','SDR','AAC','ES','es','series',1,1);
    INSERT INTO versions VALUES (1,NULL,100,1,'es','1080p','1920x1080','H264','AAC','SDR','ES','HD',1);
    INSERT INTO streams VALUES (1,1,'source','https://example.test/ep.m3u8','m3u8','Provider Episode',1);
    INSERT INTO episode_metadata VALUES (100,'tmdb','999','Título del episodio','Sinopsis TMDB','2024-01-01',45,'https://image.tmdb.org/t/p/w780/still.jpg','{}','es-ES',CURRENT_TIMESTAMP);
    """)
    row = conn.execute("SELECT title,overview,still_url,runtime FROM episode_metadata WHERE episode_id=100").fetchone()
    assert row[0] == 'Título del episodio'
    assert row[1] == 'Sinopsis TMDB'
    assert row[2].endswith('/still.jpg')
    assert row[3] == 45
    test_provider_suffix_matching()
    test_expanded_tmdb_title_matching()
    test_wrong_installment_still_rejected()
    print('OK | episode_metadata contract | title suffix/head matching')


if __name__ == '__main__':
    main()
