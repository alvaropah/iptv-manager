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
            """
            SELECT c.id, c.canonical_title
            FROM content c
            JOIN versions v ON v.content_id=c.id AND v.is_active=1
            JOIN streams s ON s.version_id=v.id AND s.is_active=1
            WHERE c.content_type='movie' AND c.is_active=1
            ORDER BY c.id LIMIT 1
            """
        ).fetchone()

        series = conn.execute(
            """
            SELECT c.id, c.canonical_title
            FROM content c
            JOIN seasons se ON se.series_id=c.id AND se.is_active=1
            JOIN episodes e ON e.season_id=se.id AND e.is_active=1
            JOIN versions v ON v.episode_id=e.id AND v.is_active=1
            JOIN streams s ON s.version_id=v.id AND s.is_active=1
            WHERE c.content_type='series' AND c.is_active=1
            ORDER BY c.id LIMIT 1
            """
        ).fetchone()

        episode = conn.execute(
            """
            SELECT e.id, e.canonical_title
            FROM episodes e
            JOIN versions v ON v.episode_id=e.id AND v.is_active=1
            JOIN streams s ON s.version_id=v.id AND s.is_active=1
            WHERE e.is_active=1
            ORDER BY e.id LIMIT 1
            """
        ).fetchone()

        # Use the same normalized field that the API searches.
        # canonical_title may legitimately contain a quality prefix such as
        # "4K-", while normalized_title intentionally removes technical
        # signals. Searching "4K-" would therefore be a bad test seed.
        search_seed_row = conn.execute(
            """
            SELECT normalized_title
            FROM content
            WHERE is_active=1
              AND normalized_title IS NOT NULL
              AND length(trim(normalized_title)) >= 3
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()
        search_seed = (search_seed_row[0] if search_seed_row else "")[:3]

    if counts["movies"] == 0 or counts["series"] == 0:
        raise RuntimeError(f"La BD no parece contener un catálogo real: {counts}")
    if counts["versions"] == 0 or counts["streams"] == 0:
        raise RuntimeError(f"La BD no contiene versiones/streams activos: {counts}")
    if movie is None or series is None or episode is None:
        raise RuntimeError("No se encontraron registros reales con relaciones completas para probar la API.")

    print("Conteo persistido:")
    for key, value in counts.items():
        print(f"  {key}: {value}")

    # DATABASE_PATH must be set before importing the application.
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

        movie_id, movie_title = movie
        response = client.get(f"/api/movies/{movie_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Película real {movie_id}: HTTP {response.status_code}")
        movie_data = response.json()
        if not movie_data.get("versions"):
            raise RuntimeError(f"Película real {movie_id} no devuelve versiones")
        if not any(v.get("streams") for v in movie_data["versions"]):
            raise RuntimeError(f"Película real {movie_id} no devuelve streams")
        print(f"  OK | película real: {movie_title} | versiones={len(movie_data['versions'])}")

        series_id, series_title = series
        response = client.get(f"/api/series/{series_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Serie real {series_id}: HTTP {response.status_code}")
        series_data = response.json()
        seasons = series_data.get("seasons", [])
        if not seasons:
            raise RuntimeError(f"Serie real {series_id} no devuelve temporadas")
        episode_count = sum(len(s.get("episodes", [])) for s in seasons)
        if episode_count == 0:
            raise RuntimeError(f"Serie real {series_id} no devuelve episodios")
        print(f"  OK | serie real: {series_title} | temporadas={len(seasons)} | episodios={episode_count}")

        episode_id, episode_title = episode
        response = client.get(f"/api/episodes/{episode_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Episodio real {episode_id}: HTTP {response.status_code}")
        episode_data = response.json()
        if not episode_data.get("versions"):
            raise RuntimeError(f"Episodio real {episode_id} no devuelve versiones")
        if not any(v.get("streams") for v in episode_data["versions"]):
            raise RuntimeError(f"Episodio real {episode_id} no devuelve streams")
        print(f"  OK | episodio real: {episode_title} | versiones={len(episode_data['versions'])}")

        response = client.get("/api/movies/999999999999")
        if response.status_code != 404:
            raise RuntimeError(f"Contenido inexistente: esperado 404, obtenido {response.status_code}")
        print("  OK | contenido inexistente → 404")

        if search_seed:
            response = client.get("/api/search", params={"q": search_seed})
            if response.status_code != 200:
                raise RuntimeError(f"Búsqueda: HTTP {response.status_code}: {response.text[:500]}")
            results = response.json().get("results", [])
            if not results:
                raise RuntimeError(f"La búsqueda real no devolvió resultados para '{search_seed}'")
            print(f"  OK | búsqueda real '{search_seed}' → {len(results)} resultados")

    print("=" * 72)
    print("v0.4.1 COMPLETADA")
    print("API validada sobre la BD real; no consulta Xtream ni modifica el catálogo.")
    print("=" * 72)


if __name__ == "__main__":
    main()
