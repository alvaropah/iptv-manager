from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.metadata import clean_provider_title, score_candidate


def check(title: str, expected: str) -> None:
    actual = clean_provider_title(title)
    assert actual == expected, f"{title!r} -> {actual!r}, esperado {expected!r}"


def main() -> None:
    check("4K-AMZ - Finnish American Rag Rug Weavers (2019)", "Finnish American Rag Rug Weavers (2019)")
    check("AMZ - Generation Wealth (2018)", "Generation Wealth (2018)")
    check("NETFLIX - Stranger Things 4K Dolby Vision", "Stranger Things")
    check("AMZ - As The Water Flows (2025)", "As The Water Flows (2025)")

    candidate = {
        "id": 1,
        "title": "翠湖",
        "original_title": "翠湖",
        "alternative_titles": ["As the Water Flows", "Cui Hu"],
        "release_date": "2025-01-01",
    }
    score = score_candidate("AMZ - As The Water Flows (2025)", 2025, candidate)
    assert score >= 0.86, f"As The Water Flows no alcanza MATCHED: {score}"

    candidate = {
        "id": 2,
        "title": "साइना",
        "original_title": "साइना",
        "alternative_titles": ["Saina"],
        "release_date": "2021-03-26",
    }
    score = score_candidate("AMZ - Saina (2021)", 2021, candidate)
    assert score >= 0.86, f"Saina no alcanza MATCHED: {score}"

    print("v0.6.7 matching tests: OK")


if __name__ == "__main__":
    main()
