from __future__ import annotations

import re
import unicodedata

TECH_RE = re.compile(r"\b(?:4k|2160p|1080p|720p|4320p|hdr10\+?|dolby.?vision|dolby.?audio|dolby.?atmos|dual.?audio|multi.?subs?|espanol|castellano|latino|vose|web.?dl|web.?rip|bluray|blu.?ray|hdtv|remux|hevc|x264|x265|h264|h265|aac|ac3|dts|uhd|fhd|sd)\b", re.I)
PREFIX_RE = re.compile(r"^(?:(?:4k|uhd|fhd|hd)\s*[-_:]\s*)?(?:[a-z0-9+]+\s*[-_:]\s*){1,3}", re.I)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = value.casefold()
    value = TECH_RE.sub(" ", value)
    value = re.sub(r"\[[^\]]*\]|\([^)]*(?:4k|2160|1080|dolby|hdr|multi|dual|audio)[^)]*\)", " ", value)
    value = re.sub(r"[^\w\s:'&-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_provider_title(value: str) -> str:
    """Remove common Xtream/provider prefixes and technical suffixes without losing the real title."""
    value = (value or "").strip()
    # Repeatedly remove known provider labels at the beginning.
    for _ in range(3):
        new = re.sub(r"^(?:4k|uhd|fhd|hd)\s*[-_:]\s*", "", value, flags=re.I)
        new = re.sub(r"^(?:amz|amazon|netflix|disney\+?|disney|apple\+?|apple|hbo|max|paramount\+?|sky|osn\+?|peacock|showtime)\s*[-_:]\s*", "", new, flags=re.I)
        if new == value:
            break
        value = new.strip()
    value = TECH_RE.sub(" ", value)
    value = re.sub(r"\b(?:19\d{2}|20\d{2})\b", lambda m: f" {m.group(0)} ", value)
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_:|")
    return value


def extract_year(title: str, year: int | None = None) -> int | None:
    if year:
        return year
    m = YEAR_RE.search(title or "")
    return int(m.group(1)) if m else None


def title_queries(provider_title: str, year: int | None = None, original_title: str | None = None) -> list[str]:
    values = [clean_provider_title(provider_title), original_title or "", provider_title]
    out = []
    for value in values:
        value = value.strip()
        if value and value not in out:
            out.append(value)
    return out


def score_candidate(provider_title: str, provider_year: int | None, candidate: dict) -> float:
    targets = {normalize_title(provider_title), normalize_title(clean_provider_title(provider_title))}
    targets.discard("")
    names = [candidate.get("title"), candidate.get("name"), candidate.get("original_title"), candidate.get("original_name")]
    normalized = [normalize_title(x) for x in names if x]
    best_score = 0.0
    for target in targets:
        target_words = set(target.split())
        for n in normalized:
            n_words = set(n.split())
            if target == n:
                best_score = max(best_score, 0.95)
                continue
            if target_words and n_words:
                overlap = len(target_words & n_words) / max(len(target_words), len(n_words))
                containment = 0.92 if target in n or n in target else 0.0
                best_score = max(best_score, max(overlap * 0.82, containment))
    date = (candidate.get("release_date") or candidate.get("first_air_date") or "")[:4]
    if provider_year and date.isdigit():
        best_score += 0.12 if int(date) == provider_year else -0.12
    return max(0.0, min(1.0, best_score))


def classify_match(score: float) -> str:
    if score >= 0.90:
        return "matched"
    if score >= 0.65:
        return "review"
    return "rejected"
