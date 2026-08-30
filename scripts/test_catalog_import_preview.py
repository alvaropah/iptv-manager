from __future__ import annotations

from collections import Counter, defaultdict

from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile
from app.core.config import settings
from app.core.content_identity import analyze_title
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient


def cmap(items):
    return {
        normalize_category_name(str(x.get("category_name", ""))): {
            "name": str(x.get("category_name", "")),
            "id": str(x.get("category_id", "")),
        }
        for x in (items or [])
    }


def selected(names, provider):
    return [
        (name, provider[normalize_category_name(name)])
        for name in names
        if normalize_category_name(name) in provider
    ]


def profile_key(profile):
    return (
        profile.quality,
        profile.resolution,
        profile.dynamic_range,
        profile.audio,
        profile.subtitles,
        profile.language_hint,
    )


def preview_vod(client, categories):
    contents = {}
    source_count = 0
    category_count = 0

    for pos, (category_name, category) in enumerate(categories, 1):
        items = client.vod_streams(category["id"]) or []
        category_count += 1
        print(f"  [{pos}/{len(categories)}] {category_name}: {len(items)} entradas")

        profile = infer_category_profile(category_name)

        for item in items:
            source_count += 1
            name = str(item.get("name", "")).strip()
            identity = analyze_title(name)
            if not identity.canonical:
                continue

            key = identity.canonical
            content = contents.setdefault(
                key,
                {
                    "title": name,
                    "year": identity.year,
                    "sources": [],
                },
            )
            content["sources"].append(
                {
                    "source_id": str(item.get("stream_id", "")),
                    "category": category_name,
                    "profile": profile_key(profile),
                }
            )

    return contents, source_count, category_count


def preview_series(client, categories):
    contents = {}
    source_count = 0
    category_count = 0
    episode_count = 0

    for pos, (category_name, category) in enumerate(categories, 1):
        items = client.series_streams(category["id"]) or []
        category_count += 1
        print(f"  [{pos}/{len(categories)}] {category_name}: {len(items)} series")

        profile = infer_category_profile(category_name)

        for item in items:
            source_count += 1
            name = str(item.get("name", "")).strip()
            identity = analyze_title(name)
            if not identity.canonical:
                continue

            key = identity.canonical
            content = contents.setdefault(
                key,
                {
                    "title": name,
                    "year": identity.year,
                    "sources": [],
                    "series_ids": set(),
                    "episodes": 0,
                },
            )

            series_id = str(item.get("series_id", ""))
            content["series_ids"].add(series_id)
            content["sources"].append(
                {
                    "source_id": series_id,
                    "category": category_name,
                    "profile": profile_key(profile),
                }
            )

            # Preview episode structure for every discovered series.
            # This is intentionally read-only.
            detail = client.series_info(series_id) or {}
            episodes = detail.get("episodes") or {}
            for season_items in episodes.values():
                if isinstance(season_items, list):
                    content["episodes"] += len(season_items)
                    episode_count += len(season_items)

    return contents, source_count, category_count, episode_count


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.7: PREVIEW DE IMPORTACIÓN DEL CATÁLOGO")
    print("=" * 72)
    print("\nObjetivo: simular la futura importación sin escribir en la BD.")
    print("Se consulta el catálogo real seleccionado.")
    print("NO se crea ni modifica ninguna base de datos persistente.")
    print("NO se modifica ninguna playlist.")

    cfg = load_catalog_selection()
    client = XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )

    print("\nAutenticando...")
    client.authenticate()
    print("  OK")

    ps = cmap(client.series_categories())
    pv = cmap(client.vod_categories())
    sc = selected(cfg.series_categories, ps)
    vc = selected(cfg.movie_categories, pv)

    print(f"\nSeries: {len(sc)}/{len(cfg.series_categories)} categorías")
    print(f"VOD:    {len(vc)}/{len(cfg.movie_categories)} categorías")

    print("\n" + "=" * 72)
    print("PREVIEW SERIES")
    print("=" * 72)
    series, series_sources, series_categories, series_episodes = preview_series(client, sc)

    print("\n" + "=" * 72)
    print("PREVIEW VOD")
    print("=" * 72)
    vod, vod_sources, vod_categories, _ = preview_vod(client, vc)

    def version_count(data):
        total = 0
        for c in data.values():
            total += len({s["profile"] for s in c["sources"]})
        return total

    def multi_source_count(data):
        return sum(1 for c in data.values() if len(c["sources"]) > 1)

    print("\n" + "=" * 72)
    print("RESUMEN DEL IMPORT PREVIEW")
    print("=" * 72)
    print(f"  Categorías SERIES recorridas:       {series_categories}")
    print(f"  Categorías VOD recorridas:          {vod_categories}")
    print(f"  Series / identidades:               {len(series)}")
    print(f"  Películas / identidades:            {len(vod)}")
    print(f"  Entradas SERIES procesadas:         {series_sources}")
    print(f"  Entradas VOD procesadas:            {vod_sources}")
    print(f"  Episodios descubiertos:             {series_episodes}")
    print(f"  Series con 2+ entradas:             {multi_source_count(series)}")
    print(f"  Películas con 2+ entradas:          {multi_source_count(vod)}")
    print(f"  Versiones técnicas SERIES (preview):{version_count(series)}")
    print(f"  Versiones técnicas VOD (preview):   {version_count(vod)}")

    print("\nMUESTRAS DE LO QUE SE IMPORTARÍA")
    for label, data in (("SERIES", series), ("VOD", vod)):
        print(f"\n  {label}")
        for key, content in sorted(data.items())[:5]:
            print(f"    {content['title']} -> {len(content['sources'])} entradas")

    print("\n" + "=" * 72)
    print("PRUEBA 5.7 COMPLETADA")
    print("PREVIEW generado correctamente.")
    print("NO se ha escrito ningún registro persistente.")
    print("NO se ha modificado ninguna playlist.")
    print("=" * 72)


if __name__ == "__main__":
    main()
