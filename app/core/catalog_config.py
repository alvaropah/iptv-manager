from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yml"


@dataclass(frozen=True)
class CatalogSelection:
    series_categories: tuple[str, ...]
    movie_categories: tuple[str, ...]

    @property
    def total_vod_categories(self) -> int:
        return len(self.series_categories) + len(self.movie_categories)


def load_catalog_selection(path: Path = CONFIG_PATH) -> CatalogSelection:
    if not path.exists():
        raise FileNotFoundError(f"No existe la configuración de catálogo: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data: Any = yaml.safe_load(fh) or {}

    series = data.get("series_categories")
    movies = data.get("movie_categories")

    if not isinstance(series, list) or not all(isinstance(x, str) and x.strip() for x in series):
        raise ValueError("config.yml: series_categories debe ser una lista de textos no vacíos.")
    if not isinstance(movies, list) or not all(isinstance(x, str) and x.strip() for x in movies):
        raise ValueError("config.yml: movie_categories debe ser una lista de textos no vacíos.")

    if len(series) != len(set(series)):
        raise ValueError("config.yml: hay categorías de series duplicadas.")
    if len(movies) != len(set(movies)):
        raise ValueError("config.yml: hay categorías de películas duplicadas.")

    return CatalogSelection(tuple(series), tuple(movies))
