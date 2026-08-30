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

    def movie(self, external_id: int, language: str | None = None) -> dict:
        return self._get(f"/movie/{external_id}", language=language, append_to_response="credits,images", include_image_language="es,null")

    def tv(self, external_id: int, language: str | None = None) -> dict:
        return self._get(f"/tv/{external_id}", language=language, append_to_response="credits,images", include_image_language="es,null")

    def alternative_titles(self, external_id: int, content_type: str, language: str | None = None) -> list[str]:
        path = f"/movie/{external_id}/alternative_titles" if content_type == "movie" else f"/tv/{external_id}/alternative_titles"
        data = self._get(path, language=language)
        items = data.get("titles") or data.get("results") or []
        return [x.get("title") for x in items if x.get("title")]

    def alternative_titles_multilang(self, external_id: int, content_type: str) -> list[str]:
        """Return alternative titles from the configured locale and English."""
        out: list[str] = []
        for language in (self.language or "es-ES", "en-US"):
            if language in (None, ""):
                continue
            try:
                for title in self.alternative_titles(external_id, content_type, language=language):
                    if title not in out:
                        out.append(title)
            except requests.RequestException:
                continue
        return out

    def episode(self, series_id: int, season: int, episode: int, language: str | None = None) -> dict:
        return self._get(f"/tv/{series_id}/season/{season}/episode/{episode}", language=language, append_to_response="credits,images", include_image_language="es,null")
