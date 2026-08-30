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
from app.db.database import connect


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
        (
            row["episode_id"], "tmdb", external_id,
            result.get("name"), result.get("overview"), result.get("air_date"),
            result.get("runtime"), still_url,
            json.dumps(result, ensure_ascii=False), settings.tmdb_language,
        ),
    )

    # metadata_links has UNIQUE(external_source, external_id), while an
    # episode can be reprocessed. Remove only this episode's previous link.
    conn.execute(
        "DELETE FROM metadata_links WHERE episode_id=? AND external_source='tmdb'",
        (row["episode_id"],),
    )
    conn.execute(
        """INSERT INTO metadata_links
        (episode_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
        VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (
            row["episode_id"], row["provider_title"], "tmdb", external_id,
            "matched", 1.0, "series_id+season_number+episode_number",
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Enriquece episodios con metadata de TMDB")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--refresh", action="store_true", help="Volver a consultar episodios ya enriquecidos")
    args = parser.parse_args()

    token = settings.tmdb_api_token or os.getenv("TMDB_API_TOKEN", "")
    if not token:
        raise SystemExit("TMDB_API_TOKEN no está configurado")

    client = TMDBClient(token, settings.tmdb_language)
    with connect() as conn:
        where = "e.is_active=1 AND c.is_active=1"
        if not args.refresh:
            where += " AND em.episode_id IS NULL"
        rows = conn.execute(
            f"""SELECT e.id AS episode_id, e.canonical_title AS provider_title,
                       s.season_number, e.episode_number,
                       cm.external_id AS tmdb_series_id
                FROM episodes e
                JOIN seasons s ON s.id=e.season_id
                JOIN content c ON c.id=s.series_id
                JOIN content_metadata cm ON cm.content_id=c.id AND cm.source='tmdb'
                LEFT JOIN episode_metadata em ON em.episode_id=e.id
                WHERE {where}
                ORDER BY e.id LIMIT ?""",
            (args.limit,),
        ).fetchall()

        matched = errors = 0
        for index, row in enumerate(rows, 1):
            try:
                result = client.episode(
                    int(row["tmdb_series_id"]),
                    int(row["season_number"]),
                    int(row["episode_number"]),
                )
                save_episode_metadata(conn, row, result)
                conn.commit()
                matched += 1
                print(
                    f"[{index}/{len(rows)}] MATCHED | {row['provider_title']} -> "
                    f"{result.get('name') or '?'} | S{row['season_number']:02d}E{row['episode_number']:02d}",
                    flush=True,
                )
            except Exception as exc:
                errors += 1
                print(
                    f"[{index}/{len(rows)}] ERROR | episode={row['episode_id']} | {exc}",
                    flush=True,
                )

        print(
            f"RESUMEN | matched={matched} errors={errors} pending={len(rows)-matched-errors}",
            flush=True,
        )


if __name__ == "__main__":
    main()
