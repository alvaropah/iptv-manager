from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.tmdb import TMDBClient
from app.db.database import connect, init_db
from app.db.metadata import init_metadata_db
from app.services.metadata import classify_match, extract_year, rank_candidates, save_metadata, search_candidates, title_queries


def save_episode_metadata(conn, row, result):
    external_id = str(result["id"])
    still_path = result.get("still_path")
    still_url = f"https://image.tmdb.org/t/p/w780{still_path}" if still_path else None

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

    conn.execute("DELETE FROM metadata_links WHERE episode_id=? AND external_source='tmdb'", (row["episode_id"],))
    conn.execute(
        """INSERT INTO metadata_links
        (episode_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
        VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(external_source, external_id) DO UPDATE SET
          episode_id=excluded.episode_id,
          provider_title=excluded.provider_title,
          match_status=excluded.match_status,
          match_score=excluded.match_score,
          matched_by=excluded.matched_by,
          updated_at=CURRENT_TIMESTAMP""",
        (row["episode_id"], row["provider_title"], "tmdb", external_id, "matched", 1.0,
         "series_id+season_number+episode_number"),
    )


def resolve_series_tmdb_id(conn, client: TMDBClient, series_id: int, cache: dict[int, str | None]) -> str | None:
    """Return the TMDB series id, resolving the series when the catalog lacks it.

    The persistent catalog is deliberately independent from the metadata workflow.
    Therefore episode enrichment cannot require content_metadata to already exist:
    that was the reason the previous implementation selected zero episodes.
    """
    if series_id in cache:
        return cache[series_id]

    existing = conn.execute(
        "SELECT external_id FROM content_metadata WHERE content_id=? AND source='tmdb'",
        (series_id,),
    ).fetchone()
    if existing and existing["external_id"]:
        cache[series_id] = str(existing["external_id"])
        return cache[series_id]

    linked = conn.execute(
        """SELECT external_id FROM metadata_links
           WHERE content_id=? AND external_source='tmdb' AND match_status='matched'
           ORDER BY updated_at DESC LIMIT 1""",
        (series_id,),
    ).fetchone()
    if linked and linked["external_id"]:
        cache[series_id] = str(linked["external_id"])
        return cache[series_id]

    row = conn.execute(
        """SELECT id,content_type,canonical_title,original_title,year
           FROM content WHERE id=? AND content_type='series' AND is_active=1""",
        (series_id,),
    ).fetchone()
    if not row:
        cache[series_id] = None
        return None

    year = extract_year(row["canonical_title"], row["year"])
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
        return None

    ranked = rank_candidates(client, "series", row["canonical_title"], year, candidates)
    score, candidate = ranked[0]
    status = classify_match(score)
    if status != "matched":
        print(f"    SERIES {status.upper()} | {row['canonical_title']} | score={score:.2f} | query={query_used}", flush=True)
        cache[series_id] = None
        return None

    detail = client.tv(candidate["id"])
    save_metadata(conn, row, detail, score, status)
    conn.commit()
    tmdb_id = str(detail["id"])
    cache[series_id] = tmdb_id
    print(f"    SERIES MATCHED | {row['canonical_title']} -> {detail.get('name') or '?'} | score={score:.2f} | tmdb={tmdb_id}", flush=True)
    return tmdb_id


def main():
    parser = argparse.ArgumentParser(description="Enriquece episodios con metadata de TMDB")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--refresh", action="store_true")
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
        if not args.refresh:
            where += " AND em.episode_id IS NULL"
        rows = conn.execute(
            f"""SELECT e.id AS episode_id, e.canonical_title AS provider_title,
                       c.id AS series_id, s.season_number, e.episode_number
                FROM episodes e
                JOIN seasons s ON s.id=e.season_id
                JOIN content c ON c.id=s.series_id
                LEFT JOIN episode_metadata em ON em.episode_id=e.id
                WHERE {where}
                ORDER BY e.id LIMIT ?""", (args.limit,),
        ).fetchall()

        matched = errors = pending = series_matches = series_unresolved = 0
        series_cache: dict[int, str | None] = {}

        for index, row in enumerate(rows, 1):
            try:
                tmdb_series_id = resolve_series_tmdb_id(conn, client, int(row["series_id"]), series_cache)
                if not tmdb_series_id:
                    pending += 1
                    print(f"[{index}/{len(rows)}] PENDING | {row['provider_title']} | serie_id={row['series_id']} | sin TMDB series", flush=True)
                    continue

                if int(row["series_id"]) not in series_cache or series_cache[int(row["series_id"])] == tmdb_series_id:
                    if sum(1 for value in series_cache.values() if value == tmdb_series_id) == 1:
                        series_matches += 1

                result = client.episode(int(tmdb_series_id), int(row["season_number"]), int(row["episode_number"]))
                save_episode_metadata(conn, row, result)
                conn.commit()
                matched += 1
                print(f"[{index}/{len(rows)}] MATCHED | {row['provider_title']} -> {result.get('name') or '?'} | S{row['season_number']:02d}E{row['episode_number']:02d} | tmdb_series={tmdb_series_id}", flush=True)
            except Exception as exc:
                errors += 1
                print(f"[{index}/{len(rows)}] ERROR | episode={row['episode_id']} | {exc}", flush=True)

        print(f"RESUMEN | matched={matched} errors={errors} pending={pending} series_resolved={series_matches} series_unresolved={series_unresolved}", flush=True)


if __name__ == "__main__":
    main()
