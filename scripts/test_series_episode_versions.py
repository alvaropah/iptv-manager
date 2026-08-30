from __future__ import annotations

from collections import defaultdict

from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile
from app.core.config import settings
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient


def category_map(items):
    result = {}
    for item in items or []:
        name = str(item.get("category_name", ""))
        result[normalize_category_name(name)] = {
            "provider_name": name,
            "provider_category_id": str(item.get("category_id", "")),
        }
    return result


def matches(selected, provider):
    return [
        (name, provider[normalize_category_name(name)])
        for name in selected
        if normalize_category_name(name) in provider
    ]


def series_by_name(client, category_id):
    items = client.series_streams(category_id)
    return {
        str(item.get("name", "")).strip().casefold(): item
        for item in (items or [])
        if item.get("name")
    }


def episode_map(detail):
    episodes = detail.get("episodes") or {}
    result = {}

    if not isinstance(episodes, dict):
        return result

    for season_no, eps in episodes.items():
        if not isinstance(eps, list):
            continue
        season_key = str(season_no)
        for ep in eps:
            if not isinstance(ep, dict):
                continue
            num = ep.get("episode_num")
            if num is None:
                continue
            result[(season_key, str(num))] = ep

    return result


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.1: EPISODIOS Y VERSIONES")
    print("=" * 72)
    print("\nObjetivo: comprobar si dos versiones de una misma serie")
    print("pueden relacionarse episodio por episodio.")
    print("No se modifica ninguna playlist.")

    cfg = load_catalog_selection()
    client = XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )

    print("\nAutenticando...")
    client.authenticate()
    print("  OK")

    provider = category_map(client.series_categories())
    selected = matches(cfg.series_categories, provider)

    print(f"Categorías SERIES seleccionadas/encontradas: {len(selected)}/{len(cfg.series_categories)}")

    # Find a pair of adjacent selected categories that actually share a series name.
    chosen = None
    chosen_series = None

    for idx in range(len(selected) - 1):
        a_name, a_cat = selected[idx]
        b_name, b_cat = selected[idx + 1]

        a_items = series_by_name(client, a_cat["provider_category_id"])
        b_items = series_by_name(client, b_cat["provider_category_id"])
        common = sorted(set(a_items) & set(b_items))

        if common:
            chosen = ((a_name, a_cat), (b_name, b_cat))
            chosen_series = a_items[common[0]]
            break

    if not chosen:
        raise RuntimeError("No se encontró un par de categorías consecutivas con una serie común.")

    (cat_a, cat_b) = chosen
    print("\nPAR DE VERSIONES ENCONTRADO")
    print(f"  A: {cat_a[0]} | category_id={cat_a[1]['provider_category_id']}")
    print(f"  B: {cat_b[0]} | category_id={cat_b[1]['provider_category_id']}")
    print(f"  Serie común: {chosen_series.get('name')}")
    print(f"  series_id A: {chosen_series.get('series_id')}")

    # Locate the matching series in B.
    b_items = series_by_name(client, cat_b[1]["provider_category_id"])
    b_series = b_items[chosen_series["name"].strip().casefold()]

    detail_a = client.series_info(str(chosen_series["series_id"]))
    detail_b = client.series_info(str(b_series["series_id"]))

    map_a = episode_map(detail_a)
    map_b = episode_map(detail_b)

    print(f"  series_id B: {b_series.get('series_id')}")
    print(f"\nEpisodios A: {len(map_a)}")
    print(f"Episodios B: {len(map_b)}")

    common = sorted(set(map_a) & set(map_b))
    only_a = sorted(set(map_a) - set(map_b))
    only_b = sorted(set(map_b) - set(map_a))

    print(f"Episodios presentes en ambas versiones: {len(common)}")
    print(f"Solo en A: {len(only_a)}")
    print(f"Solo en B: {len(only_b)}")

    profile_a = infer_category_profile(cat_a[0])
    profile_b = infer_category_profile(cat_b[0])

    print("\nMATRIZ EPISODIO → VERSIONES")
    print("-" * 72)
    for key in common[:12]:
        season, number = key
        a = map_a[key]
        b = map_b[key]
        print(
            f"S{season}E{number}: "
            f"A[id={a.get('id')}, ext={a.get('container_extension')}, "
            f"quality={profile_a.quality or '?'}] | "
            f"B[id={b.get('id')}, ext={b.get('container_extension')}, "
            f"quality={profile_b.quality or '?'}]"
        )

    if only_a:
        print("\nEJEMPLOS SOLO EN A:")
        for key in only_a[:5]:
            print(f"  S{key[0]}E{key[1]} | id={map_a[key].get('id')}")

    if only_b:
        print("\nEJEMPLOS SOLO EN B:")
        for key in only_b[:5]:
            print(f"  S{key[0]}E{key[1]} | id={map_b[key].get('id')}")

    print("\n" + "=" * 72)
    print("PRUEBA 5.1 COMPLETADA")
    print("Se ha probado la relación episodio-a-episodio entre dos versiones.")
    print("No se ha sincronizado el catálogo completo.")
    print("=" * 72)


if __name__ == "__main__":
    main()
