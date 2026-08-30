from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.db.database import connect


def _normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _page(page: int, page_size: int, total: int) -> dict[str, int]:
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


def get_stats() -> dict[str, int]:
    with connect() as conn:
        return {
            "movies": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],
            "series": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],
            "seasons": conn.execute("SELECT COUNT(*) FROM seasons WHERE is_active=1").fetchone()[0],
            "episodes": conn.execute("SELECT COUNT(*) FROM episodes WHERE is_active=1").fetchone()[0],
            "versions": conn.execute("SELECT COUNT(*) FROM versions WHERE is_active=1").fetchone()[0],
            "streams": conn.execute("SELECT COUNT(*) FROM streams WHERE is_active=1").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0],
        }


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
                ORDER BY content_type, provider_order, name""", params).fetchall()
    return [dict(row) for row in rows]


def list_catalog(content_type: str, page: int = 1, page_size: int = 40, category_id: int | None = None, q: str | None = None) -> dict[str, Any]:
    clauses = ["c.content_type=?", "c.is_active=1"]
    params: list[Any] = [content_type]
    if category_id is not None:
        clauses.append("EXISTS (SELECT 1 FROM content_categories cc WHERE cc.content_id=c.id AND cc.category_id=?)")
        params.append(category_id)
    if q:
        clauses.append("c.normalized_title LIKE ?")
        params.append(f"%{_normalize_search(q)}%")
    where = " AND ".join(clauses)
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM content c WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""SELECT c.id, c.content_type, c.canonical_title AS name, c.original_title,
                       c.year, c.poster_url, c.backdrop_url
                FROM content c WHERE {where}
                ORDER BY c.normalized_title, c.year DESC, c.id LIMIT ? OFFSET ?""",
            [*params, page_size, offset]).fetchall()
    return {"items": [dict(r) for r in rows], **_page(page, page_size, total)}


def search_catalog(query: str, limit: int = 50, content_type: str | None = None, page: int = 1, page_size: int | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    q = f"%{_normalize_search(query)}%"
    clauses = ["is_active=1", "normalized_title LIKE ?"]
    params: list[Any] = [q]
    if content_type:
        clauses.append("content_type=?")
        params.append(content_type)
    with connect() as conn:
        if page_size is None:
            rows = conn.execute(f"""SELECT id, content_type, canonical_title AS name, original_title, year, poster_url
                FROM content WHERE {' AND '.join(clauses)} ORDER BY normalized_title, year DESC LIMIT ?""", [*params, limit]).fetchall()
            return [dict(row) for row in rows]
        total = conn.execute(f"SELECT COUNT(*) FROM content WHERE {' AND '.join(clauses)}", params).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(f"""SELECT id, content_type, canonical_title AS name, original_title, year, poster_url, backdrop_url
            FROM content WHERE {' AND '.join(clauses)} ORDER BY normalized_title, year DESC, id LIMIT ? OFFSET ?""", [*params, page_size, offset]).fetchall()
    return {"items": [dict(row) for row in rows], **_page(page, page_size, total), "query": query}


def _version_rows(conn, content_id: int | None = None, episode_id: int | None = None) -> list[dict[str, Any]]:
    clauses = ["v.is_active=1"]
    params: list[Any] = []
    if content_id is not None:
        clauses.append("v.content_id=?"); params.append(content_id)
    if episode_id is not None:
        clauses.append("v.episode_id=?"); params.append(episode_id)
    rows = conn.execute(f"""SELECT v.id, v.category_id, c.name AS category_name,
                   v.languages AS language, v.quality, v.resolution, v.video_codec,
                   v.audio_codec, v.dynamic_range, v.languages, v.subtitles, v.label,
                   s.id AS stream_db_id, s.provider_stream_id AS source_id,
                   s.stream_url AS playback_url, s.container_extension AS container, s.original_name
            FROM versions v JOIN categories c ON c.id=v.category_id
            LEFT JOIN streams s ON s.version_id=v.id AND s.is_active=1
            WHERE {' AND '.join(clauses)}
            ORDER BY CASE v.quality WHEN '8K' THEN 1 WHEN '4K' THEN 2 WHEN '1080p' THEN 3 WHEN '720p' THEN 4 ELSE 9 END,
                     v.dynamic_range DESC, v.label""", params).fetchall()
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        d = dict(row); vid = d.pop("id")
        item = grouped.get(vid)
        if item is None:
            keys = ("category_id","category_name","language","quality","resolution","video_codec","audio_codec","dynamic_range","languages","subtitles","label")
            item = {"id": vid, **{k: d[k] for k in keys}, "streams": []}; grouped[vid] = item
        if d.get("stream_db_id") is not None:
            item["streams"].append({"id": d["stream_db_id"], "source_id": d["source_id"], "playback_url": d["playback_url"], "container": d["container"], "original_name": d["original_name"]})
    return list(grouped.values())


def get_content(content_id: int, content_type: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("""SELECT id, content_type, canonical_title AS title, original_title, year, overview,
                      poster_url, backdrop_url, first_seen_at, last_seen_at, last_detail_sync_at
               FROM content WHERE id=? AND content_type=? AND is_active=1""", (content_id, content_type)).fetchone()
        if row is None: return None
        result = dict(row)
        result["categories"] = [dict(r) for r in conn.execute("""SELECT c.id, c.name, c.provider_category_id, c.quality,
                          c.resolution, c.dynamic_range, c.audio, c.subtitles, c.language_hint
                   FROM content_categories cc JOIN categories c ON c.id=cc.category_id WHERE cc.content_id=? ORDER BY c.name""", (content_id,)).fetchall()]
        result["versions"] = _version_rows(conn, content_id=content_id)
        return result


def get_series_seasons(series_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        seasons = conn.execute("SELECT id, season_number, name, overview, poster_url FROM seasons WHERE series_id=? AND is_active=1 ORDER BY season_number", (series_id,)).fetchall()
        output = []
        for season in seasons:
            data = dict(season); episodes = conn.execute("SELECT id, episode_number, canonical_title AS title, overview, air_date, poster_url FROM episodes WHERE season_id=? AND is_active=1 ORDER BY episode_number", (season["id"],)).fetchall()
            data["episodes"] = []
            for episode in episodes:
                ep = dict(episode); ep["versions"] = _version_rows(conn, episode_id=episode["id"]); data["episodes"].append(ep)
            output.append(data)
        return output


def get_episode(episode_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("""SELECT e.id, e.episode_number, e.canonical_title AS title, e.overview, e.air_date,
                      e.poster_url, s.id AS season_id, s.season_number, s.series_id, c.canonical_title AS series_title
               FROM episodes e JOIN seasons s ON s.id=e.season_id JOIN content c ON c.id=s.series_id
               WHERE e.id=? AND e.is_active=1""", (episode_id,)).fetchone()
        if row is None: return None
        result = dict(row); result["versions"] = _version_rows(conn, episode_id=episode_id); return result
