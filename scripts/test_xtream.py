from __future__ import annotations

import json
import sys

from app.core.config import settings
from app.core.xtream import XtreamClient


def main() -> int:
    print("============================================================")
    print("IPTV MANAGER — PRUEBA 1: CONEXIÓN Y CATEGORÍAS")
    print("============================================================")

    client = XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )

    print("\n1. Autenticando contra Xtream...")
    auth = client.authenticate()
    user_info = auth.get("user_info", {}) if isinstance(auth, dict) else {}

    print("   OK — autenticación correcta.")
    print(f"   Estado: {user_info.get('status', 'desconocido')}")

    print("\n2. Consultando categorías LIVE...")
    live = client.live_categories()
    print(f"   OK — {len(live) if isinstance(live, list) else 0} categorías.")

    print("\n3. Consultando categorías VOD...")
    vod = client.vod_categories()
    print(f"   OK — {len(vod) if isinstance(vod, list) else 0} categorías.")

    print("\n4. Consultando categorías SERIES...")
    series = client.series_categories()
    print(f"   OK — {len(series) if isinstance(series, list) else 0} categorías.")

    def show_sample(title: str, data):
        print(f"\n{title}")
        if not isinstance(data, list):
            print("   Respuesta no esperada.")
            return
        for item in data[:5]:
            print(
                f"   - {item.get('category_id', '?')}: "
                f"{item.get('category_name', '?')}"
            )

    show_sample("Muestra LIVE:", live)
    show_sample("Muestra VOD:", vod)
    show_sample("Muestra SERIES:", series)

    print("\n============================================================")
    print("PRUEBA COMPLETADA — todavía NO se ha descargado el catálogo.")
    print("============================================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
