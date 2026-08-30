from __future__ import annotations

import time

import requests

BASE_URL = "https://api.tvmaze.com"


class TVMazeClient:
    """Small client for the public TVmaze API used as a secondary source.

    TVmaze exposes show search and episode-by-season/number endpoints, so it is
    useful when TMDB has a show but is missing a season/episode.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.timeout = (5, 15)
        self.max_retries = 3

    def _get(self, path: str, **params):
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers={"accept": "application/json", "User-Agent": "iptv-manager/1.0"},
                    timeout=self.timeout,
                )
                if response.status_code == 404:
                    response.raise_for_status()
                if response.status_code == 429 and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after), 10.0) if retry_after else 2 ** (attempt - 1)
                    except ValueError:
                        delay = 2 ** (attempt - 1)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                status = getattr(exc.response, "status_code", None)
                if status == 404 or attempt >= self.max_retries:
                    raise
                time.sleep(2 ** (attempt - 1))
        assert last_error is not None
        raise last_error

    def search_shows(self, query: str) -> list[dict]:
        return self._get("/search/shows", q=query)

    def episode(self, show_id: int, season: int, number: int) -> dict:
        return self._get(
            "/shows/{}/episodebynumber".format(show_id),
            season=season,
            number=number,
        )
