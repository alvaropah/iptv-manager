from unittest.mock import Mock

import requests

from scripts.enrich_tmdb_episodes import resolve_episode_with_fallback


def _http_404() -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 404
    return requests.HTTPError(response=response)


def test_tvmaze_fallback_is_used_when_primary_and_alternate_tmdb_fail():
    tmdb = Mock()
    tmdb.episode.side_effect = _http_404()
    tmdb.search_tv.return_value = []

    tvmaze = Mock()
    tvmaze.search_shows.return_value = [
        {"show": {"id": 9765, "name": "The Simpsons", "premiered": "1989-12-17"}}
    ]
    tvmaze.episode.return_value = {
        "id": 123456,
        "name": "Pilot",
        "airdate": "1989-12-17",
        "summary": "Fallback episode from TVmaze",
    }

    row = {
        "provider_title": "The Simpsons",
        "season_number": 1,
        "episode_number": 1,
    }

    result, matched_by = resolve_episode_with_fallback(
        tmdb,
        row,
        "999999",
        tvmaze,
        {},
        diagnostic=False,
    )

    assert result["id"] == 123456
    assert result["name"] == "Pilot"
    assert matched_by.startswith("tvmaze+season_number+episode_number+")
    tvmaze.episode.assert_called_once_with(9765, 1, 1)
