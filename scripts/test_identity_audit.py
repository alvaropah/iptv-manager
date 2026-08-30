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


def audit(client, categories, fetcher, id_key):
    occurrences = defaultdict(list)
    total_entries = 0

    for pos, (category_name, category) in enumerate(categories, 1):
        items = fetcher(category["id"]) or []
        total_entries += len(items)
        profile = infer_category_profile(category_name)

        print(f"  [{pos}/{len(categories)}] {category_name}: {len(items)} entradas")

        for item in items:
            name = str(item.get("name", "")).strip()
            analysis = analyze_title(name)
            if not analysis.canonical:
                continue

            occurrences[analysis.canonical].append({
                "name": name,
                "source_id": str(item.get(id_key, "")),
                "category": category_name,
                "year": analysis.year,
                "profile": profile,
            })

    multi = {k: v for k, v in occurrences.items() if len(v) > 1}

    # Potentially suspicious cases:
    # same canonical identity but explicitly different years.
    year_conflicts = {}
    for key, entries in multi.items():
        years = {e["year"] for e in entries if e["year"] is not None}
        if len(years) > 1:
            year_conflicts[key] = entries

    # Cases where entries share identity but categories provide no technical
    # distinction. These are not errors; they are worth auditing because the
    # duplicate may represent a regional/provider duplicate.
    indistinguishable = {}
    for key, entries in multi.items():
        profiles = {
            (
                e["profile"].quality,
                e["profile"].resolution,
                e["profile"].dynamic_range,
                e["profile"].audio,
                e["profile"].subtitles,
                e["profile"].language_hint,
            )
            for e in entries
        }
        if len(profiles) == 1:
            indistinguishable[key] = entries

    return {
        "total_entries": total_entries,
        "unique_identities": len(occurrences),
        "multi_category": multi,
        "year_conflicts": year_conflicts,
        "indistinguishable": indistinguishable,
    }


def print_examples(title, mapping, limit=15):
    print(f"\n{title}: {len(mapping)}")
    for key, entries in list(sorted(mapping.items()))[:limit]:
        print(f"  CANDIDATO: {key}")
        for e in entries:
            p = e["profile"]
            signals = []
            for n, v in (
                ("quality", p.quality),
                ("resolution", p.resolution),
                ("dynamic_range", p.dynamic_range),
                ("audio", p.audio),
                ("subtitles", p.subtitles),
                ("language", p.language_hint),
            ):
                if v is not None:
                    signals.append(f"{n}={v}")
            print(
                f"    - {e['category']} | source_id={e['source_id']} | "
                f"year={e['year']} | {', '.join(signals) if signals else 'sin señales'}"
            )


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.4: AUDITORÍA COMPLETA DE IDENTIDAD")
    print("=" * 72)
    print("\nRecorre TODAS las categorías seleccionadas.")
    print("Solo analiza identidad; no fusiona, no escribe catálogo y no modifica playlists.")

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

    for label, cats, fetcher, id_key in (
        ("SERIES", sc, client.series_streams, "series_id"),
        ("VOD", vc, client.vod_streams, "stream_id"),
    ):
        print("\n" + "=" * 72)
        print(label)
        print("=" * 72)

        result = audit(client, cats, fetcher, id_key)
        multi = result["multi_category"]
        conflicts = result["year_conflicts"]
        indist = result["indistinguishable"]

        print("\nRESUMEN")
        print(f"  Entradas totales:                 {result['total_entries']}")
        print(f"  Identidades únicas:               {result['unique_identities']}")
        print(f"  Presentes en 2+ categorías:       {len(multi)}")
        print(f"  Conflictos explícitos de año:     {len(conflicts)}")
        print(f"  Sin diferencia técnica visible:   {len(indist)}")

        print_examples("CASOS CONFLICTIVOS POR AÑO", conflicts)
        print_examples("CASOS SIN DIFERENCIA TÉCNICA VISIBLE", indist)

    print("\n" + "=" * 72)
    print("PRUEBA 5.4 COMPLETADA")
    print("Auditoría completa realizada sobre las categorías seleccionadas.")
    print("Los casos dudosos se muestran para revisión; no se fusiona ningún contenido.")
    print("=" * 72)


if __name__ == "__main__":
    main()
