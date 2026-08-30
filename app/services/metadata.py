from __future__ import annotations

import re
import unicodedata


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = value.casefold()
    value = re.sub(r"\b(4k|2160p|1080p|720p|hdr10\+?|dolby.?vision|dolby.?audio|dual.?audio|multi.?subs?|espanol|castellano|latino|vose|web.?dl|web.?rip|bluray|hdtv)\b", " ", value)
    value = re.sub(r"\[[^\]]*\]|\([^)]*(?:4k|2160|1080|dolby|hdr|multi)[^)]*\)", " ", value)
    value = re.sub(r"[^\w\s:'&-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_year(title: str, year: int | None = None) -> int | None:
    if year:
        return year
    m = re.search(r"\b(19\d{2}|20\d{2})\b", title or "")
    return int(m.group(1)) if m else None


def score_candidate(provider_title: str, provider_year: int | None, candidate: dict) -> float:
    target = normalize_title(provider_title)
    names = [candidate.get("title"), candidate.get("name"), candidate.get("original_title"), candidate.get("original_name")]
    normalized = [normalize_title(x) for x in names if x]
    if target and target in normalized:
        score = 1.0
    else:
        words = set(target.split())
        best = max((len(words & set(n.split())) / max(len(words), len(set(n.split())), 1) for n in normalized), default=0.0)
        score = best * 0.85
    date = (candidate.get("release_date") or candidate.get("first_air_date") or "")[:4]
    if provider_year and date.isdigit():
        score += 0.12 if int(date) == provider_year else -0.10
    return max(0.0, min(1.0, score))


def classify_match(score: float) -> str:
    if score >= 0.90:
        return "matched"
    if score >= 0.65:
        return "review"
    return "rejected"
