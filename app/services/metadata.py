from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

TECH_RE = re.compile(r"\b(?:4k|2160p|1080p|720p|4320p|hdr10\+?|dolby.?vision|dolby.?audio|dolby.?atmos|dual.?audio|multi.?subs?|espanol|castellano|latino|vose|web.?dl|web.?rip|bluray|blu.?ray|hdtv|remux|hevc|x264|x265|h264|h265|aac|ac3|dts|uhd|fhd|sd)\b", re.I)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
COUNTRY_SUFFIX_RE = re.compile(r"\s*\([A-Z]{2}\)\s*$")
PROVIDER_PREFIX_RE = re.compile(r"^(?:4k|8k|uhd|fhd|hd|amz|amazon|netflix|disney\+?|disney|apple\+?|apple|hbo|max|paramount\+?|sky|osn\+?|peacock|showtime|prime\+?|prime|crunchyroll|discovery\+?|discovery|vix(?:\s+premium)?|movistar|atresplayer|rtve|starz|hulu|viaplay|filmin|rakuten|nickelodeon|marvel)\s*[-_:|]\s*", re.I)

# Significant installment markers. These are identity evidence, not removable noise.
INSTALLMENT_RE = re.compile(r"\b(?:vol(?:ume)?\.?\s*\d+|part\s*\d+|pt\.?\s*\d+|chapter\s*\d+|special\s*\d+|season\s*\d+|series\s*\d+)\b", re.I)
SEQUEL_RE = re.compile(r"(?<!\w)(\d{1,2})(?!\w)")


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = value.casefold()
    value = TECH_RE.sub(" ", value)
    value = re.sub(r"\[[^\]]*\]|\([^)]*(?:4k|2160|1080|dolby|hdr|multi|dual|audio)[^)]*\)", " ", value)
    value = re.sub(r"[()\[\]]", " ", value)
    value = re.sub(r"[^\w\s:'&.-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_provider_title(value: str) -> str:
    value = (value or "").strip()
    previous = None
    while value and value != previous:
        previous = value
        value = PROVIDER_PREFIX_RE.sub("", value).strip()
    value = TECH_RE.sub(" ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_:|")
    return value


def extract_year(title: str, year: int | None = None) -> int | None:
    if year:
        return year
    m = YEAR_RE.search(title or "")
    return int(m.group(1)) if m else None


def _clean_search_title(value: str) -> str:
    """Build a TMDB search title without provider/year/country packaging noise."""
    value = clean_provider_title(value)
    value = YEAR_RE.sub(" ", value)
    # Provider feeds commonly append the two-letter origin country after the year,
    # e.g. "Clarkson's Farm (2021) (GB)". It is search metadata, not part of title.
    value = COUNTRY_SUFFIX_RE.sub(" ", value)
    value = re.sub(r"\(\s*\)|\[\s*\]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_:|()[]")
    return value


def title_queries(provider_title: str, year: int | None = None, original_title: str | None = None) -> list[str]:
    values = [provider_title]
    if original_title:
        values.append(original_title)
    out: list[str] = []
    for value in values:
        value = _clean_search_title(value)
        if value and value not in out:
            out.append(value)
    return out


def _title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    direct = SequenceMatcher(None, a, b).ratio()
    aw, bw = set(a.split()), set(b.split())
    overlap = len(aw & bw) / max(len(aw), len(bw), 1)
    return max(direct, overlap)


def _candidate_names(candidate: dict) -> list[str]:
    names = [candidate.get("title"), candidate.get("name"), candidate.get("original_title"), candidate.get("original_name")]
    names.extend(candidate.get("_locale_variants", []))
    alternatives = candidate.get("alternative_titles") or []
    if isinstance(alternatives, dict):
        alternatives = alternatives.get("titles") or alternatives.get("results") or []
    for item in alternatives:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            names.extend([item.get("title"), item.get("name")])
    return [x for x in names if isinstance(x, str) and x.strip()]


def _installment_signature(value: str) -> tuple[tuple[str, str], ...]:
    """Extract meaningful installment markers so Vol. 2 cannot match Vol. 3."""
    text = normalize_title(value)
    markers: list[tuple[str, str]] = []
    for match in INSTALLMENT_RE.finditer(text):
        token = re.sub(r"\s+", "", match.group(0).casefold()).replace("volume", "vol")
        number = re.search(r"\d+", token)
        markers.append(("installment", f"{token}:{number.group(0) if number else ''}"))
    # Standalone sequel numbers are meaningful only when they occur at the end of a title.
    end = re.search(r"(?:^|\s)(\d{1,2})$", text)
    if end:
        markers.append(("sequel", end.group(1)))
    return tuple(markers)


def _marker_conflict(provider: str, candidate: str) -> bool:
    p = _installment_signature(provider)
    c = _installment_signature(candidate)
    if not p or not c:
        return False
    return p != c


def score_candidate(provider_title: str, provider_year: int | None, candidate: dict) -> float:
    clean = YEAR_RE.sub(" ", clean_provider_title(provider_title))
    raw = YEAR_RE.sub(" ", provider_title or "")
    targets = [normalize_title(x) for x in (clean, raw) if x]
    names = _candidate_names(candidate)
    normalized = [normalize_title(x) for x in names]
    best = max((_title_similarity(target, name) for target in targets for name in normalized), default=0.0)

    # A conflicting volume/part/special/sequel number is strong evidence of a different title.
    if any(_marker_conflict(provider_title, name) for name in names):
        best = min(best, 0.35)

    date = (candidate.get("release_date") or candidate.get("first_air_date") or "")[:4]
    if provider_year and date.isdigit():
        if int(date) == provider_year:
            best = min(1.0, best + 0.18)
        elif best < 0.90:
            best = max(0.0, best - 0.10)
    return round(best, 4)


def classify_match(score: float) -> str:
    if score >= 0.86:
        return "matched"
    if score >= 0.62:
        return "review"
    return "rejected"
