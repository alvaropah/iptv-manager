from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.tmdb import TMDBClient
from app.db.database import connect
from app.services.metadata import classify_match, extract_year, score_candidate, title_queries


def save_metadata(conn, row, result, score, status):
    tmdb_id = str(result["id"])
    is_movie = row["content_type"] == "movie"
    credits = result.get("credits") or {}
    crew = credits.get("crew") or []
    directors = [p.get("name") for p in crew if p.get("job") == "Director"]
    creators = [p.get("name") for p in result.get("created_by") or []]
    cast = [{k: p.get(k) for k in ("id", "name", "character", "profile_path")} for p in (credits.get("cast") or [])[:20]]
    genres = [g.get("name") for g in result.get("genres") or []]
    poster_path = result.get("poster_path")
    backdrop_path = result.get("backdrop_path")
    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
    backdrop = f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else None
    title = result.get("title") if is_movie else result.get("name")
    original = result.get("original_title") if is_movie else result.get("original_name")
    date = result.get("release_date") if is_movie else result.get("first_air_date")
    year = int(date[:4]) if date and date[:4].isdigit() else None
    conn.execute("""INSERT INTO metadata_links(content_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
      VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(content_id,external_source) DO UPDATE SET provider_title=excluded.provider_title,external_id=excluded.external_id,match_status=excluded.match_status,match_score=excluded.match_score,matched_by=excluded.matched_by,updated_at=CURRENT_TIMESTAMP""",
      (row["id"], row["canonical_title"], "tmdb", tmdb_id, status, score, "clean_title+year+multilang"))
    if status != "matched":
        return
    runtime = result.get("runtime") if is_movie else ((result.get("episode_run_time") or [None])[0])
    conn.execute("""INSERT INTO content_metadata(content_id,source,external_id,title,original_title,overview,year,runtime,genres_json,director,creators_json,cast_json,poster_url,backdrop_url,rating,raw_json,language,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(content_id) DO UPDATE SET source=excluded.source,external_id=excluded.external_id,title=excluded.title,original_title=excluded.original_title,overview=excluded.overview,year=excluded.year,runtime=excluded.runtime,genres_json=excluded.genres_json,director=excluded.director,creators_json=excluded.creators_json,cast_json=excluded.cast_json,poster_url=excluded.poster_url,backdrop_url=excluded.backdrop_url,rating=excluded.rating,raw_json=excluded.raw_json,language=excluded.language,updated_at=CURRENT_TIMESTAMP""",
      (row["id"], "tmdb", tmdb_id, title, original, result.get("overview"), year, runtime, json.dumps(genres, ensure_ascii=False), ", ".join(x for x in directors if x), json.dumps(creators, ensure_ascii=False), json.dumps(cast, ensure_ascii=False), poster, backdrop, result.get("vote_average"), json.dumps(result, ensure_ascii=False), settings.tmdb_language))


def search_candidates(client, content_type, query, year):
    """Search in Spanish first, then English so titles whose TMDB display name is non-Latin are recoverable."""
    search = client.search_movie if content_type == "movie" else client.search_tv
    candidates = []
    seen = set()
    # Spanish is preferred because it gives us Spanish-facing metadata.
    for language in (settings.tmdb_language, "en-US"):
        for use_year in (True, False):
            found = search(query, year if use_year else None, language=language)
            for item in found:
                if item.get("id") not in seen:
                    candidates.append(item)
                    seen.add(item.get("id"))
            if found:
                # Keep the remaining language as a fallback, but don't hammer the API
                # with a year/no-year pair once a good result set exists.
                break
    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--type", choices=["movie", "series"], default=None)
    args = parser.parse_args()
    token = settings.tmdb_api_token or os.getenv("TMDB_API_TOKEN", "")
    if not token:
        raise SystemExit("TMDB_API_TOKEN no está configurado")
    client = TMDBClient(token, settings.tmdb_language)
    with connect() as conn:
        clauses = ["c.is_active=1"]
        params: list[object] = []
        if args.type:
            clauses.append("c.content_type=?")
            params.append(args.type)
        rows = conn.execute(f"SELECT c.id,c.content_type,c.canonical_title,c.original_title,c.year FROM content c WHERE {' AND '.join(clauses)} ORDER BY c.id LIMIT ?", [*params, args.limit]).fetchall()
        matched = review = rejected = no_candidates = errors = 0
        for index, row in enumerate(rows, 1):
            try:
                year = extract_year(row["canonical_title"], row["year"])
                queries = title_queries(row["canonical_title"], year, row["original_title"])
                all_candidates = []
                query_used = None
                for query in queries:
                    query_used = query
                    all_candidates = search_candidates(client, row["content_type"], query, year)
                    if all_candidates:
                        break
                if not all_candidates:
                    no_candidates += 1
                    print(f"[{index}/{len(rows)}] NO MATCH | proveedor={row['canonical_title']} | consulta={query_used}")
                    continue
                ranked = sorted(((score_candidate(row["canonical_title"], year, c), c) for c in all_candidates), key=lambda x: x[0], reverse=True)
                score, candidate = ranked[0]
                status = classify_match(score)
                detail = client.movie(candidate["id"]) if row["content_type"] == "movie" else client.tv(candidate["id"])
                save_metadata(conn, row, detail, score, status)
                if status == "matched": matched += 1
                elif status == "review": review += 1
                else: rejected += 1
                display = detail.get("title") or detail.get("name") or "?"
                lang = "en-US" if candidate in [] else ""
                print(f"[{index}/{len(rows)}] {status.upper()} | {row['canonical_title']} -> {display} | score={score:.2f} | query={query_used}")
                if index % 10 == 0:
                    conn.commit()
                time.sleep(0.05)
            except Exception as exc:
                errors += 1
                print(f"[{index}/{len(rows)}] ERROR | content={row['id']} | {exc}")
        conn.commit()
        print(f"RESUMEN | matched={matched} review={review} rejected={rejected} no_candidates={no_candidates} errors={errors}")


if __name__ == "__main__":
    main()
