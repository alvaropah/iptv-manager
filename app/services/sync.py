from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile
from app.core.config import settings
from app.core.content_identity import analyze_title, display_title
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient
from app.db.database import connect, init_db


def build_xtream_client() -> XtreamClient:
    return XtreamClient(settings.xtream_host, settings.xtream_username, settings.xtream_password)


def test_connection() -> dict:
    client = build_xtream_client()
    auth = client.authenticate()
    user_info = auth.get("user_info", {}) if isinstance(auth, dict) else {}
    return {"connected": True, "status": user_info.get("status"), "exp_date": user_info.get("exp_date")}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def category_map(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        normalize_category_name(str(x.get("category_name", ""))): x
        for x in (items or [])
    }


def url_for_vod(client: XtreamClient, stream_id: str, ext: str | None) -> str:
    extension = (ext or "mkv").lstrip(".")
    return f"{client.host}/movie/{client.username}/{client.password}/{stream_id}.{extension}"


def url_for_episode(client: XtreamClient, episode_id: str, ext: str | None) -> str:
    extension = (ext or "mkv").lstrip(".")
    return f"{client.host}/series/{client.username}/{client.password}/{episode_id}.{extension}"


def profile_values(category_name: str) -> dict[str, Any]:
    p = infer_category_profile(category_name)
    return {
        "quality": p.quality,
        "resolution": p.resolution,
        "dynamic_range": p.dynamic_range,
        "audio": p.audio,
        "subtitles": p.subtitles,
        "language": p.language_hint,
    }


def source_key(profile: dict[str, Any]) -> str:
    return "|".join(str(profile.get(k) or "") for k in ("quality", "resolution", "dynamic_range", "audio", "subtitles", "language"))


def upsert_provider(conn, client: XtreamClient) -> int:
    conn.execute(
        "INSERT INTO providers(name,host) VALUES(?,?) ON CONFLICT(host) DO UPDATE SET updated_at=CURRENT_TIMESTAMP",
        ("Xtream", client.host),
    )
    return conn.execute("SELECT id FROM providers WHERE host=?", (client.host,)).fetchone()[0]


def upsert_category(conn, provider_id: int, item: dict[str, Any], content_type: str, selected: bool) -> int:
    profile = profile_values(str(item.get("category_name", "")))
    conn.execute(
        """INSERT INTO categories(provider_id,provider_category_id,name,content_type,provider_order,selected,
           quality,resolution,dynamic_range,audio,subtitles,language_hint,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(provider_id,provider_category_id) DO UPDATE SET
           name=excluded.name, content_type=excluded.content_type, provider_order=excluded.provider_order,
           selected=excluded.selected, quality=excluded.quality, resolution=excluded.resolution,
           dynamic_range=excluded.dynamic_range, audio=excluded.audio, subtitles=excluded.subtitles,
           language_hint=excluded.language_hint, updated_at=CURRENT_TIMESTAMP""",
        (provider_id, str(item.get("category_id", "")), str(item.get("category_name", "")), content_type,
         item.get("category_id"), int(selected), profile["quality"], profile["resolution"],
         profile["dynamic_range"], profile["audio"], profile["subtitles"], profile["language"]),
    )
    return conn.execute(
        "SELECT id FROM categories WHERE provider_id=? AND provider_category_id=?",
        (provider_id, str(item.get("category_id", ""))),
    ).fetchone()[0]


def ensure_content(conn, provider_id: int, content_type: str, analysis, original: str) -> tuple[int, bool]:
    row = conn.execute(
        "SELECT id, original_title, year FROM content WHERE provider_id=? AND content_type=? AND normalized_title=? AND year IS ?",
        (provider_id, content_type, analysis.canonical, analysis.year),
    ).fetchone()
    if row:
        changed = row[1] != original
        conn.execute(
            "UPDATE content SET original_title=?, is_active=1, last_seen_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (original, row[0]),
        )
        return row[0], changed
    cur = conn.execute(
        """INSERT INTO content(provider_id,content_type,canonical_title,normalized_title,original_title,year)
           VALUES(?,?,?,?,?,?)""",
        (provider_id, content_type, display_title(original), analysis.canonical, original, analysis.year),
    )
    return cur.lastrowid, True


