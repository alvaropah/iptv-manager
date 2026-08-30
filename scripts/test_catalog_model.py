from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile
from app.core.config import settings
from app.core.content_identity import display_title, normalize_content_title
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient


@dataclass
class Version:
    category: str
    category_id: str
    source_id: str
    source_name: str
    profile: object


@dataclass
class ContentCandidate:
    content_key: str
    title: str
    versions: list[Version] = field(default_factory=list)


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


def selected_matches(selected, provider):
    return [
        (name, provider[normalize_category_name(name)])
        for name in selected
        if normalize_category_name(name) in provider
    ]


def collect_vod_sample(client, matches):
    # Two adjacent categories are intentional: the current config starts with
    # a normal category followed by its 4K counterpart.
    sample = matches[:2]
    candidates = defaultdict(lambda: ContentCandidate("", ""))
    raw_total = 0

    for configured_name, category in sample:
        items = client.vod_streams(category["provider_category_id"])
        print(f"\nCategoría VOD: {configured_name}")
        print(f"  category_id={category['provider_category_id']}")
        print(f"  Entradas recibidas: {len(items) if isinstance(items, list) else 0}")

        if not isinstance(items, list):
            continue

        profile = infer_category_profile(configured_name)
        for item in items[:20]:
            raw_total += 1
            source_name = str(item.get("name", "")).strip()
            key = normalize_content_title(source_name)
            if not key:
                continue
            candidate = candidates[key]
            if not candidate.content_key:
                candidate.content_key = key
                candidate.title = display_title(source_name)
            candidate.versions.append(
                Version(
                    category=configured_name,
                    category_id=str(category["provider_category_id"]),
                    source_id=str(item.get("stream_id", "")),
                    source_name=source_name,
                    profile=profile,
                )
            )

    return candidates, raw_total


def collect_series_sample(client, matches):
    sample = matches[:2]
    candidates = defaultdict(lambda: ContentCandidate("", ""))
    raw_total = 0
    sample_series_id = None

    for configured_name, category in sample:
        items = client.series_streams(category["provider_category_id"])
        print(f"\nCategoría SERIES: {configured_name}")
        print(f"  category_id={category['provider_category_id']}")
        print(f"  Entradas recibidas: {len(items) if isinstance(items, list) else 0}")

        if not isinstance(items, list):
            continue

        profile = infer_category_profile(configured_name)
        for item in items[:20]:
            raw_total += 1
            source_name = str(item.get("name", "")).strip()
            key = normalize_content_title(source_name)
            if not key:
                continue
            candidate = candidates[key]
            if not candidate.content_key:
                candidate.content_key = key
                candidate.title = display_title(source_name)
            candidate.versions.append(
                Version(
                    category=configured_name,
                    category_id=str(category["provider_category_id"]),
                    source_id=str(item.get("series_id", "")),
                    source_name=source_name,
                    profile=profile,
                )
            )
            if sample_series_id is None and item.get("series_id"):
                sample_series_id = str(item["series_id"])

    return candidates, raw_total, sample_series_id


def print_candidate_section(title, candidates, raw_total, limit=5):
    duplicates = [c for c in candidates.values() if len(c.versions) > 1]
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)
    print(f"Entradas de muestra: {raw_total}")
    print(f"Contenido candidato único: {len(candidates)}")
    print(f"Candidatos con >1 versión/categoría: {len(duplicates)}")

    shown = 0
    for candidate in sorted(
        candidates.values(),
        key=lambda x: x.title.casefold()
    ):
        if shown >= limit:
            break
        print(f"\n  CONTENIDO: {candidate.title}")
        print(f"  content_key: {candidate.content_key}")
        print(f"  Versiones encontradas: {len(candidate.versions)}")
        for version in candidate.versions:
            p = version.profile
            signals = []
            for label, value in (
                ("quality", p.quality),
                ("resolution", p.resolution),
                ("dynamic_range", p.dynamic_range),
                ("audio", p.audio),
                ("subtitles", p.subtitles),
                ("language_hint", p.language_hint),
            ):
                if value is not None:
                    signals.append(f"{label}={value}")
            print(
                f"    - source_id={version.source_id} | "
                f"category={version.category} | "
                f"signals={', '.join(signals) if signals else 'none'}"
            )
        shown += 1


def print_series_detail(client, series_id):
    print("\n" + "-" * 72)
    print("DETALLE DE UNA SERIE — TEMPORADAS / EPISODIOS")
    print("-" * 72)
    print(f"series_id: {series_id}")
    detail = client.series_info(series_id)
    if not isinstance(detail, dict):
        print(f"Respuesta inesperada: {type(detail).__name__}")
        return

    seasons = detail.get("seasons") or []
    episodes = detail.get("episodes") or {}
    info = detail.get("info") or {}

    print(f"Nombre: {info.get('name', '?')}")
    print(f"Temporadas declaradas: {len(seasons)}")
    print(f"Bloques de episodios: {len(episodes) if isinstance(episodes, dict) else 0}")

    shown = 0
    if isinstance(episodes, dict):
        for season_no, eps in episodes.items():
            if not isinstance(eps, list):
                continue
            print(f"  Temporada {season_no}: {len(eps)} episodios")
            if eps:
                ep = eps[0]
                print(
                    f"    Episodio ejemplo: id={ep.get('id')} | "
                    f"S{season_no}E{ep.get('episode_num')} | "
                    f"title={ep.get('title')} | "
                    f"container={ep.get('container_extension')}"
                )
                shown += 1
            if shown >= 2:
                break


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5: MODELO DE CONTENIDO Y VERSIONES")
    print("=" * 72)
    print("\nObjetivo: comprobar que el mismo contenido puede agrupar")
    print("varias entradas/categorías como versiones, sin modificar la playlist.")
    print("Se consulta solo una muestra de las categorías seleccionadas.")

    cfg = load_catalog_selection()
    client = XtreamClient(
        settings.xtream_host,
        settings.xtream_username,
        settings.xtream_password,
    )

    print("\nAutenticando...")
    client.authenticate()
    print("  OK")

    provider_vod = category_map(client.vod_categories())
    provider_series = category_map(client.series_categories())

    vod_matches = selected_matches(cfg.movie_categories, provider_vod)
    series_matches = selected_matches(cfg.series_categories, provider_series)

    print(f"\nCategorías VOD seleccionadas/encontradas: {len(vod_matches)}/{len(cfg.movie_categories)}")
    print(f"Categorías SERIES seleccionadas/encontradas: {len(series_matches)}/{len(cfg.series_categories)}")

    if len(vod_matches) < 2 or len(series_matches) < 2:
        raise RuntimeError("No hay al menos dos categorías seleccionadas para probar versiones.")

    series_candidates, series_raw, series_id = collect_series_sample(client, series_matches)
    vod_candidates, vod_raw = collect_vod_sample(client, vod_matches)

    print_candidate_section("MUESTRA PELÍCULAS / VOD", vod_candidates, vod_raw)
    print_candidate_section("MUESTRA SERIES", series_candidates, series_raw)

    if series_id:
        print_series_detail(client, series_id)

    print("\n" + "=" * 72)
    print("PRUEBA 5 COMPLETADA")
    print("No se ha generado ni modificado ninguna playlist.")
    print("No se ha sincronizado el catálogo completo.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
