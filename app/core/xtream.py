from __future__ import annotations

from typing import Any

import requests


class XtreamClient:
    """Cliente reutilizable para la API Xtream."""

    def __init__(self, host: str, username: str, password: str, timeout: int = 60):
        if not host:
            raise ValueError("XTREAM_HOST no está configurado.")
        if not username or not password:
            raise ValueError("Faltan XTREAM_USERNAME o XTREAM_PASSWORD.")

        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "IPTV-Manager/0.1"})

    def api(self, action: str | None = None) -> Any:
        params = {"username": self.username, "password": self.password}
        if action:
            params["action"] = action

        response = self.session.get(
            f"{self.host}/player_api.php",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def authenticate(self) -> dict[str, Any]:
        data = self.api()
        user_info = data.get("user_info", {}) if isinstance(data, dict) else {}

        if str(user_info.get("auth", "1")) == "0":
            raise RuntimeError("Xtream ha rechazado las credenciales.")

        return data

    def live_categories(self):
        return self.api("get_live_categories")

    def vod_categories(self):
        return self.api("get_vod_categories")

    def series_categories(self):
        return self.api("get_series_categories")
