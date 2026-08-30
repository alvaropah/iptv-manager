from __future__ import annotations

import json
import os
import sqlite3
import unicodedata
from pathlib import Path

DB = Path(os.environ.get('DATABASE_PATH', 'data/iptv_manager.db'))
OUT = Path('preview/preview-data.json')


def clean(s):
    return s if s is not None else ''


def category_map(conn, content_type):
    rows = conn.execute('''
        SELECT id, name, content_type, quality, resolution, dynamic_range,
               audio, subtitles, language_hint
        FROM categories WHERE selected=1 AND content_type=?
        ORDER BY provider_order, name
    ''', (content_type,)).fetchall()
    return [dict(r) for r in rows]


def ids_for(conn, content_id):
    return [r[0] for r in conn.execute(
        'SELECT category_id FROM content_categories WHERE content_id=?', (content_id,)
    )]


def categories_for(conn, content_id):
    return [dict(r) for r in conn.execute('''
        SELECT c.id, c.name, c.quality, c.resolution, c.dynamic_range,
               c.audio, c.subtitles, c.language_hint
        FROM content_categories cc JOIN categories c ON c.id=cc.category_id
        WHERE cc.content_id=? ORDER BY c.name
    ''', (content_id,)).fetchall()]


def versions_for(conn, content_id=None, episode_id=None):
    where = ['v.is_active=1']
    params = []
    if content_id is not None:
        where.append('v.content_id=?'); params.append(content_id)
    if episode_id is not None:
        where.append('v.episode_id=?'); params.append(episode_id)
    rows = conn.execute(f'''
        SELECT v.id, v.category_id, c.name category_name, v.languages language,
               v.quality, v.resolution, v.video_codec, v.audio_codec,
               v.dynamic_range, v.subtitles, v.label,
               COUNT(s.id) stream_count
        FROM versions v JOIN categories c ON c.id=v.category_id
        LEFT JOIN streams s ON s.version_id=v.id AND s.is_active=1
        WHERE {' AND '.join(where)}
        GROUP BY v.id
        ORDER BY CASE v.quality WHEN '8K' THEN 1 WHEN '4K' THEN 2 WHEN '1080p' THEN 3 WHEN '720p' THEN 4 ELSE 9 END,
                 v.label
        LIMIT 20
    ''', params).fetchall()
    return [dict(r) for r in rows]


def main():
    if not DB.exists():
        raise SystemExit(f'No existe {DB}')
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        stats = {
            'movies': conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],
            'series': conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],
            'seasons': conn.execute('SELECT COUNT(*) FROM seasons WHERE is_active=1').fetchone()[0],
            'episodes': conn.execute('SELECT COUNT(*) FROM episodes WHERE is_active=1').fetchone()[0],
            'versions': conn.execute('SELECT COUNT(*) FROM versions WHERE is_active=1').fetchone()[0],
            'streams': conn.execute('SELECT COUNT(*) FROM streams WHERE is_active=1').fetchone()[0],
            'categories': conn.execute('SELECT COUNT(*) FROM categories WHERE selected=1').fetchone()[0],
        }

        cats_movie = category_map(conn, 'movie')
        cats_series = category_map(conn, 'series')
        cat_ids_movie = {c['id'] for c in cats_movie}
        cat_ids_series = {c['id'] for c in cats_series}

        def base_rows(content_type, limit=120):
            rows = conn.execute('''
                SELECT id, canonical_title name, original_title, year, poster_url,
                       backdrop_url, overview
                FROM content
                WHERE content_type=? AND is_active=1
                ORDER BY normalized_title, year DESC, id
                LIMIT ?
            ''', (content_type, limit)).fetchall()
            result=[]
            for r in rows:
                d=dict(r)
                d['overview']=clean(d['overview'])
                d['category_ids']=[x for x in ids_for(conn, d['id']) if x in (cat_ids_movie if content_type=='movie' else cat_ids_series)]
                d['categories']=categories_for(conn, d['id'])[:8]
                d['versions']=versions_for(conn, content_id=d['id'])[:8]
                result.append(d)
            return result

        movies=base_rows('movie')
        series=base_rows('series')

        # Add a compact real series hierarchy for the first 18 series.
        for x in series[:18]:
            seasons=[]
            for s in conn.execute('''
                SELECT id, season_number, name, overview, poster_url
                FROM seasons WHERE series_id=? AND is_active=1
                ORDER BY season_number LIMIT 6
            ''', (x['id'],)).fetchall():
                sd=dict(s)
                eps=[]
                for e in conn.execute('''
                    SELECT id, episode_number, canonical_title title, overview, air_date, poster_url
                    FROM episodes WHERE season_id=? AND is_active=1
                    ORDER BY episode_number LIMIT 18
                ''', (s['id'],)).fetchall():
                    ed=dict(e)
                    ed['version_count']=conn.execute('SELECT COUNT(*) FROM versions WHERE episode_id=? AND is_active=1', (e['id'],)).fetchone()[0]
                    eps.append(ed)
                sd['episodes']=eps
                seasons.append(sd)
            x['seasons']=seasons

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'preview': True,
        'warning': 'Static visual preview. Playback URLs are intentionally excluded.',
        'stats': stats,
        'categories': cats_movie + cats_series,
        'movies': movies,
        'series': series,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Preview generado: {OUT} ({OUT.stat().st_size/1024:.1f} KB)')
    print('Playback URLs: 0 (intencionadamente excluidas)')


if __name__ == '__main__':
    main()
