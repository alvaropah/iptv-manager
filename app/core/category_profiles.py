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
    """Normalize provider's normal and Unicode-styled lettering."""
    value = unicodedata.normalize("NFKD", value or "")
    # Remove combining marks so ñ/á/é/etc. are matched consistently.
    value = "".join(
        ch for ch in value if unicodedata.category(ch) != "Mn"
    )
    # Some provider category names use modifier/phonetic Unicode letters
    # that NFKD leaves behind (e.g. ɪ in stylized Dolby Vision).
    value = value.translate(str.maketrans({
        "ɪ": "i",
        "ʏ": "y",
        "ʀ": "r",
        "ʙ": "b",
        "ʟ": "l",
        "ᴅ": "d",
        "ᴏ": "o",
        "ᴌ": "l",
        "ᴇ": "e",
        "ᴍ": "m",
        "ᴠ": "v",
        "ᴰ": "D",
        "ᴼ": "O",
        "ᴸ": "L",
        "ᴮ": "B",
        "ʸ": "y",
        "ⱽ": "V",
        "ᴵ": "I",
        "ˢ": "s",
        "ᶦ": "i",
        "ᵒ": "o",
        "ˡ": "l",
        "ᵇ": "b",
        "ⁱ": "i",
        "ⁿ": "n",
    }))
    value = value.casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def infer_category_profile(category_name: str) -> CategoryProfile:
    """Conservative category signals; no stream-level facts are invented."""
    n = _fold(category_name)

    quality = resolution = dynamic_range = audio = language_hint = None
    subtitles = None

    if re.search(r"\b8k\b", n):
        quality, resolution = "8K", "4320p"
    elif re.search(r"\b4k\b|3840p", n):
        quality, resolution = "4K", "2160p"
    elif re.search(r"\b1080p\b|\bfhd\b|\bfull hd\b", n):
        quality, resolution = "1080p", "1080p"
    elif re.search(r"\b720p\b|\bhd\b", n):
        quality, resolution = "720p", "720p"

    # Dolby Vision is more specific than generic HDR, so it wins.
    if "dolby vision" in n:
        dynamic_range = "Dolby Vision"
    elif re.search(r"\bhdr\b", n):
        dynamic_range = "HDR"

    if "dolby audio" in n:
        audio = "Dolby Audio"

    if re.search(r"\bsubtitles?\b|\bsubtitled\b|\bsubs\b", n):
        subtitles = True

    if re.search(r"^es\s*[-–—]", n) or re.search(r"\bespana\b", n):
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
