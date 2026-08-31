from app.services.metadata import (
    classify_match,
    clean_provider_title,
    explain_match,
    score_candidate,
    title_queries,
)


def test_netflix_provider_prefix_is_removed():
    assert clean_provider_title("NF - Kaleidoscope (US)") == "Kaleidoscope (US)"
    assert clean_provider_title("4K-NF - Night on Earth (GB)") == "Night on Earth (GB)"


def test_locale_provider_prefix_is_removed():
    assert clean_provider_title("ES - Steins;Gate 0 (2018) (JP)") == "Steins;Gate 0 (2018) (JP)"


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


def test_country_match_can_disambiguate_same_title():
    provider = "AMZ - Kaleidoscope (US)"
    us = {"id": 156902, "title": "Kaleidoscope", "origin_country": ["US"]}
    gb = {"id": 9678, "title": "Kaleidoscope", "origin_country": ["GB"]}
    assert score_candidate(provider, None, us, "US") > score_candidate(provider, None, gb, "US")


def test_country_conflict_does_not_create_false_perfect_match():
    provider = "AMZ - Kaleidoscope (US)"
    candidate = {"id": 9678, "title": "Kaleidoscope", "origin_country": ["GB"]}
    score = score_candidate(provider, None, candidate, "US")
    assert score < 0.96
    assert "country_conflict" in explain_match(provider, None, candidate, "US")


def test_explain_match_reports_year_and_title_evidence():
    candidate = {"id": 1, "title": "Man on the Run", "release_date": "2026-01-01"}
    reasons = explain_match("AMZ - Man on the Run (2026)", 2026, candidate)
    assert "exact_title" in reasons
    assert "year_match" in reasons
