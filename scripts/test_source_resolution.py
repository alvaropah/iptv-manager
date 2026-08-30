from __future__ import annotations

from collections import defaultdict

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


def classify_entry(category_name, item):
    profile = infer_category_profile(category_name)
    signals = {
        "quality": profile.quality,
        "resolution": profile.resolution,
        "dynamic_range": profile.dynamic_range,
        "audio": profile.audio,
        "subtitles": profile.subtitles,
        "language": profile.language_hint,
    }
    return {
        "category": category_name,
        "source_id": str(item.get("series_id", item.get("stream_id", ""))),
        "name": str(item.get("name", "")),
        "year": analyze_title(item.get("name", "")).year,
        "signals": signals,
    }


def quality_key(entry):
    s = entry["signals"]
    return (
        s.get("quality") or "",
        s.get("resolution") or "",
        s.get("dynamic_range") or "",
        s.get("audio") or "",
        str(s.get("language") or ""),
    )


def audit(client, categories, fetcher, limit_examples=12):
    groups = defaultdict(list)

    for pos, (category_name, category) in enumerate(categories, 1):
        items = fetcher(category["id"]) or []
        print(f"  [{pos}/{len(categories)}] {category_name}: {len(items)} entradas")
        for item in items:
            analysis = analyze_title(item.get("name", ""))
            if analysis.canonical:
                groups[analysis.canonical].append(
                    classify_entry(category_name, item)
                )

    multi = {k: v for k, v in groups.items() if len(v) > 1}

    same_category = {}
    cross_category = {}
    technical_variants = {}
    duplicate_streams = {}

    for key, entries in multi.items():
        cats = {e["category"] for e in entries}
        qkeys = {quality_key(e) for e in entries}

        if len(cats) == 1:
            same_category[key] = entries
        else:
            cross_category[key] = entries

        if len(qkeys) > 1:
            technical_variants[key] = entries

        if len(cats) == 1 and len(qkeys) == 1:
            duplicate_streams[key] = entries

    return groups, multi, same_category, cross_category, technical_variants, duplicate_streams


def show(title, mapping, limit=12):
    print(f"\n{title}: {len(mapping)}")
    for key, entries in list(sorted(mapping.items()))[:limit]:
        print(f"\n  CONTENIDO: {key}")
        for e in entries:
            active = [f"{k}={v}" for k, v in e["signals"].items() if v is not None]
            print(
                f"    - source_id={e['source_id']} | "
                f"category={e['category']} | "
                f"{', '.join(active) if active else 'sin señales'}"
            )


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.5: RESOLUCIÓN DE FUENTES Y VERSIONES")
    print("=" * 72)
    print("\nObjetivo: separar identidad, fuente y stream.")
    print("Se clasifican duplicados como:")
    print("  1) versiones técnicas distintas;")
    print("  2) fuentes/categorías distintas;")
    print("  3) posibles streams duplicados.")
    print("No se fusiona ni se modifica ninguna playlist.")

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

    for label, cats, fetcher in (
        ("SERIES", sc, client.series_streams),
        ("VOD", vc, client.vod_streams),
    ):
        print("\n" + "=" * 72)
        print(label)
        print("=" * 72)

        groups, multi, same_cat, cross_cat, tech, dup = audit(
            client, cats, fetcher
        )

        print("\nRESUMEN")
        print(f"  Identidades únicas:                 {len(groups)}")
        print(f"  Con 2+ entradas:                    {len(multi)}")
        print(f"  Variantes entre categorías:         {len(cross_cat)}")
        print(f"  Variantes técnicas detectadas:     {len(tech)}")
        print(f"  Posibles streams duplicados:       {len(dup)}")
        print(f"  Múltiples entradas misma categoría:{len(same_cat)}")

        show("EJEMPLOS — VERSIONES TÉCNICAS", tech)
        show("EJEMPLOS — FUENTES/CATEGORÍAS", cross_cat)
        show("EJEMPLOS — POSIBLES STREAMS DUPLICADOS", dup)

    print("\n" + "=" * 72)
    print("PRUEBA 5.5 COMPLETADA")
    print("Identidad, fuente y stream han sido tratados como niveles distintos.")
    print("No se ha fusionado ningún contenido ni modificado ninguna playlist.")
    print("=" * 72)


if __name__ == "__main__":
    main()
