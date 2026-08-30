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
    value = re.sub(r"\s+", " ", value).strip()
    return value


def infer_category_profile(category_name: str) -> CategoryProfile:
    """
    Conservative interpretation of category metadata.

    Only signals explicitly present in the category name are inferred.
    The original category name remains authoritative provenance.
    """
    n = _fold(category_name)

    quality = None
    resolution = None
    dynamic_range = None
    audio = None
    subtitles = None
    language_hint = None

    if re.search(r"\b8k\b|⁸ᴷ", n):
        quality = "8K"
        resolution = "4320p"
    elif re.search(r"\b4k\b|3840p|⁴ᴷ|³⁸⁴⁰ᴾ", n):
        quality = "4K"
        resolution = "2160p"
    elif re.search(r"\b2k\b", n):
        quality = "2K"
    elif re.search(r"\b1080p\b|\bfhd\b|\bfull hd\b", n):
        quality = "1080p"
        resolution = "1080p"
    elif re.search(r"\b720p\b|\bhd\b", n):
        quality = "720p"
        resolution = "720p"

    if "dolby vision" in n or "dolby ⱽᶦˢᶦᵒⁿ" in n or "ᴴᴰᴿ" in category_name:
        dynamic_range = "Dolby Vision"
    elif re.search(r"\bhdr\b|ᴴᴰᴿ", n):
        dynamic_range = "HDR"

    if "dolby audio" in n or "ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ" in category_name:
        audio = "Dolby Audio"

    if "subtitles" in n or "subtitle" in n or "subtitled" in n:
        subtitles = True

    # Language is deliberately only a hint when the category name is explicit.
    if re.search(r"\bespaña\b|\bes\b(?:-|$)", n):
        language_hint = "es"
    elif re.search(r"\benglish\b|\beng\b", n):
        language_hint = "en"
    elif re.search(r"\bfrançais\b|\bfrench\b|\bfra\b", n):
        language_hint = "fr"

    return CategoryProfile(
        quality=quality,
        resolution=resolution,
        dynamic_range=dynamic_range,
        audio=audio,
        subtitles=subtitles,
        language_hint=language_hint,
    )
