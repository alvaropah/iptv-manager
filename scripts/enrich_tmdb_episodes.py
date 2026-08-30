from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.tmdb import TMDBClient
from app.db.database import connect, init_db
from app.db.metadata import init_metadata_db
from app.services.metadata import classify_match, extract_country, extract_year, title_queries
from scripts.enrich_tmdb import rank_candidates, save_metadata, search_candidates


def save_episode_metadata(conn, row, result):
    external_id = str(result["id"])
    still_path = result.get("still_path")
    still_url = f"https://image.tmdb.org/t/p/w780{still_path}" if still_path else None
    conn.execute("DELETE FROM metadata_links WHERE episode_id=? AND external_source='tmdb'", (row["episode_id"],))
    conn.execute(
        """INSERT INTO episode_metadata
        (episode_id,source,external_id,title,overview,air_date,runtime,still_url,raw_json,language,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(episode_id) DO UPDATE SET
          source=excluded.source, external_id=excluded.external_id,
          title=excluded.title, overview=excluded.overview,
          air_date=excluded.air_date, runtime=excluded.runtime,
          still_url=excluded.still_url, raw_json=excluded.raw_json,
          language=excluded.language, updated_at=CURRENT_TIMESTAMP""",
        (row["episode_id"], "tmdb", external_id, result.get("name"), result.get("overview"),
         result.get("air_date"), result.get("runtime"), still_url,
         json.dumps(result, ensure_ascii=False), settings.tmdb_language),
    )
    conn.execute("""DELETE FROM metadata_links WHERE external_source='tmdb' AND external_id=?""", (external_id,))
    conn.execute(
        """INSERT INTO metadata_links
        (episode_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
        VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (row["episode_id"], row["provider_title"], "tmdb", external_id, "matched", 1.0,
         "series_id+season_number+episode_number"),
    )


def resolve_series_tmdb_id(conn: object, client: TMDBClient, series_id: int, cache: dict[int, str | None], diagnostic: bool = False) -> tuple[str | None, bool]:
    """Return (TMDB series id, newly_resolved)."""
    if series_id in cache:
        return cache[series_id], False

    existing = conn.execute(
        "SELECT external_id FROM content_metadata WHERE content_id=? AND source='tmdb'",
        (series_id,),
    ).fetchone()
    if existing and existing["external_id"]:
        cache[series_id] = str(existing["external_id"])
        print(f"    SERIES CACHE/DB | serie_id={series_id} | tmdb={cache[series_id]}", flush=True) if diagnostic else None
        return cache[series_id], False

    linked = conn.execute(
        """SELECT external_id FROM metadata_links
           WHERE content_id=? AND external_source='tmdb' AND match_status='matched'
           ORDER BY updated_at DESC LIMIT 1""",
        (series_id,),
    ).fetchone()
    if linked and linked["external_id"]:
        cache[series_id] = str(linked["external_id"])
        print(f"    SERIES LINK | serie_id={series_id} | tmdb={cache[series_id]}", flush=True) if diagnostic else None
        return cache[series_id], False

    row = conn.execute(
        """SELECT id,content_type,canonical_title,original_title,year
           FROM content WHERE id=? AND content_type='series' AND is_active=1""",
        (series_id,),
    ).fetchone()
    if not row:
        cache[series_id] = None
        return None, True

    year = extract_year(row["canonical_title"], row["year"])
    country = extract_country(row["canonical_title"])
    queries = title_queries(row["canonical_title"], year, row["original_title"])
    candidates: list[dict] = []
    query_used = None
    for query in queries:
        query_used = query
        candidates = search_candidates(client, "series", query, year)
        if candidates:
            break

    if not candidates:
        print(f"    SERIES NO MATCH | {row['canonical_title']} | query={query_used}", flush=True)
        cache[series_id] = None
        return None, True

    ranked = rank_candidates(client, "series", row["canonical_title"], year, candidates, country, diagnostic=diagnostic)
    score, candidate = ranked[0]
    status = classify_match(score)
    if status != "matched":
        print(f"    SERIES {status.upper()} | {row['canonical_title']} | score={score:.2f} | country={country or '?'} | query={query_used}", flush=True)
        cache[series_id] = None
        return None, True

    detail = client.tv(candidate["id"])
    save_metadata(conn, row, detail, score, status)
    conn.commit()
    tmdb_id = str(detail["id"])
    cache[series_id] = tmdb_id
    print(f"    SERIES MATCHED | {row['canonical_title']} -> {detail.get('name') or '?'} | score={score:.2f} | tmdb={tmdb_id}", flush=True)
    return tmdb_id, True


def _http_status(exc: Exception) -> int | None:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code
    return None


def main():
    parser = argparse.ArgumentParser(description="Enriquece episodios con metadata de TMDB")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--series-id", type=int, default=None, help="Procesa únicamente una serie concreta")
    parser.add_argument("--diagnostic", action="store_true", help="Muestra candidatos y señales de matching")
    args = parser.parse_args()

    token = settings.tmdb_api_token or os.getenv("TMDB_API_TOKEN", "")
    if not token:
        raise SystemExit("TMDB_API_TOKEN no está configurado")

    init_db()
    with connect() as conn:
        init_metadata_db(conn)
        conn.commit()
        client = TMDBClient(token, settings.tmdb_language)
        where = "e.is_active=1 AND c.is_active=1"
        params: list[object] = []
        if not args.refresh:
            where += " AND em.episode_id IS NULL"
        if args.series_id is not None:
            where += " AND c.id=?"
            params.append(args.series_id)
        rows = conn.execute(
            f"""SELECT e.id AS episode_id, e.canonical_title AS provider_title,
                       c.id AS series_id, s.season_number, e.episode_number
                FROM episodes e
                JOIN seasons s ON s.id=e.season_id
                JOIN content c ON c.id=s.series_id
                LEFT JOIN episode_metadata em ON em.episode_id=e.id
                WHERE {where}
                ORDER BY s.season_number,e.episode_number,e.id LIMIT ?""", (*params, args.limit),
        ).fetchall()

        if args.series_id is not None:
            print(f"PREFLIGHT | series_id={args.series_id} | episodes_selected={len(rows)} | limit={args.limit} | refresh={args.refresh}", flush=True)
        else:
            print(f"PREFLIGHT | episodes_selected={len(rows)} | limit={args.limit} | refresh={args.refresh}", flush=True)

        matched = errors = pending = series_resolved = series_unresolved = 0
        series_cache: dict[int, str | None] = {}

        for index, row in enumerate(rows, 1):
            try:
                tmdb_series_id, newly_resolved = resolve_series_tmdb_id(conn, client, int(row["series_id"]), series_cache, diagnostic=args.diagnostic)
                if newly_resolved:
                    if tmdb_series_id:
                        series_resolved += 1
                    else:
                        series_unresolved += 1
                if not tmdb_series_id:
                    pending += 1
                    print(f"[{index}/{len(rows)}] PENDING | {row['provider_title']} | serie_id={row['series_id']} | sin TMDB series", flush=True)
                    continue
                try:
                    result = client.episode(int(tmdb_series_id), int(row["season_number"]), int(row["episode_number"]))
                except requests.HTTPError as exc:
                    status = _http_status(exc)
                    if status == 404:
                        pending += 1
                        print(f"[{index}/{len(rows)}] PENDING | {row['provider_title']} | TMDB episode inexistente S{row['season_number']:02d}E{row['episode_number']:02d} | tmdb_series={tmdb_series_id}", flush=True)
                        conn.rollback()
                        continue
                    raise
                save_episode_metadata(conn, row, result)
                conn.commit()
                matched += 1
                print(f"[{index}/{len(rows)}] MATCHED | {row['provider_title']} -> {result.get('name') or '?'} | S{row['season_number']:02d}E{row['episode_number']:02d} | tmdb_series={tmdb_series_id}", flush=True)
            except Exception as exc:
                conn.rollback()
                errors += 1
                status = _http_status(exc)
                detail = f"HTTP {status}" if status else f"{type(exc).__name__}: {exc}"
                print(f"[{index}/{len(rows)}] ERROR | episode={row['episode_id']} | {detail}", flush=True)
        print(f"RESUMEN | matched={matched} errors={errors} pending={pending} series_resolved={series_resolved} series_unresolved={series_unresolved}", flush=True)


if __name__ == "__main__":
    main()
