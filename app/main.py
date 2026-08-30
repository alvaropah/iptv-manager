from __future__ import annotations
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import init_db, connect
from app.db.metadata import init_metadata_db
from app.db.repository import get_categories,get_content,get_episode,get_series_seasons,get_stats,list_catalog,search_catalog

APP_VERSION="0.7.0"
app=FastAPI(title="IPTV Manager API",version=APP_VERSION,description="Biblioteca IPTV con catálogo unificado y metadatos TMDB persistentes.")
WEB_DIR=__import__("pathlib").Path(__file__).resolve().parent/"web"
if WEB_DIR.exists(): app.mount("/ui",StaticFiles(directory=str(WEB_DIR),html=True),name="ui")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["GET"],allow_headers=["*"])
@app.on_event("startup")
def startup():
    init_db()
    with connect() as conn: init_metadata_db(conn); conn.commit()
@app.get("/")
def root(): return {"name":"IPTV Manager","version":APP_VERSION,"status":"ok","metadata":"tmdb-integrated"}
@app.get("/api/health")
def health(): return {"status":"healthy","version":APP_VERSION,"metadata":"tmdb-integrated"}
@app.get("/api/stats")
def stats(): return get_stats()
@app.get("/api/categories")
def categories(content_type:str|None=Query(None,pattern="^(movie|series|live)$"),selected_only:bool=True): return get_categories(content_type,selected_only)
@app.get("/api/catalog/{content_type}")
def catalog(content_type:str,page:int=Query(1,ge=1),page_size:int=Query(40,ge=1,le=100),category_id:int|None=Query(None,ge=1),q:str|None=Query(None,min_length=2)):
    if content_type not in {"movie","series"}: raise HTTPException(400,"Tipo de contenido no válido")
    return list_catalog(content_type,page,page_size,category_id,q)
@app.get("/api/search")
def search(q:str=Query(min_length=2),content_type:str|None=Query(None,pattern="^(movie|series)$"),page:int=Query(1,ge=1),page_size:int=Query(40,ge=1,le=100),limit:int|None=Query(None,ge=1,le=200)):
    if limit is not None and page==1:return {"query":q,"results":search_catalog(q,limit,content_type)}
    return search_catalog(q,50,content_type,page,page_size)
@app.get("/api/movies/{content_id}")
def movie_detail(content_id:int):
    result=get_content(content_id,"movie")
    if result is None: raise HTTPException(404,"Película no encontrada")
    return result
@app.get("/api/series/{content_id}")
def series_detail(content_id:int):
    result=get_content(content_id,"series")
    if result is None: raise HTTPException(404,"Serie no encontrada")
    result["seasons"]=get_series_seasons(content_id); return result
@app.get("/api/series/{content_id}/seasons")
def series_seasons(content_id:int):
    if get_content(content_id,"series") is None: raise HTTPException(404,"Serie no encontrada")
    return get_series_seasons(content_id)
@app.get("/api/episodes/{episode_id}")
def episode_detail(episode_id:int):
    result=get_episode(episode_id)
    if result is None: raise HTTPException(404,"Episodio no encontrado")
    return result
