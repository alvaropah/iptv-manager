from __future__ import annotations

import re

from app.db.database import connect


def normalize_name(value: str) -> str:
    value = value.casefold()
    return re.sub(r"\s+", " ", value).strip()


def get_stats() -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT content_type, COUNT(*) AS total
            FROM catalog_items
            GROUP BY content_type
            ORDER BY content_type
            """
        ).fetchall()

        categories = conn.execute(
            "SELECT COUNT(*) AS total FROM categories"
        ).fetchone()["total"]

    result = {row["content_type"]: row["total"] for row in rows}
    result["categories"] = categories
    return result


def search_catalog(query: str, limit: int = 50) -> list[dict]:
    q = f"%{normalize_name(query)}%"

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, content_type, category_id, name, year, poster_url
            FROM catalog_items
            WHERE normalized_name LIKE ?
            ORDER BY normalized_name ASC
            LIMIT ?
            """,
            (q, limit),
        ).fetchall()

    return [dict(row) for row in rows]
