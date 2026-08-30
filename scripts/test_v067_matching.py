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


def check_variant(title: str, candidate: dict, label: str) -> None:
    score = score_candidate(title, None, candidate)
    assert score > 0.80, f"{label}: la variante conocida no se reconoce: score={score}"
    print(f"OK | {label} | variant recognized | score={score:.4f}")


def main() -> None:
    check("4K-AMZ - Finnish American Rag Rug Weavers (2019)", "Finnish American Rag Rug Weavers (2019)")
    check("AMZ - Generation Wealth (2018)", "Generation Wealth (2018)")
    check("NETFLIX - Stranger Things 4K Dolby Vision", "Stranger Things")
    check("AMZ - As The Water Flows (2025)", "As The Water Flows (2025)")

    check_variant(
        "AMZ - As The Water Flows (2025)",
        {"id": 1, "title": "翠湖", "original_title": "翠湖", "alternative_titles": ["As the Water Flows", "Cui Hu"]},
        "As The Water Flows",
    )
    check_variant(
        "AMZ - Saina (2021)",
        {"id": 2, "title": "साइना", "original_title": "साइना", "alternative_titles": ["Saina"]},
        "Saina",
    )

    # A low-similarity candidate must not be promoted merely because it exists.
    bad = {"id": 3, "title": "Három sárkány", "original_title": "Három sárkány", "alternative_titles": []}
    score = score_candidate("AMZ - Spinsters (2023)", 2023, bad)
    assert score < 0.62, f"Spinsters candidato incorrecto demasiado alto: {score}"

    print("v0.6.7 matching tests: OK")


if __name__ == "__main__":
    main()
