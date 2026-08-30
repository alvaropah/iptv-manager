from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryProfile:
    quality: str | None = None
    resolution: str | None = None
    dynamic_range: str | None = None
    audio: str | None = None
    subtitles: bool | None = None
    language_hint: str | None = None


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.casefold()
    return re.sub(r"\s+", " ", value).strip()


def infer_category_profile(category_name: str) -> CategoryProfile:
    n = _fold(category_name)

    quality = None
    resolution = None
    dynamic_range = None
    audio = None
    subtitles = None
    language_hint = None

    if re.search(r"\b8k\b", n):
        quality, resolution = "8K", "4320p"
    elif re.search(r"\b4k\b|3840p", n):
        quality, resolution = "4K", "2160p"
    elif re.search(r"\b1080p\b|\bfhd\b|\bfull hd\b", n):
        quality, resolution = "1080p", "1080p"
    elif re.search(r"\b720p\b|\bhd\b", n):
        quality, resolution = "720p", "720p"

    if "dolby vision" in n:
        dynamic_range = "Dolby Vision"
    elif re.search(r"\bhdr\b", n):
        dynamic_range = "HDR"

    if "dolby audio" in n:
        audio = "Dolby Audio"

    if "subtitles" in n or "subtitle" in n or "subtitled" in n:
        subtitles = True

    if re.search(r"\bespaña\b|\bes(?:-|$)", n):
        language_hint = "es"
    elif re.search(r"\benglish\b|\beng(?:-|$)", n):
        language_hint = "en"
    elif re.search(r"\bfrench\b|\bfrançais\b|\bfra(?:-|$)", n):
        language_hint = "fr"

    return CategoryProfile(
        quality=quality,
        resolution=resolution,
        dynamic_range=dynamic_range,
        audio=audio,
        subtitles=subtitles,
        language_hint=language_hint,
    )
