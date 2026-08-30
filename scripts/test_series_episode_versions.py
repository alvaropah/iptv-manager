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
        name = str(item.get("category_name", "")).strip()
        result[normalize_category_name(name)] = {
            "provider_name": name,
            "provider_category_id": str(item.get("category_id", "")),
        }
    return result


def selected_categories(selected, provider):
    return [
        (name, provider[normalize_category_name(name)])
        for name in selected
        if normalize_category_name(name) in provider
    ]


def normalized_series_name(name: str) -> str:
    return " ".join(str(name or "").casefold().split())


def get_series_items(client, category_id):
    items = client.series_streams(category_id)
    return {
        normalized_series_name(item.get("name")): item
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
        for ep in eps:
            if not isinstance(ep, dict):
                continue
            number = ep.get("episode_num")
            if number is None:
                continue
            result[(str(season_no), str(number))] = ep

    return result


def find_shared_series(client, categories):
    """
    Find real shared series across ANY selected categories.

    We deliberately do not assume that version categories are adjacent.
    """
    occurrences = defaultdict(list)

    for index, (category_name, category) in enumerate(categories):
        items = get_series_items(client, category["provider_category_id"])
        print(
            f"  [{index + 1}/{len(categories)}] {category_name}: "
            f"{len(items)} series"
        )

        for key, item in items.items():
            occurrences[key].append(
                {
                    "category_name": category_name,
                    "category_id": category["provider_category_id"],
                    "item": item,
                }
            )

    shared = [
        (key, entries)
        for key, entries in occurrences.items()
        if len(entries) >= 2
    ]

    # Prefer pairs whose category profiles carry different technical signals,
    # especially a normal/4K pair. This makes the test meaningful.
    def score(pair):
        _, entries = pair
        profiles = [
            infer_category_profile(e["category_name"])
            for e in entries
        ]
        qualities = {p.quality for p in profiles if p.quality}
        dynamic = {p.dynamic_range for p in profiles if p.dynamic_range}
        audio = {p.audio for p in profiles if p.audio}
        return (
            100 if "4K" in qualities and len(qualities) > 1 else 0,
            20 if len(qualities) > 1 else 0,
            10 if dynamic else 0,
            5 if audio else 0,
            len(entries),
        )

    shared.sort(key=score, reverse=True)
    return shared


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.1: EPISODIOS Y VERSIONES")
    print("=" * 72)
    print("\nObjetivo: encontrar automáticamente una misma serie")
    print("en varias categorías seleccionadas y comparar sus episodios.")
    print("No se modifica ninguna playlist.")
    print("Las categorías NO tienen que ser consecutivas.")

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
    selected = selected_categories(cfg.series_categories, provider)

    print(
        f"\nCategorías SERIES seleccionadas/encontradas: "
        f"{len(selected)}/{len(cfg.series_categories)}"
    )

    if len(selected) < 2:
        raise RuntimeError("No hay suficientes categorías seleccionadas.")

    print("\nBUSCANDO SERIES PRESENTES EN MÚLTIPLES CATEGORÍAS...")
    shared = find_shared_series(client, selected)

    print(f"\nSeries presentes en 2+ categorías: {len(shared)}")

    if not shared:
        raise RuntimeError(
            "No se encontró ninguna serie compartida entre las categorías seleccionadas."
        )

    # Choose the best candidate found by the scoring above.
    series_key, occurrences = shared[0]
    base = occurrences[0]
    other = occurrences[1]

    print("\n" + "-" * 72)
    print("PAR DE VERSIONES SELECCIONADO")
    print("-" * 72)
    print(f"Serie: {base['item'].get('name')}")
    print(
        f"A: {base['category_name']} | "
        f"category_id={base['category_id']} | "
        f"series_id={base['item'].get('series_id')}"
    )
    print(
        f"B: {other['category_name']} | "
        f"category_id={other['category_id']} | "
        f"series_id={other['item'].get('series_id')}"
    )

    profile_a = infer_category_profile(base["category_name"])
    profile_b = infer_category_profile(other["category_name"])

    print(
        f"A señales: quality={profile_a.quality}, "
        f"resolution={profile_a.resolution}, "
        f"dynamic_range={profile_a.dynamic_range}, "
        f"audio={profile_a.audio}, language={profile_a.language_hint}"
    )
    print(
        f"B señales: quality={profile_b.quality}, "
        f"resolution={profile_b.resolution}, "
        f"dynamic_range={profile_b.dynamic_range}, "
        f"audio={profile_b.audio}, language={profile_b.language_hint}"
    )

    detail_a = client.series_info(str(base["item"]["series_id"]))
    detail_b = client.series_info(str(other["item"]["series_id"]))

    map_a = episode_map(detail_a)
    map_b = episode_map(detail_b)

    print(f"\nEpisodios A: {len(map_a)}")
    print(f"Episodios B: {len(map_b)}")

    common = sorted(set(map_a) & set(map_b))
    only_a = sorted(set(map_a) - set(map_b))
    only_b = sorted(set(map_b) - set(map_a))

    print(f"Episodios presentes en ambas versiones: {len(common)}")
    print(f"Solo en A: {len(only_a)}")
    print(f"Solo en B: {len(only_b)}")

    print("\nMATRIZ EPISODIO → VERSIONES")
    print("-" * 72)

    for season, number in common[:20]:
        a = map_a[(season, number)]
        b = map_b[(season, number)]
        print(
            f"S{season}E{number}: "
            f"A[id={a.get('id')}, ext={a.get('container_extension')}] | "
            f"B[id={b.get('id')}, ext={b.get('container_extension')}]"
        )

    if only_a:
        print("\nEJEMPLOS SOLO EN A:")
        for season, number in only_a[:10]:
            ep = map_a[(season, number)]
            print(f"  S{season}E{number} | id={ep.get('id')}")

    if only_b:
        print("\nEJEMPLOS SOLO EN B:")
        for season, number in only_b[:10]:
            ep = map_b[(season, number)]
            print(f"  S{season}E{number} | id={ep.get('id')}")

    print("\n" + "=" * 72)
    print("PRUEBA 5.1 COMPLETADA")
    print("Se ha comparado una serie compartida entre categorías.")
    print("No se ha sincronizado el catálogo completo.")
    print("No se ha modificado ninguna playlist.")
    print("=" * 72)


if __name__ == "__main__":
    main()
