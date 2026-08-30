from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    db_path = Path(os.environ.get("DATABASE_PATH", "data/iptv_manager.db"))
    if not db_path.exists():
        raise RuntimeError(f"No existe la BD restaurada: {db_path}")

    token = os.environ.get("TMDB_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TMDB_API_TOKEN no está disponible para validar el enriquecimiento")

    # Primero distinguimos un problema de credenciales de un problema del catálogo.
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/movie/550",
            headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
            params={"language": "es-ES"},
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"TMDB no acepta TMDB_API_TOKEN: {type(exc).__name__}: {exc}. "
            "Debe ser el 'API Read Access Token' de TMDB, no otro tipo de credencial."
        ) from exc

    with sqlite3.connect(db_path) as conn:
        active_content = conn.execute(
            "SELECT COUNT(*) FROM content WHERE is_active=1"
        ).fetchone()[0]
        links = conn.execute(
            "SELECT COUNT(*) FROM metadata_links WHERE external_source='tmdb'"
        ).fetchone()[0]
        matched = conn.execute(
            "SELECT COUNT(*) FROM metadata_links WHERE external_source='tmdb' AND match_status='matched'"
        ).fetchone()[0]
        review = conn.execute(
            "SELECT COUNT(*) FROM metadata_links WHERE external_source='tmdb' AND match_status='review'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM metadata_links WHERE external_source='tmdb' AND match_status='rejected'"
        ).fetchone()[0]
        metadata = conn.execute(
            "SELECT COUNT(*) FROM content_metadata WHERE source='tmdb'"
        ).fetchone()[0]
        spanish = conn.execute(
            "SELECT COUNT(*) FROM content_metadata WHERE source='tmdb' AND language='es-ES'"
        ).fetchone()[0]
        rich = conn.execute(
            """
            SELECT COUNT(*) FROM content_metadata
            WHERE source='tmdb'
              AND overview IS NOT NULL AND trim(overview) <> ''
              AND (poster_url IS NOT NULL OR backdrop_url IS NOT NULL)
            """
        ).fetchone()[0]
        sample = conn.execute(
            """
            SELECT c.canonical_title, cm.title, cm.year, cm.rating,
                   cm.director, cm.creators_json, cm.cast_json
            FROM content_metadata cm
            JOIN content c ON c.id=cm.content_id
            WHERE cm.source='tmdb'
            ORDER BY cm.content_id
            LIMIT 1
            """
        ).fetchone()

    print(f"Contenido activo en BD: {active_content}")
    print(f"TMDB links: {links} | matched: {matched} | review: {review} | rejected: {rejected}")

    if active_content == 0:
        raise RuntimeError(
            "La BD restaurada no contiene ningún contenido activo. "
            "El problema está en la sincronización/restauración del catálogo, no en TMDB."
        )
    if links == 0:
        raise RuntimeError(
            "TMDB está autenticado pero el enriquecimiento no creó metadata_links. "
            "Revisa el log del paso 'Enriquecimiento TMDB opcional' para ver si las búsquedas devuelven 0 candidatos o si hay errores al consultar detalles."
        )
    if matched == 0:
        raise RuntimeError(
            f"TMDB no ha producido ningún match válido (links={links}, review={review}, rejected={rejected})"
        )
    if metadata == 0:
        raise RuntimeError("TMDB ha generado matches pero no ha persistido content_metadata")
    if spanish != metadata:
        raise RuntimeError(f"Idioma TMDB inesperado: español={spanish}, metadata={metadata}")
    if rich == 0:
        raise RuntimeError("No hay ningún registro TMDB con sinopsis e imagen")

    print("content_metadata:", metadata)
    print("metadata en español:", spanish)
    print("registros ricos (sinopsis + imagen):", rich)
    if sample:
        provider_title, tmdb_title, year, rating, director, creators, cast = sample
        cast_count = len(json.loads(cast)) if cast else 0
        creator_count = len(json.loads(creators)) if creators else 0
        print(f"muestra: {provider_title} → {tmdb_title} ({year})")
        print(f"rating={rating} | director={director or 'N/D'} | creadores={creator_count} | reparto={cast_count}")
    print("TMDB enrichment: OK")
    print("v0.6 TMDB VALIDADA")


if __name__ == "__main__":
    main()
