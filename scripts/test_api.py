from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def main() -> None:
    print("=" * 72)
    print("IPTV MANAGER — v0.4.0: API FOUNDATION")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "catalog.db"
        os.environ["DATABASE_PATH"] = str(db)

        # Import after DATABASE_PATH is set because settings are read at import time.
        from app.db.database import connect, init_db
        from app.main import app

        init_db()
        with connect() as conn:
            conn.execute("INSERT INTO providers(name,host) VALUES('Test','http://test')")
            provider_id = conn.execute("SELECT id FROM providers WHERE host='http://test'").fetchone()[0]
            conn.execute("""INSERT INTO categories(provider_id,provider_category_id,name,content_type,selected)
                            VALUES(?,?,?,?,1)""", (provider_id, "1", "ES - PELÍCULAS", "movie"))
            cat = conn.execute("SELECT id FROM categories WHERE provider_category_id='1'").fetchone()[0]
            conn.execute("""INSERT INTO content(provider_id,content_type,canonical_title,normalized_title,original_title,year)
                            VALUES(?,?,?,?,?,?)""", (provider_id,"movie","Test Movie","test movie","Test Movie",2026))
            cid = conn.execute("SELECT id FROM content WHERE canonical_title='Test Movie'").fetchone()[0]
            conn.execute("INSERT INTO content_categories(content_id,category_id) VALUES(?,?)", (cid, cat))
            conn.execute("""INSERT INTO versions(content_id,category_id,quality,resolution,label,source_key)
                            VALUES(?,?,?,?,?,?)""", (cid,cat,"4K","2160p","4K / 2160p","4K|2160p"))
            vid = conn.execute("SELECT id FROM versions WHERE content_id=?", (cid,)).fetchone()[0]
            conn.execute("""INSERT INTO streams(version_id,provider_id,provider_stream_id,stream_url,container_extension)
                            VALUES(?,?,?,?,?)""", (vid,provider_id,"123","http://example.invalid/movie/123.mkv","mkv"))
            conn.commit()

        with TestClient(app) as client:
            checks = [
                ("GET /", client.get("/"), 200),
                ("GET /api/health", client.get("/api/health"), 200),
                ("GET /api/stats", client.get("/api/stats"), 200),
                ("GET /api/categories", client.get("/api/categories"), 200),
                ("GET /api/search", client.get("/api/search?q=test"), 200),
                ("GET /api/movies/{id}", client.get(f"/api/movies/{cid}"), 200),
                ("GET /api/movies/missing", client.get("/api/movies/999999"), 404),
            ]
            for label, response, expected in checks:
                if response.status_code != expected:
                    raise RuntimeError(f"{label}: esperado {expected}, obtenido {response.status_code}: {response.text}")
                print(f"  OK | {label}")

            movie = client.get(f"/api/movies/{cid}").json()
            if not movie["versions"] or not movie["versions"][0]["streams"][0]["playback_url"]:
                raise RuntimeError("El detalle de película no devuelve la versión/stream esperado.")
            print("  OK | película → versiones → streams")

    print("=" * 72)
    print("v0.4.0 COMPLETADA")
    print("API validada contra una BD SQLite de prueba; no consulta Xtream.")
    print("=" * 72)


if __name__ == "__main__":
    main()
