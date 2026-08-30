from __future__ import annotations

import sys

from app.core.catalog_config import load_catalog_selection
from app.core.config import settings
from app.core.xtream import XtreamClient


def category_map(data):
    if not isinstance(data, list):
        return {}
    return {str(item.get("category_name", "")): str(item.get("category_id", ""))
            for item in data if isinstance(item, dict) and item.get("category_name")}


def report_selection(title: str, configured: tuple[str, ...], available: dict[str, str]) -> None:
    found = [name for name in configured if name in available]
    missing = [name for name in configured if name not in available]
    print(f"\n{title}")
    print(f"   Configuradas: {len(configured)}")
    print(f"   Encontradas:  {len(found)}")
    print(f"   No encontradas: {len(missing)}")
    for name in missing:
        print(f"   ❌ {name}")
    if found:
        print("   IDs seleccionados (muestra):")
        for name in found[:10]:
            print(f"      - {available[name]}: {name}")


def main() -> int:
    print("============================================================")
    print("IPTV MANAGER — PRUEBA 2: CONFIGURACIÓN CENTRAL")
    print("============================================================")

    selection = load_catalog_selection()
    print(f"\nConfiguración cargada desde: config.yml")
    print(f"   Series seleccionadas: {len(selection.series_categories)}")
    print(f"   Películas seleccionadas: {len(selection.movie_categories)}")
    print(f"   Total categorías VOD seleccionadas: {selection.total_vod_categories}")
    print("   LIVE: no se filtra aquí; queda independiente del catálogo VOD.")

    client = XtreamClient(settings.xtream_host, settings.xtream_username, settings.xtream_password)

    print("\nAutenticando contra Xtream...")
    auth = client.authenticate()
    user_info = auth.get("user_info", {}) if isinstance(auth, dict) else {}
    print(f"   OK — estado: {user_info.get('status', 'desconocido')}")

    print("Consultando categorías reales...")
    live = category_map(client.live_categories())
    vod = category_map(client.vod_categories())
    series = category_map(client.series_categories())
    print(f"   LIVE proveedor: {len(live)}")
    print(f"   VOD proveedor: {len(vod)}")
    print(f"   SERIES proveedor: {len(series)}")

    report_selection("SELECCIÓN DE SERIES — según config.yml", selection.series_categories, series)
    report_selection("SELECCIÓN DE PELÍCULAS — según config.yml", selection.movie_categories, vod)

    print("\n============================================================")
    print("PRUEBA COMPLETADA — todavía NO se ha descargado el catálogo.")
    print("El Core ya queda gobernado por la selección de config.yml.")
    print("============================================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
