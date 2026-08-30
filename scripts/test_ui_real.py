from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

DB = Path(os.environ.get("DATABASE_PATH", "data/iptv_manager.db"))
REQUIRED = {
    "providers", "categories", "content", "seasons", "episodes",
    "versions", "streams", "content_categories", "stream_categories",
    "series_sources", "sync_runs", "change_events", "sync_state",
}

def main() -> None:
    print("=" * 72)
    print("IPTV MANAGER — v0.4.3: UI SOBRE CATÁLOGO REAL")
    print("=" * 72)

    if not DB.exists():
        raise RuntimeError(f"No se encontró la BD: {DB}")

    with sqlite3.connect(DB) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = REQUIRED - tables
        if missing:
            raise RuntimeError(f"BD incompatible; faltan tablas: {sorted(missing)}")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check={integrity}")
        counts = {
            "movies": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],
            "series": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],
            "seasons": conn.execute("SELECT COUNT(*) FROM seasons WHERE is_active=1").fetchone()[0],
            "episodes": conn.execute("SELECT COUNT(*) FROM episodes WHERE is_active=1").fetchone()[0],
            "versions": conn.execute("SELECT COUNT(*) FROM versions WHERE is_active=1").fetchone()[0],
            "streams": conn.execute("SELECT COUNT(*) FROM streams WHERE is_active=1").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0],
        }
        seed_row = conn.execute(
            "SELECT normalized_title FROM content WHERE is_active=1 AND normalized_title IS NOT NULL "
            "AND length(trim(normalized_title)) >= 3 ORDER BY id LIMIT 1"
        ).fetchone()

    print(f"BD real encontrada: {DB} ({DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print("SQLite integrity_check: OK")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    if not all(counts[k] > 0 for k in ("movies", "series", "versions", "streams", "categories")):
        raise RuntimeError(f"La BD no parece contener un catálogo real: {counts}")

    from app.main import app
    with TestClient(app) as client:
        for path in ("/ui/", "/ui/style.css", "/ui/app.js"):
            r = client.get(path)
            if r.status_code != 200:
                raise RuntimeError(f"{path}: HTTP {r.status_code}")
            print(f"  OK | {path}")

        r = client.get("/api/stats")
        if r.status_code != 200:
            raise RuntimeError(f"/api/stats: HTTP {r.status_code}: {r.text[:300]}")
        api_stats = r.json()
        for k, v in counts.items():
            if api_stats.get(k) != v:
                raise RuntimeError(f"/api/stats {k}: BD={v}, API={api_stats.get(k)}")
        print("  OK | /api/stats coincide con SQLite")

        seed = seed_row[0][:3] if seed_row else "amz"
        r = client.get("/api/search", params={"q": seed})
        if r.status_code != 200:
            raise RuntimeError(f"Búsqueda: HTTP {r.status_code}: {r.text[:300]}")
        results = r.json().get("results", [])
        if not results:
            raise RuntimeError(f"La búsqueda real no devolvió resultados para '{seed}'")
        print(f"  OK | búsqueda real '{seed}' → {len(results)} resultados")

    print("=" * 72)
    print("v0.4.3 COMPLETADA")
    print("UI y API validadas contra el catálogo real.")
    print("No se consulta Xtream ni se modifica el catálogo.")
    print("=" * 72)

if __name__ == "__main__":
    main()