def ensure_content_category(conn, content_id: int, category_id: int) -> None:
    conn.execute("INSERT OR IGNORE INTO content_categories(content_id,category_id) VALUES(?,?)", (content_id, category_id))


def ensure_version(conn, content_id: int | None, episode_id: int | None, category_id: int, profile: dict[str, Any], source_key_value: str) -> int:
    row = conn.execute(
        """SELECT id FROM versions WHERE content_id IS ? AND episode_id IS ? AND category_id=? AND source_key=?""",
        (content_id, episode_id, category_id, source_key_value),
    ).fetchone()
    if row:
        conn.execute("UPDATE versions SET is_active=1,last_seen_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (row[0],))
        return row[0]
    label = " / ".join(str(x) for x in (profile.get("quality"), profile.get("resolution"), profile.get("dynamic_range"), profile.get("audio")) if x)
    cur = conn.execute(
        """INSERT INTO versions(content_id,episode_id,category_id,source_key,quality,resolution,dynamic_range,audio_codec,subtitles,languages,label)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (content_id, episode_id, category_id, source_key_value, profile.get("quality"), profile.get("resolution"),
         profile.get("dynamic_range"), profile.get("audio"), str(profile.get("subtitles")) if profile.get("subtitles") is not None else None,
         profile.get("language"), label or None),
    )
    return cur.lastrowid


def ensure_stream(conn, version_id: int, provider_id: int, source_id: str, url: str | None, ext: str | None, original_name: str, raw: dict[str, Any]) -> tuple[int, bool]:
    fp = fingerprint(raw)
    row = conn.execute("SELECT id, fingerprint, version_id FROM streams WHERE provider_id=? AND provider_stream_id=? AND version_id=?", (provider_id, source_id, version_id)).fetchone()
    if row:
        changed = row[1] != fp or row[2] != version_id
        conn.execute(
            """UPDATE streams SET version_id=?,stream_url=?,container_extension=?,original_name=?,raw_json=?,fingerprint=?,
               is_active=1,last_seen_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (version_id, url, ext, original_name, json.dumps(raw, ensure_ascii=False), fp, row[0]),
        )
        return row[0], changed
    cur = conn.execute(
        """INSERT INTO streams(version_id,provider_id,provider_stream_id,stream_url,container_extension,original_name,raw_json,fingerprint)
           VALUES(?,?,?,?,?,?,?,?)""",
        (version_id, provider_id, source_id, url, ext, original_name, json.dumps(raw, ensure_ascii=False), fp),
    )
    return cur.lastrowid, True


def process_vod(conn, client: XtreamClient, provider_id: int, category_id: int, category_name: str, items: list[dict[str, Any]], run_id: int) -> tuple[int, int]:
    new = changed = 0
    profile = profile_values(category_name)
    skey = source_key(profile)
    for item in items:
        original = str(item.get("name", "")).strip()
        analysis = analyze_title(original)
        if not analysis.canonical:
            continue
        content_id, content_new = ensure_content(conn, provider_id, "movie", analysis, original)
        if content_new:
            new += 1
            conn.execute("INSERT INTO change_events(sync_run_id,entity_type,entity_id,event_type,summary) VALUES(?,?,?,?,?)", (run_id,"movie",content_id,"added",original))
        ensure_content_category(conn, content_id, category_id)
        version_id = ensure_version(conn, content_id, None, category_id, profile, skey)
        source_id = str(item.get("stream_id", ""))
        ext = str(item.get("container_extension") or item.get("ext") or "mkv")
        url = url_for_vod(client, source_id, ext) if source_id else None
        _, stream_changed = ensure_stream(conn, version_id, provider_id, source_id, url, ext, original, item)
        conn.execute("INSERT OR IGNORE INTO stream_categories(provider_stream_id,category_id) VALUES(?,?)", (source_id, category_id))
        if stream_changed and not content_new:
            changed += 1
    return new, changed


def series_item_fingerprint(item: dict[str, Any]) -> str:
    # Keep the list-level metadata only; this is what lets us skip detail calls when unchanged.
    return fingerprint({k: item.get(k) for k in sorted(item) if k not in {"added", "last_modified"}})


def detail_worker(host: str, username: str, password: str, series_id: str) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        client = XtreamClient(host, username, password, timeout=60)
        return series_id, client.series_info(series_id) or {}, None
    except Exception as exc:
        return series_id, None, str(exc)


def episode_map(detail: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    raw = detail.get("episodes") or {}
    result: dict[int, list[dict[str, Any]]] = {}
    if isinstance(raw, dict):
        for key, eps in raw.items():
            if isinstance(eps, list):
                try: season_no = int(key)
                except (ValueError, TypeError): continue
                result[season_no] = [e for e in eps if isinstance(e, dict) and e.get("episode_num") is not None]
    return result


def sync_series_details(conn, client: XtreamClient, provider_id: int, jobs: list[dict[str, Any]], run_id: int) -> tuple[int, int, int, int]:
    if not jobs:
        return 0, 0, 0, 0

    # The same provider series_id can appear in several selected categories.
    # Fetch its detail exactly once, then fan it out to all category versions.
    by_series: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        by_series.setdefault(job["series_id"], []).append(job)

    workers = max(1, min(int(os.getenv("SYNC_WORKERS", "8")), 12))
    new_eps = changed = detail_requests = errors = 0
    total = len(by_series)
    print(f"  Series únicas que requieren detalle: {total} (workers={workers})", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(detail_worker, client.host, client.username, client.password, series_id): series_id
            for series_id in by_series
        }
        for idx, future in enumerate(as_completed(futures), 1):
            series_id = futures[future]
            try:
                returned_id, detail, error = future.result()
            except Exception as exc:
                returned_id, detail, error = series_id, None, str(exc)
            detail_requests += 1

            if error or detail is None:
                errors += 1
                conn.execute(
                    "INSERT INTO change_events(sync_run_id,entity_type,event_type,summary) VALUES(?,?,?,?)",
                    (run_id, "series", "changed", f"Error detalle {series_id}: {error}"),
                )
                continue

            seasons = episode_map(detail)
            for job in by_series[returned_id]:
                content_id = job["content_id"]
                category_id = job["category_id"]
                profile = job["profile"]
                skey = source_key(profile)
                seen_episode_streams: set[str] = set()

                for season_no, eps in seasons.items():
                    conn.execute(
                        """INSERT INTO seasons(series_id,season_number,name,is_active,last_seen_at,updated_at)
                           VALUES(?,?,?,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                           ON CONFLICT(series_id,season_number) DO UPDATE SET
                           name=excluded.name,is_active=1,last_seen_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP""",
                        (content_id, season_no, f"Season {season_no}"),
                    )
                    season_id = conn.execute(
                        "SELECT id FROM seasons WHERE series_id=? AND season_number=?",
                        (content_id, season_no),
                    ).fetchone()[0]

                    seen_episode_numbers: set[int] = set()
                    for ep in eps:
                        number = int(ep.get("episode_num"))
                        seen_episode_numbers.add(number)
                        title = str(ep.get("title") or ep.get("name") or f"Episode {number}")
                        info = ep.get("info") if isinstance(ep.get("info"), dict) else {}
                        poster = info.get("movie_image") or ep.get("movie_image")
                        analysis = analyze_title(title)
                        conn.execute(
                            """INSERT INTO episodes(season_id,episode_number,canonical_title,normalized_title,overview,air_date,poster_url,is_active,last_seen_at,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                               ON CONFLICT(season_id,episode_number) DO UPDATE SET
                               canonical_title=excluded.canonical_title,normalized_title=excluded.normalized_title,
                               overview=excluded.overview,air_date=excluded.air_date,poster_url=excluded.poster_url,
                               is_active=1,last_seen_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP""",
                            (season_id, number, display_title(title), analysis.canonical, ep.get("plot"),
                             ep.get("air_date"), poster, 1),
                        )
                        episode_id = conn.execute(
                            "SELECT id FROM episodes WHERE season_id=? AND episode_number=?",
                            (season_id, number),
                        ).fetchone()[0]
                        version_id = ensure_version(conn, None, episode_id, category_id, profile, skey)
                        source_id = str(ep.get("id", ""))
                        if not source_id:
                            continue
                        seen_episode_streams.add(source_id)
                        ext = str(ep.get("container_extension") or ep.get("container") or "mkv")
                        url = url_for_episode(client, source_id, ext)
                        _, stream_changed = ensure_stream(
                            conn, version_id, provider_id, source_id, url, ext, title, ep
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO stream_categories(provider_stream_id,category_id) VALUES(?,?)",
                            (source_id, category_id),
                        )
                        if stream_changed:
                            changed += 1

                    # Soft-remove episode streams belonging to this version when a refreshed
                    # detail response no longer contains them. The source_id set is scoped to
                    # this series/category version, so other categories remain untouched.
                    rows = conn.execute(
                        """SELECT s.id,s.provider_stream_id FROM streams s
                           JOIN versions v ON v.id=s.version_id
                           WHERE s.provider_id=? AND v.episode_id IS NOT NULL
                             AND v.category_id=? AND v.content_id IS NULL
                             AND s.is_active=1""",
                        (provider_id, category_id),
                    ).fetchall()
                    for row in rows:
                        sid = str(row[1])
                        if sid not in seen_episode_streams:
                            # We cannot safely infer ownership from category alone when several
                            # series share it. Only mark as inactive if this stream belongs to an
                            # episode of the current content.
                            owner = conn.execute(
                                """SELECT 1 FROM streams s
                                   JOIN versions v ON v.id=s.version_id
                                   JOIN episodes e ON e.id=v.episode_id
                                   JOIN seasons se ON se.id=e.season_id
                                   WHERE s.id=? AND se.series_id=? LIMIT 1""",
                                (row[0], content_id),
                            ).fetchone()
                            if owner:
                                conn.execute("UPDATE streams SET is_active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?", (row[0],))

                conn.execute(
                    "UPDATE content SET last_detail_sync_at=CURRENT_TIMESTAMP WHERE id=?",
                    (content_id,),
                )
                conn.execute(
                    """UPDATE series_sources SET last_detail_sync_at=CURRENT_TIMESTAMP,is_active=1,last_seen_at=CURRENT_TIMESTAMP
                       WHERE content_id=? AND provider_series_id=? AND category_id=?""",
                    (content_id, series_id, category_id),
                )

            if idx % 25 == 0 or idx == total:
                print(f"    detalles {idx}/{total}", flush=True)
            # Keep the transaction reasonably small on the first import.
            if idx % 25 == 0:
                conn.commit()

    return new_eps, changed, detail_requests, errors


def run_sync() -> dict[str, Any]:
    init_db()
    cfg = load_catalog_selection()
    client = build_xtream_client()
    client.authenticate()
    with connect() as conn:
        provider_id = upsert_provider(conn, client)
        cur = conn.execute("INSERT INTO sync_runs(provider_id,status) VALUES(?,?)", (provider_id,"running"))
        run_id = cur.lastrowid
        try:
            real_series = category_map(client.series_categories())
            real_vod = category_map(client.vod_categories())
            selected_series = [real_series[normalize_category_name(x)] for x in cfg.series_categories if normalize_category_name(x) in real_series]
            selected_vod = [real_vod[normalize_category_name(x)] for x in cfg.movie_categories if normalize_category_name(x) in real_vod]

            conn.execute("UPDATE categories SET selected=0 WHERE provider_id=? AND content_type IN ('series','movie')", (provider_id,))
            for i, item in enumerate(selected_series,1): upsert_category(conn, provider_id, item, "series", True)
            for i, item in enumerate(selected_vod,1): upsert_category(conn, provider_id, item, "movie", True)
            conn.commit()

            movie_total = series_total = 0
            new_count = changed_count = 0
            series_jobs: list[dict[str, Any]] = []
            series_occurrences = 0
            series_detail_skipped = 0
            seen_series_sources: set[tuple[str,str]] = set()
            seen_vod_streams: set[tuple[int, str]] = set()

            print(f"Sincronizando VOD: {len(selected_vod)} categorías", flush=True)
            for i, cat in enumerate(selected_vod,1):
                category_id = conn.execute("SELECT id FROM categories WHERE provider_id=? AND provider_category_id=?", (provider_id,str(cat.get("category_id")))).fetchone()[0]
                items = client.vod_streams(str(cat.get("category_id"))) or []
                movie_total += len(items)
                n,c = process_vod(conn, client, provider_id, category_id, str(cat.get("category_name")), items, run_id)
                new_count += n; changed_count += c
                for item in items: seen_vod_streams.add((category_id, str(item.get("stream_id",""))))
                print(f"  [{i}/{len(selected_vod)}] {cat.get('category_name')}: {len(items)}", flush=True)
                conn.commit()

            print(f"Sincronizando SERIES: {len(selected_series)} categorías", flush=True)
            for i, cat in enumerate(selected_series,1):
                category_id = conn.execute("SELECT id FROM categories WHERE provider_id=? AND provider_category_id=?", (provider_id,str(cat.get("category_id")))).fetchone()[0]
                items = client.series_streams(str(cat.get("category_id"))) or []
                series_total += len(items)
                series_occurrences += len(items)
                profile = profile_values(str(cat.get("category_name")))
                for item in items:
                    original = str(item.get("name", "")).strip()
                    analysis = analyze_title(original)
                    if not analysis.canonical: continue
                    content_id, content_new = ensure_content(conn, provider_id, "series", analysis, original)
                    if content_new:
                        new_count += 1
                        conn.execute("INSERT INTO change_events(sync_run_id,entity_type,entity_id,event_type,summary) VALUES(?,?,?,?,?)", (run_id,"series",content_id,"added",original))
                    ensure_content_category(conn, content_id, category_id)
                    sid = str(item.get("series_id", ""))
                    fp = series_item_fingerprint(item)
                    prev = conn.execute("SELECT fingerprint,last_detail_sync_at FROM series_sources WHERE content_id=? AND provider_series_id=? AND category_id=?", (content_id,sid,category_id)).fetchone()
                    conn.execute(
                        """INSERT INTO series_sources(content_id,provider_series_id,category_id,fingerprint,is_active,last_seen_at)
                           VALUES(?,?,?,?,1,CURRENT_TIMESTAMP)
                           ON CONFLICT(content_id,provider_series_id,category_id) DO UPDATE SET fingerprint=excluded.fingerprint,is_active=1,last_seen_at=CURRENT_TIMESTAMP""",
                        (content_id,sid,category_id,fp),
                    )
                    if prev is None or prev[0] != fp or prev[1] is None:
                        series_jobs.append({"series_id":sid,"content_id":content_id,"category_id":category_id,"profile":profile})
                    else:
                        series_detail_skipped += 1
                    seen_series_sources.add((sid,str(cat.get("category_id"))))
                print(f"  [{i}/{len(selected_series)}] {cat.get('category_name')}: {len(items)}", flush=True)
                conn.commit()

            eps_new, detail_changed, detail_requests, detail_errors = sync_series_details(conn, client, provider_id, series_jobs, run_id)
            changed_count += detail_changed

            # Soft-remove streams that disappeared from the selected VOD snapshot.
            if seen_vod_streams:
                rows = conn.execute(
                    """SELECT s.id,s.provider_stream_id,v.category_id
                       FROM streams s JOIN versions v ON v.id=s.version_id
                       WHERE s.provider_id=? AND s.is_active=1 AND v.content_id IS NOT NULL""",
                    (provider_id,),
                ).fetchall()
                for row in rows:
                    key = (int(row[2]), str(row[1]))
                    if key not in seen_vod_streams:
                        conn.execute("UPDATE streams SET is_active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?", (row[0],))

            conn.execute("UPDATE sync_runs SET finished_at=CURRENT_TIMESTAMP,status='success',movie_count=?,series_count=?,episode_count=(SELECT COUNT(*) FROM episodes),version_count=(SELECT COUNT(*) FROM versions),stream_count=(SELECT COUNT(*) FROM streams),new_count=?,changed_count=?,detail_requests=?,skipped_detail_requests=(SELECT COUNT(*) FROM series_sources)-?,error=NULL WHERE id=?", (movie_total,series_total,new_count,changed_count,detail_requests,len(series_jobs),run_id))
            conn.commit()
            return {"run_id":run_id,"status":"success","movies":movie_total,"series":series_total,"series_detail_requests":detail_requests,"series_detail_candidates":len(series_jobs),
                "series_detail_skipped":series_detail_skipped,"new":new_count,"changed":changed_count,"detail_errors":detail_errors}
        except Exception as exc:
            conn.execute("UPDATE sync_runs SET finished_at=CURRENT_TIMESTAMP,status='error',error=? WHERE id=?", (str(exc),run_id))
            conn.commit()
            raise
