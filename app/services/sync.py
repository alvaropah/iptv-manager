from __future__ import annotations

from app.core.config import settings
from app.core.xtream import XtreamClient


def build_xtream_client() -> XtreamClient:
    return XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )


def test_connection() -> dict:
    client = build_xtream_client()
    auth = client.authenticate()
    user_info = auth.get("user_info", {}) if isinstance(auth, dict) else {}

    return {
        "connected": True,
        "status": user_info.get("status"),
        "exp_date": user_info.get("exp_date"),
    }
