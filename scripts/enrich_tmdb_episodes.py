from __future__ import annotations

import argparse
import difflib
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
from app.core.tvmaze import TVMazeClient
from app.db.database import connect, init_db
from app.db.metadata import init_metadata_db
from app.services.metadata import classify_match, extract_country, extract_year, title_queries
from scripts.enrich_tmdb import rank_candidates, save_metadata, search_candidates


def save_episode_metadata(
    conn,
    row,
    result,
    matched_by="series_id+season_number+episode_number",
    source="tmdb",
    language=None,
):
    """Persist episode metadata without assuming TMDB is the only provider."""
    external_id = str(result["id"])
    still_url = None
    if source == "tmdb":
        still_path = result.get("still_path")
        still_url = f"https://image.tmdb.org/t/p/w780{still_path}" if still_path else None
    elif source == "tvmaze":
        image = result.get("image") or {}
        still_url = image.get("original") or image.get("medium")

    conn.execute(
        "DELETE FROM metadata_links WHERE episode_id=? AND external_source=?",
        (row["episode_id"], source),
    )
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
        (
            row["episode_id"],
            source,
            external_id,
            result.get("name"),
            result.get("overview") if source == "tmdb" else result.get("summary"),
            result.get("air_date") if source == "tmdb" else result.get("airdate"),
            result.get("runtime"),
            still_url,
            json.dumps(result, ensure_ascii=False),
            language or (settings.tmdb_language if source == "tmdb" else "en"),
        ),
    )
    conn.execute(
        "DELETE FROM metadata_links WHERE external_source=? AND external_id=?",
        (source, external_id),
    )
    conn.execute(
        """INSERT INTO metadata_links
        (episode_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
        VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (
            row["episode_id"],
            row["provider_title"],
            source,
            external_id,
            "matched",
            1.0,
            matched_by,
        ),
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


def _clean_title(value: str | None) -> str:
    value = (value or "").lower()
    for token in ("(us)", "(uk)", "(gb)", "(pt)", "(es)", "(jp)", "(au)"):
        value = value.replace(token, " ")
    return " ".join(ch if ch.isalnum() else " " for ch in value).split().__str__().strip()


def _title_score(left: str, right: str) -> float:
    a = _clean_title(left)
    b = _clean_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def resolve_tvmaze_show_id(
    client: TVMazeClient,
    provider_title: str,
    cache: dict[str, int | None],
    diagnostic: bool = False,
) -> tuple[int | None, float]:
    """Find a high-confidence TVmaze show id once per provider title."""
    key = _clean_title(provider_title)
    if key in cache:
        return cache[key], 1.0 if cache[key] else 0.0

    year = extract_year(provider_title, None)
    best_id: int | None = None
    best_score = 0.0
    query_used = None
    for query in title_queries(provider_title, year, None):
        query_used = query
        try:
            candidates = client.search_shows(query)
        except requests.HTTPError:
            candidates = []
        if not candidates:
            continue
        for item in candidates:
            show = item.get("show") or {}
            name = show.get("name") or ""
            score = _title_score(provider_title, name)
            premiered = str(show.get("premiered") or "")[:4]
            if year and premiered == str(year):
                score = min(1.0, score + 0.03)
            if score > best_score:
                best_score = score
                best_id = int(show["id"])
        if best_score >= 0.90:
            break

    # Secondary sources must be conservative: an approximate title is not enough
    # to attach metadata silently to thousands of episodes.
    if best_score < 0.82:
        best_id = None
        best_score = 0.0

    cache[key] = best_id
    if diagnostic:
        print(
            f"    TVMAZE SERIES {'MATCHED' if best_id else 'NO MATCH'} | "
            f"query={query_used} | id={best_id or '?'} | score={best_score:.2f}",
            flush=True,
        )
    return best_id, best_score


def resolve_episode_with_secondary(
    client: TVMazeClient,
    row,
    tvmaze_cache: dict[str, int | None],
    diagnostic: bool = False,
):
    """Resolve an episode from TVmaze after TMDB and TMDB-series fallbacks fail."""
    show_id, score = resolve_tvmaze_show_id(client, str(row["provider_title"]), tvmaze_cache, diagnostic=diagnostic)
    if not show_id:
        return None, None

    season = int(row["season_number"])
    episode = int(row["episode_number"])
    try:
        result = client.episode(show_id, season, episode)
    except requests.HTTPError as exc:
        if _http_status(exc) == 404:
            return None, None
        raise

    result = dict(result)
    result["_tvmaze_show_id"] = show_id
    result["_tvmaze_match_score"] = score
    print(
        f"    EPISODE SECONDARY | {row['provider_title']} | S{season:02d}E{episode:02d} "
        f"| source=tvmaze | show={show_id} | score={score:.2f}",
        flush=True,
    )
    return result, f"tvmaze+season_number+episode_number+score_{score:.2f}"


def resolve_episode_with_fallback(
    client: TMDBClient,
    row,
    primary_tmdb_series_id: str,
    tvmaze_client: TVMazeClient,
    tvmaze_cache: dict[str, int | None],
    diagnostic: bool = False,
):
    """Resolve through TMDB first, then alternate TMDB series, then TVmaze."""
    season = int(row["season_number"])
    episode = int(row["episode_number"])
    try:
        return client.episode(int(primary_tmdb_series_id), season, episode), "series_id+season_number+episode_number"
    except requests.HTTPError as exc:
        if _http_status(exc) != 404:
            raise

    provider_title = str(row["provider_title"])
    year = extract_year(provider_title, None)
    country = extract_country(provider_title)
    queries = title_queries(provider_title, year, None)
    candidates: list[dict] = []
    query_used = None
    for query in queries:
        query_used = query
        candidates = search_candidates(client, "series", query, year)
        if candidates:
            break

    if candidates:
        ranked = rank_candidates(client, "series", provider_title, year, candidates, country, diagnostic=diagnostic)
        for score, candidate in ranked:
            candidate_id = int(candidate["id"])
            if candidate_id == int(primary_tmdb_series_id) or classify_match(score) != "matched":
                continue
            try:
                result = client.episode(candidate_id, season, episode)
            except requests.HTTPError as exc:
                if _http_status(exc) == 404:
                    continue
                raise
            print(
                f"    EPISODE FALLBACK | {provider_title} | S{season:02d}E{episode:02d} "
                f"| primary={primary_tmdb_series_id} | fallback={candidate_id} | score={score:.2f} "
                f"| query={query_used}",
                flush=True,
            )
            return result, f"alternate_series_candidate+season_number+episode_number+score_{score:.2f}"

    # TMDB has no usable episode: consult the secondary provider before declaring
    # the item permanently pending. This is intentionally isolated at episode
    # level so the canonical series mapping remains the TMDB mapping.
    return resolve_episode_with_secondary(tvmaze_client, row, tvmaze_cache, diagnostic=diagnostic)


def _http_status(exc: Exception) -> int | None:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code
    return None


def main():
    parser = argparse.ArgumentParser(description="Enriquece episodios con metadata de TMDB y fuentes secundarias")
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
        tvmaze_client = TVMazeClient()
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
        tvmaze_cache: dict[str, int | None] = {}

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

                result, matched_by = resolve_episode_with_fallback(
                    client,
                    row,
                    tmdb_series_id,
                    tvmaze_client,
                    tvmaze_cache,
                    diagnostic=args.diagnostic,
                )
                if result is None:
                    pending += 1
                    print(f"[{index}/{len(rows)}] PENDING | {row['provider_title']} | TMDB/secondary episode inexistente S{row['season_number']:02d}E{row['episode_number']:02d} | tmdb_series={tmdb_series_id}", flush=True)
                    conn.rollback()
                    continue

                source = "tvmaze" if matched_by and matched_by.startswith("tvmaze+") else "tmdb"
                save_episode_metadata(
                    conn,
                    row,
                    result,
                    matched_by=matched_by or "series_id+season_number+episode_number",
                    source=source,
                    language="en" if source == "tvmaze" else settings.tmdb_language,
                )
                conn.commit()
                matched += 1
                print(f"[{index}/{len(rows)}] MATCHED | {row['provider_title']} -> {result.get('name') or '?'} | S{row['season_number']:02d}E{row['episode_number']:02d} | source={source} | tmdb_series={tmdb_series_id}", flush=True)
            except Exception as exc:
                conn.rollback()
                errors += 1
                status = _http_status(exc)
                detail = f"HTTP {status}" if status else f"{type(exc).__name__}: {exc}"
                print(f"[{index}/{len(rows)}] ERROR | episode={row['episode_id']} | {detail}", flush=True)
        print(f"RESUMEN | matched={matched} errors={errors} pending={pending} series_resolved={series_resolved} series_unresolved={series_unresolved}", flush=True)


if __name__ == "__main__":
    main()
