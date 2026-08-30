from __future__ import annotations

from app.db.database import connect


def get_stats() -> dict:
    with connect() as conn:
        counts = {
            "movies": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie'").fetchone()[0],
            "series": conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series'").fetchone()[0],
            "seasons": conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0],
            "episodes": conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
            "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
            "streams": conn.execute("SELECT COUNT(*) FROM streams WHERE is_active=1").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0],
        }
        return counts


def search_catalog(query: str, limit: int = 50) -> list[dict]:
    q = f"%{query.casefold().strip()}%"
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, content_type, canonical_title AS name, year, poster_url
               FROM content
               WHERE is_active=1 AND normalized_title LIKE ?
               ORDER BY normalized_title LIMIT ?""",
            (q, limit),
        ).fetchall()
    return [dict(row) for row in rows]
