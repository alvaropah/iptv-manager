from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

DB = Path(os.environ.get("DATABASE_PATH", "data/iptv_manager.db"))


def main() -> None:
    print("=" * 72)
    print("IPTV MANAGER — v0.5.1: UI BIBLIOTECA SOBRE CATÁLOGO REAL")
    print("=" * 72)

    if not DB.exists():
        raise RuntimeError(f"No se encontró la BD: {DB}")

    with sqlite3.connect(DB) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check={integrity}")
        counts = {
            "movies": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],
            "series": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],
            "episodes": conn.execute("SELECT COUNT(*) FROM episodes WHERE is_active=1").fetchone()[0],
            "versions": conn.execute("SELECT COUNT(*) FROM versions WHERE is_active=1").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0],
        }

    print(f"BD real: {DB} ({DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print("SQLite integrity_check: OK")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    from app.main import app
    with TestClient(app) as client:
        for path in ("/ui/", "/ui/style.css", "/ui/app.js"):
            r = client.get(path)
            if r.status_code != 200:
                raise RuntimeError(f"{path}: HTTP {r.status_code}")
            print(f"  OK | {path}")

        html = client.get("/ui/").text
        for marker in ("mobileMenu", "search", "BIBLIOTECA", "v0.5.1"):
            if marker not in html:
                raise RuntimeError(f"La UI no contiene el marcador esperado: {marker}")
        print("  OK | shell UI v0.5.1")

        js = client.get("/ui/app.js").text
        for marker in ("function home", "function list", "function categories", "function openMovie", "function openSeries", "function showEpisode"):
            if marker not in js:
                raise RuntimeError(f"app.js no contiene: {marker}")
        print("  OK | navegación principal de biblioteca")

        r = client.get("/api/health")
        if r.status_code != 200 or r.json().get("version") != "0.5.1":
            raise RuntimeError(f"/api/health inesperado: {r.status_code} {r.text[:300]}")
        print("  OK | API health v0.5.1")

        r = client.get("/api/catalog/movie", params={"page": 1, "page_size": 6})
        if r.status_code != 200 or not r.json().get("items"):
            raise RuntimeError("Catálogo de películas sin resultados")
        print("  OK | catálogo de películas")

        r = client.get("/api/catalog/series", params={"page": 1, "page_size": 6})
        if r.status_code != 200 or not r.json().get("items"):
            raise RuntimeError("Catálogo de series sin resultados")
        print("  OK | catálogo de series")

        r = client.get("/api/categories", params={"content_type": "movie"})
        if r.status_code != 200 or not r.json():
            raise RuntimeError("Categorías de películas sin resultados")
        print("  OK | filtros de categorías")

    print("=" * 72)
    print("v0.5.1 UI BIBLIOTECA COMPLETADA")
    print("Diseño y navegación validados sobre el catálogo real.")
    print("No se consulta Xtream ni se modifica la BD durante la prueba.")
    print("=" * 72)


if __name__ == "__main__":
    main()
