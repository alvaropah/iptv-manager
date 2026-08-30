from __future__ import annotations

import re
import unicodedata


def normalize_category_name(value: str) -> str:
    """Normaliza espacios y mayúsculas sin eliminar caracteres útiles."""
    value = unicodedata.normalize("NFKC", value or "")
    value = value.casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value
