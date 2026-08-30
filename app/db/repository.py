from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.db.database import connect


def _normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value.casefold()).strip()


def get_stats() -> dict[str, int]:
    with connect() as conn:
        counts = {
            "movies": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],
            "series": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],
            "seasons": conn.execute("SELECT COUNT(*) FROM seasons WHERE is_active=1").fetchone()[0],
            "episodes": conn.execute("SELECT COUNT(*) FROM episodes WHERE is_active=1").fetchone()[0],
            "versions": conn.execute("SELECT COUNT(*) FROM versions WHERE is_active=1").fetchone()[0],
            "streams": conn.execute("SELECT COUNT(*) FROM streams WHERE is_active=1").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0],
        }
        return counts


def get_categories(content_type: str | None = None, selected_only: bool = True) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if content_type:
        clauses.append("content_type=?")
        params.append(content_type)
    if selected_only:
        clauses.append("selected=1")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT id, provider_category_id, name, content_type, selected,
                       quality, resolution, dynamic_range, audio, subtitles, language_hint
                FROM categories{where}
                ORDER BY content_type, provider_order, name""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def search_catalog(query: str, limit: int = 50, content_type: str | None = None) -> list[dict[str, Any]]:
    q = f"%{_normalize_search(query)}%"
    clauses = ["is_active=1", "normalized_title LIKE ?"]
    params: list[Any] = [q]
    if content_type:
        clauses.append("content_type=?")
        params.append(content_type)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT id, content_type, canonical_title AS name, original_title,
                       year, poster_url
                FROM content
                WHERE {' AND '.join(clauses)}
                ORDER BY normalized_title, year DESC LIMIT ?""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _version_rows(conn, content_id: int | None = None, episode_id: int | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = ["v.is_active=1"]
    params: list[Any] = []
    if content_id is not None:
        clauses.append("v.content_id=?")
        params.append(content_id)
    if episode_id is not None:
        clauses.append("v.episode_id=?")
        params.append(episode_id)
    rows = conn.execute(
        f"""SELECT v.id, v.category_id, c.name AS category_name,
                   v.languages AS language, v.quality, v.resolution, v.video_codec,
                   v.audio_codec, v.dynamic_range, v.languages, v.subtitles, v.label,
                   s.id AS stream_db_id, s.provider_stream_id AS source_id,
                   s.stream_url AS playback_url, s.container_extension AS container,
                   s.original_name
            FROM versions v
            JOIN categories c ON c.id=v.category_id
            LEFT JOIN streams s ON s.version_id=v.id AND s.is_active=1
            WHERE {' AND '.join(clauses)}
            ORDER BY
              CASE v.quality WHEN '8K' THEN 1 WHEN '4K' THEN 2 WHEN '1080p' THEN 3 WHEN '720p' THEN 4 ELSE 9 END,
              v.dynamic_range DESC, v.label""",
        params,
    ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        d = dict(row)
        vid = d.pop("id")
        item = grouped.get(vid)
        if item is None:
            item = {"id": vid, **{k: d[k] for k in ("category_id", "category_name", "language", "quality", "resolution", "video_codec", "audio_codec", "dynamic_range", "languages", "subtitles", "label")}, "streams": []}
            grouped[vid] = item
        if d.get("stream_db_id") is not None:
            item["streams"].append({
                "id": d["stream_db_id"],
                "source_id": d["source_id"],
                "playback_url": d["playback_url"],
                "container": d["container"],
                "original_name": d["original_name"],
            })
    return list(grouped.values())


def get_content(content_id: int, content_type: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT id, content_type, canonical_title AS title, original_title, year,
                      overview, poster_url, backdrop_url, first_seen_at, last_seen_at,
                      last_detail_sync_at
               FROM content WHERE id=? AND content_type=? AND is_active=1""",
            (content_id, content_type),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["categories"] = [
            dict(r) for r in conn.execute(
                """SELECT c.id, c.name, c.provider_category_id, c.quality, c.resolution,
                          c.dynamic_range, c.audio, c.subtitles, c.language_hint
                   FROM content_categories cc JOIN categories c ON c.id=cc.category_id
                   WHERE cc.content_id=? ORDER BY c.name""",
                (content_id,),
            ).fetchall()
        ]
        result["versions"] = _version_rows(conn, content_id=content_id)
        return result


def get_series_seasons(series_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        seasons = conn.execute(
            """SELECT id, season_number, name, overview, poster_url
               FROM seasons WHERE series_id=? AND is_active=1 ORDER BY season_number""",
            (series_id,),
        ).fetchall()
        output: list[dict[str, Any]] = []
        for season in seasons:
            season_data = dict(season)
            episodes = conn.execute(
                """SELECT id, episode_number, canonical_title AS title, overview, air_date, poster_url
                   FROM episodes WHERE season_id=? AND is_active=1 ORDER BY episode_number""",
                (season["id"],),
            ).fetchall()
            season_data["episodes"] = []
            for episode in episodes:
                ep = dict(episode)
                ep["versions"] = _version_rows(conn, episode_id=episode["id"])
                season_data["episodes"].append(ep)
            output.append(season_data)
        return output


def get_episode(episode_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT e.id, e.episode_number, e.canonical_title AS title, e.overview,
                      e.air_date, e.poster_url, s.id AS season_id, s.season_number,
                      s.series_id, c.canonical_title AS series_title
               FROM episodes e
               JOIN seasons s ON s.id=e.season_id
               JOIN content c ON c.id=s.series_id
               WHERE e.id=? AND e.is_active=1""",
            (episode_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["versions"] = _version_rows(conn, episode_id=episode_id)
        return result
