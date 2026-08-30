from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.db.repository import (
    get_categories,
    get_content,
    get_episode,
    get_series_seasons,
    get_stats,
    search_catalog,
)
from app.core.config import settings


APP_VERSION = "0.4.1"

app = FastAPI(
    title="IPTV Manager API",
    version=APP_VERSION,
    description="API de catálogo para IPTV Manager. Lee la BD local y no consulta Xtream para servir el catálogo.",
)

# Preparado para el futuro frontend. En desarrollo permitimos localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {"name": "IPTV Manager", "version": APP_VERSION, "status": "ok"}


@app.get("/api/health")
def health() -> dict:
    return {"status": "healthy", "version": APP_VERSION}


@app.get("/api/stats")
def stats() -> dict:
    return get_stats()


@app.get("/api/categories")
def categories(
    content_type: str | None = Query(default=None, pattern="^(movie|series|live)$"),
    selected_only: bool = True,
) -> list[dict]:
    return get_categories(content_type=content_type, selected_only=selected_only)


@app.get("/api/search")
def search(
    q: str = Query(min_length=2),
    content_type: str | None = Query(default=None, pattern="^(movie|series)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return {"query": q, "results": search_catalog(q, limit, content_type)}


@app.get("/api/movies/{content_id}")
def movie_detail(content_id: int) -> dict:
    result = get_content(content_id, "movie")
    if result is None:
        raise HTTPException(status_code=404, detail="Película no encontrada")
    return result


@app.get("/api/series/{content_id}")
def series_detail(content_id: int) -> dict:
    result = get_content(content_id, "series")
    if result is None:
        raise HTTPException(status_code=404, detail="Serie no encontrada")
    result["seasons"] = get_series_seasons(content_id)
    return result


@app.get("/api/series/{content_id}/seasons")
def series_seasons(content_id: int) -> list[dict]:
    result = get_content(content_id, "series")
    if result is None:
        raise HTTPException(status_code=404, detail="Serie no encontrada")
    return get_series_seasons(content_id)


@app.get("/api/episodes/{episode_id}")
def episode_detail(episode_id: int) -> dict:
    result = get_episode(episode_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    return result
