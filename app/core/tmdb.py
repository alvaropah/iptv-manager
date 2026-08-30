from __future__ import annotations

import requests

BASE_URL = "https://api.themoviedb.org/3"


class TMDBClient:
    def __init__(self, token: str, language: str = "es-ES") -> None:
        self.token = token
        self.language = language

    def _get(self, path: str, language: str | None = None, **params):
        selected_language = language or self.language
        r = requests.get(
            f"{BASE_URL}{path}",
            params={"language": selected_language, **params},
            headers={"Authorization": f"Bearer {self.token}", "accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def search_movie(self, title: str, year: int | None = None, language: str | None = None) -> list[dict]:
        params = {"query": title}
        if year:
            params["primary_release_year"] = year
        return self._get("/search/movie", language=language, **params).get("results", [])

    def search_tv(self, title: str, year: int | None = None, language: str | None = None) -> list[dict]:
        params = {"query": title}
        if year:
            params["first_air_date_year"] = year
        return self._get("/search/tv", language=language, **params).get("results", [])

    def movie(self, external_id: int) -> dict:
        return self._get(f"/movie/{external_id}", append_to_response="credits,images", include_image_language="es,null")

    def tv(self, external_id: int) -> dict:
        return self._get(f"/tv/{external_id}", append_to_response="credits,images", include_image_language="es,null")

    def episode(self, series_id: int, season: int, episode: int) -> dict:
        return self._get(f"/tv/{series_id}/season/{season}/episode/{episode}", append_to_response="credits,images", include_image_language="es,null")
