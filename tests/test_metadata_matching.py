from app.services.metadata import classify_match, clean_provider_title, score_candidate, title_queries


def test_netflix_provider_prefix_is_removed():
    assert clean_provider_title("NF - Kaleidoscope (US)") == "Kaleidoscope (US)"
    assert clean_provider_title("4K-NF - Night on Earth (GB)") == "Night on Earth (GB)"


def test_episode_query_does_not_include_episode_marker():
    assert title_queries("AMZ - Clarkson's Farm - S01E01 - Tractoring") == ["Clarkson's Farm"]


def test_exact_title_with_conflicting_year_requires_review():
    candidate = {"id": 1, "title": "Man on the Run", "release_date": "2024-01-01"}
    score = score_candidate("AMZ - Man on the Run (2026)", 2026, candidate)
    assert score < 0.86
    assert classify_match(score) == "review"


def test_exact_title_with_matching_year_remains_match():
    candidate = {"id": 1, "title": "Man on the Run", "release_date": "2026-01-01"}
    score = score_candidate("AMZ - Man on the Run (2026)", 2026, candidate)
    assert score >= 0.86
    assert classify_match(score) == "matched"
