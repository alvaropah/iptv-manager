from fastapi import FastAPI, Query

from app.db.database import init_db
from app.db.repository import get_stats, search_catalog

app = FastAPI(
    title="IPTV Manager",
    version="0.1.0",
    description="Núcleo personal para gestionar un catálogo Xtream.",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root():
    return {
        "name": "IPTV Manager",
        "version": "0.1.0",
        "status": "ok",
        "next_step": "xtream_sync",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/stats")
def stats():
    return get_stats()


@app.get("/api/search")
def search(
    q: str = Query(min_length=2),
    limit: int = Query(default=50, ge=1, le=200),
):
    return {"query": q, "results": search_catalog(q, limit)}
