from __future__ import annotations

import re
import unicodedata


def normalize_content_title(value: str) -> str:
    """Normalize a title for candidate matching, without guessing identity."""
    text = unicodedata.normalize("NFKC", value or "").strip()
    text = re.sub(r"^\s*(?:4k|8k)\s*[-:]\s*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def display_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip()
    text = re.sub(r"^\s*(?:4k|8k)\s*[-:]\s*", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text)
