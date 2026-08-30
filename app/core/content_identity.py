from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TECHNICAL_TOKEN_RE = re.compile(
    r"\b(?:4k|8k|2160p|3840p|1080p|720p|hdr|dolby(?:\s+vision|\s+audio)?|"
    r"multi(?:\s*-\s*)?subs?|subtitles?|dual\s+audio)\b",
    re.IGNORECASE,
)
LANGUAGE_TOKEN_RE = re.compile(
    r"(?:\bes\b|\besp\b|\bespana\b|\ben\b|\beng\b|\benglish\b|"
    r"\bfr\b|\bfra\b|\bfrench\b)",
    re.IGNORECASE,
)
SEASON_EPISODE_RE = re.compile(r"\bS\d{1,3}(?:E\d{1,3})+\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class IdentityAnalysis:
    original: str
    normalized: str
    canonical: str
    year: int | None
    technical_tokens_removed: tuple[str, ...]
    language_tokens_removed: tuple[str, ...]
    season_episode_removed: tuple[str, ...]


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.casefold()
    return re.sub(r"\s+", " ", value).strip()


def _clean(value: str) -> str:
    value = _fold(value)
    value = re.sub(r"[\[\]{}()]", " ", value)
    value = re.sub(r"[_|]+", " ", value)
    value = re.sub(r"[-–—]+", " ", value)
    value = re.sub(r"[^a-z0-9+&'.: ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def analyze_title(value: str) -> IdentityAnalysis:
    original = str(value or "").strip()
    text = unicodedata.normalize("NFKC", original)

    technical = tuple(dict.fromkeys(
        m.group(0) for m in TECHNICAL_TOKEN_RE.finditer(text)
    ))
    languages = tuple(dict.fromkeys(
        m.group(0) for m in LANGUAGE_TOKEN_RE.finditer(text)
    ))
    season_episode = tuple(dict.fromkeys(
        m.group(0) for m in SEASON_EPISODE_RE.finditer(text)
    ))

    canonical = _clean(text)
    canonical = TECHNICAL_TOKEN_RE.sub(" ", canonical)
    canonical = LANGUAGE_TOKEN_RE.sub(" ", canonical)
    canonical = SEASON_EPISODE_RE.sub(" ", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip(" .:-")

    year_match = YEAR_RE.search(text)
    year = int(year_match.group(0)) if year_match else None

    return IdentityAnalysis(
        original=original,
        normalized=_clean(text),
        canonical=canonical,
        year=year,
        technical_tokens_removed=technical,
        language_tokens_removed=languages,
        season_episode_removed=season_episode,
    )


def normalize_content_title(value: str) -> str:
    return analyze_title(value).canonical


def display_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip()
    return re.sub(r"\s+", " ", text)
