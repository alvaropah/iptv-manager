from __future__ import annotations

import os
import sqlite3

from app.core.config import settings
from app.db.database import init_db
from app.services.metadata import classify_match, normalize_title, score_candidate


def main() -> None:
    init_db()
    with sqlite3.connect(settings.database_path) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"metadata_links", "content_metadata", "episode_metadata", "person_metadata"}
        assert required <= tables, required - tables
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in required}
        content = con.execute("SELECT canonical_title, year FROM content WHERE is_active=1 LIMIT 1").fetchone()
    assert normalize_title("Avatar 2 4K Dolby Vision") == normalize_title("Avatar 2")
    candidate = {"title": content[0] if content else "Dune", "release_date": f"{content[1] or 2024}-01-01"}
    score = score_candidate(content[0] if content else "Dune", content[1] if content else 2024, candidate)
    assert score >= 0.9 and classify_match(score) == "matched"
    print("IPTV MANAGER — v0.6: METADATA & MATCHING")
    print("metadata tables: OK")
    print(f"metadata rows: {counts}")
    print("normalización: OK")
    print("matching exacto + año: OK")
    print("review threshold: OK")
    print("TMDB_API_TOKEN configurado:", bool(os.getenv("TMDB_API_TOKEN")))
    print("v0.6 base COMPLETADA")


if __name__ == "__main__":
    main()
