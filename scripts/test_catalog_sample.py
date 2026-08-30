from __future__ import annotations

import json
import sys

from app.core.config import settings
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient
from app.config_loader import load_config


def category_map(items):
    result = {}
    for item in items or []:
        name = str(item.get("category_name", ""))
        cid = str(item.get("category_id", ""))
        result[normalize_category_name(name)] = {
            "provider_name": name,
            "provider_category_id": cid,
        }
    return result


def main() -> int:
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 3: DESCUBRIMIENTO DE CATÁLOGO")
    print("=" * 72)

    cfg = load_config()
    client = XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )

    print("\nAutenticando...")
    client.authenticate()
    print("   OK")

    print("\nConsultando categorías...")
    provider_vod = category_map(client.vod_categories())
    provider_series = category_map(client.series_categories())

    selected_vod = cfg.movie_categories
    selected_series = cfg.series_categories

    # Use normalized matching so "NETFLIX SERIES" matches "NETFLIX  SERIES".
    selected_vod_matches = [
        (name, provider_vod[normalize_category_name(name)])
        for name in selected_vod
        if normalize_category_name(name) in provider_vod
    ]
    selected_series_matches = [
        (name, provider_series[normalize_category_name(name)])
        for name in selected_series
        if normalize_category_name(name) in provider_series
    ]

    print(
        f"   Categorías VOD seleccionadas: {len(selected_vod)} "
        f"→ encontradas: {len(selected_vod_matches)}"
    )
    print(
        f"   Categorías SERIES seleccionadas: {len(selected_series)} "
        f"→ encontradas: {len(selected_series_matches)}"
    )

    missing = [
        name for name in selected_series
        if normalize_category_name(name) not in provider_series
    ]
    missing += [
        name for name in selected_vod
        if normalize_category_name(name) not in provider_vod
    ]

    if missing:
        print("\n   Categorías no encontradas:")
        for name in missing:
            print(f"      - {name}")
    else:
        print("   Todas las categorías seleccionadas tienen correspondencia.")

    # Small sample: first matching series and first matching movie category.
    if not selected_series_matches or not selected_vod_matches:
        print("\nNo hay categorías suficientes para hacer la muestra.")
        return 1

    series_config_name, series_cat = selected_series_matches[0]
    vod_config_name, vod_cat = selected_vod_matches[0]

    print("\n" + "-" * 72)
    print("MUESTRA SERIES")
    print("-" * 72)
    print(f"Categoría configurada: {series_config_name}")
    print(f"Categoría proveedor:  {series_cat['provider_name']}")
    print(f"category_id:          {series_cat['provider_category_id']}")

    series_items = client.series_streams(series_cat["provider_category_id"])
    if not isinstance(series_items, list):
        print(f"Respuesta inesperada: {type(series_items).__name__}")
        return 1

    print(f"Series devueltas por Xtream: {len(series_items)}")
    for item in series_items[:3]:
        print(
            f"  - series_id={item.get('series_id')} | "
            f"name={item.get('name')} | "
            f"category_id={item.get('category_id')}"
        )

    if series_items:
        sample_series_id = str(series_items[0].get("series_id"))
        print(f"\nConsultando detalle de serie: {sample_series_id}")
        detail = client.series_info(sample_series_id)

        if not isinstance(detail, dict):
            print(f"Respuesta inesperada: {type(detail).__name__}")
            return 1

        seasons = detail.get("seasons") or []
        episodes = detail.get("episodes") or {}

        print(f"  Nombre: {detail.get('info', {}).get('name', detail.get('name', '?'))}")
        print(f"  Temporadas: {len(seasons)}")
        print(f"  Claves de episodios: {len(episodes) if isinstance(episodes, dict) else 0}")

        if seasons:
            s = seasons[0]
            print(
                f"  Primera temporada: {s.get('season_number')} | "
                f"{s.get('name', '')}"
            )

        if isinstance(episodes, dict):
            shown = 0
            for season_no, eps in episodes.items():
                print(f"  Temporada {season_no}: {len(eps) if isinstance(eps, list) else 0} episodios")
                if isinstance(eps, list) and eps:
                    ep = eps[0]
                    print("    Primer episodio:")
                    print(
                        f"      id={ep.get('id')} | "
                        f"episode_num={ep.get('episode_num')} | "
                        f"title={ep.get('title')} | "
                        f"container={ep.get('container_extension')}"
                    )
                    print(
                        f"      video={ep.get('video')} | "
                        f"audio={ep.get('audio')}"
                    )
                    shown += 1
                if shown >= 2:
                    break

    print("\n" + "-" * 72)
    print("MUESTRA PELÍCULAS / VOD")
    print("-" * 72)
    print(f"Categoría configurada: {vod_config_name}")
    print(f"Categoría proveedor:  {vod_cat['provider_name']}")
    print(f"category_id:          {vod_cat['provider_category_id']}")

    vod_items = client.vod_streams(vod_cat["provider_category_id"])
    if not isinstance(vod_items, list):
        print(f"Respuesta inesperada: {type(vod_items).__name__}")
        return 1

    print(f"Películas devueltas por Xtream: {len(vod_items)}")
    for item in vod_items[:5]:
        print(
            f"  - stream_id={item.get('stream_id')} | "
            f"name={item.get('name')} | "
            f"year={item.get('year')} | "
            f"rating={item.get('rating')} | "
            f"ext={item.get('container_extension')}"
        )

    print("\n" + "=" * 72)
    print("PRUEBA 3 COMPLETADA")
    print("Solo se han consultado muestras; todavía NO se sincroniza todo el catálogo.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
