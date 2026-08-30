from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def main() -> None:
    print("=" * 72)
    print("IPTV MANAGER — v0.4.1: API SOBRE CATÁLOGO REAL")
    print("=" * 72)

    db_path = Path(os.environ.get("DATABASE_PATH", "data/iptv_manager.db"))
    if not db_path.exists():
        raise RuntimeError(f"No existe la BD restaurada: {db_path}")

    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"BD encontrada: {db_path} ({size_mb:.1f} MB)")

    with sqlite3.connect(db_path) as conn:
        counts = {
            "movies": scalar(conn, "SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1"),
            "series": scalar(conn, "SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1"),
            "seasons": scalar(conn, "SELECT COUNT(*) FROM seasons WHERE is_active=1"),
            "episodes": scalar(conn, "SELECT COUNT(*) FROM episodes WHERE is_active=1"),
            "versions": scalar(conn, "SELECT COUNT(*) FROM versions WHERE is_active=1"),
            "streams": scalar(conn, "SELECT COUNT(*) FROM streams WHERE is_active=1"),
            "categories": scalar(conn, "SELECT COUNT(*) FROM categories WHERE selected=1"),
        }
        movie = conn.execute(
            "SELECT id, canonical_title FROM content WHERE content_type='movie' AND is_active=1 ORDER BY id LIMIT 1"
        ).fetchone()
        series = conn.execute(
            "SELECT id, canonical_title FROM content WHERE content_type='series' AND is_active=1 ORDER BY id LIMIT 1"
        ).fetchone()
        episode = conn.execute(
            "SELECT id FROM episodes WHERE is_active=1 ORDER BY id LIMIT 1"
        ).fetchone()

    if counts["movies"] == 0 or counts["series"] == 0:
        raise RuntimeError(f"La BD no parece contener un catálogo real: {counts}")

    print("Conteo persistido:")
    for key, value in counts.items():
        print(f"  {key}: {value}")

    # The application reads DATABASE_PATH at import time, so this env var must be set before imports.
    os.environ["DATABASE_PATH"] = str(db_path)
    from app.main import app

    with TestClient(app) as client:
        checks = [
            ("GET /", client.get("/"), 200),
            ("GET /api/health", client.get("/api/health"), 200),
            ("GET /api/stats", client.get("/api/stats"), 200),
            ("GET /api/categories", client.get("/api/categories"), 200),
        ]
        for label, response, expected in checks:
            if response.status_code != expected:
                raise RuntimeError(f"{label}: esperado {expected}, obtenido {response.status_code}: {response.text[:500]}")
            print(f"  OK | {label}")

        api_stats = client.get("/api/stats").json()
        for key in counts:
            if api_stats.get(key) != counts[key]:
                raise RuntimeError(f"/api/stats {key}: BD={counts[key]}, API={api_stats.get(key)}")
        print("  OK | /api/stats coincide con SQLite")

        if movie:
            movie_id, movie_title = movie
            response = client.get(f"/api/movies/{movie_id}")
            if response.status_code != 200:
                raise RuntimeError(f"Película real {movie_id}: HTTP {response.status_code}")
            data = response.json()
            print(f"  OK | película real: {movie_title} | versiones={len(data.get('versions', []))}")

        if series:
            series_id, series_title = series
            response = client.get(f"/api/series/{series_id}")
            if response.status_code != 200:
                raise RuntimeError(f"Serie real {series_id}: HTTP {response.status_code}")
            data = response.json()
            seasons = data.get("seasons", [])
            print(f"  OK | serie real: {series_title} | temporadas={len(seasons)}")

        if episode:
            episode_id = episode[0]
            response = client.get(f"/api/episodes/{episode_id}")
            if response.status_code != 200:
                raise RuntimeError(f"Episodio real {episode_id}: HTTP {response.status_code}")
            data = response.json()
            print(f"  OK | episodio real: {data.get('title')} | versiones={len(data.get('versions', []))}")

        response = client.get("/api/movies/999999999")
        if response.status_code != 404:
            raise RuntimeError(f"Contenido inexistente: esperado 404, obtenido {response.status_code}")
        print("  OK | contenido inexistente → 404")

        response = client.get("/api/search?q=the")
        if response.status_code != 200:
            raise RuntimeError(f"Búsqueda: HTTP {response.status_code}: {response.text[:500]}")
        print(f"  OK | búsqueda real → {len(response.json().get('results', []))} resultados")

    print("=" * 72)
    print("v0.4.1 COMPLETADA")
    print("API validada sobre la BD real; no consulta Xtream ni modifica el catálogo.")
    print("=" * 72)


if __name__ == "__main__":
    main()
