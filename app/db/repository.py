from __future__ import annotations
import json, re, unicodedata
from typing import Any
from app.db.database import connect

def _normalize_search(value: str) -> str:
    value=unicodedata.normalize("NFKD",value or "")
    value="".join(ch for ch in value if unicodedata.category(ch)!="Mn")
    return re.sub(r"\s+"," ",value.casefold()).strip()

def _json(value):
    if not value: return []
    try: return json.loads(value)
    except (TypeError,ValueError): return []

def _page(page,page_size,total): return {"page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size if total else 0}

def get_stats():
    with connect() as conn:
        return {"movies":conn.execute("SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1").fetchone()[0],"series":conn.execute("SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1").fetchone()[0],"seasons":conn.execute("SELECT COUNT(*) FROM seasons WHERE is_active=1").fetchone()[0],"episodes":conn.execute("SELECT COUNT(*) FROM episodes WHERE is_active=1").fetchone()[0],"versions":conn.execute("SELECT COUNT(*) FROM versions WHERE is_active=1").fetchone()[0],"streams":conn.execute("SELECT COUNT(*) FROM streams WHERE is_active=1").fetchone()[0],"categories":conn.execute("SELECT COUNT(*) FROM categories WHERE selected=1").fetchone()[0]}

def get_categories(content_type=None,selected_only=True):
    clauses=[]; params=[]
    if content_type: clauses.append("content_type=?"); params.append(content_type)
    if selected_only: clauses.append("selected=1")
    where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
    with connect() as conn: rows=conn.execute(f"SELECT id,provider_category_id,name,content_type,selected,quality,resolution,dynamic_range,audio,subtitles,language_hint FROM categories{where} ORDER BY content_type,provider_order,name",params).fetchall()
    return [dict(r) for r in rows]

def _metadata(conn,content_id):
    r=conn.execute("SELECT source,external_id,title,original_title,overview,year,runtime,genres_json,director,creators_json,cast_json,poster_url,backdrop_url,rating,language,updated_at FROM content_metadata WHERE content_id=?",(content_id,)).fetchone()
    if not r:return None
    d=dict(r); d["genres"]=_json(d.pop("genres_json")); d["creators"]=_json(d.pop("creators_json")); d["cast"]=_json(d.pop("cast_json")); return d

def _metadata_link(conn,content_id):
    r=conn.execute("SELECT external_source,external_id,match_status,match_score,matched_by,provider_title,updated_at FROM metadata_links WHERE content_id=? AND external_source='tmdb' ORDER BY updated_at DESC LIMIT 1",(content_id,)).fetchone()
    return dict(r) if r else None

def _catalog_select():
    return "c.id,c.content_type,COALESCE(m.title,c.canonical_title) AS name,c.canonical_title AS provider_title,COALESCE(m.original_title,c.original_title) AS original_title,COALESCE(m.year,c.year) AS year,COALESCE(m.poster_url,c.poster_url) AS poster_url,COALESCE(m.backdrop_url,c.backdrop_url) AS backdrop_url,m.overview,m.rating"

def list_catalog(content_type,page=1,page_size=40,category_id=None,q=None):
    clauses=["c.content_type=?","c.is_active=1"]; params=[content_type]
    if category_id is not None: clauses.append("EXISTS (SELECT 1 FROM content_categories cc WHERE cc.content_id=c.id AND cc.category_id=?)"); params.append(category_id)
    if q: clauses.append("c.normalized_title LIKE ?"); params.append(f"%{_normalize_search(q)}%")
    where=" AND ".join(clauses); offset=(page-1)*page_size
    with connect() as conn:
        total=conn.execute(f"SELECT COUNT(*) FROM content c WHERE {where}",params).fetchone()[0]
        rows=conn.execute(f"SELECT {_catalog_select()} FROM content c LEFT JOIN content_metadata m ON m.content_id=c.id WHERE {where} ORDER BY c.normalized_title,year DESC,c.id LIMIT ? OFFSET ?",[*params,page_size,offset]).fetchall()
    return {"items":[dict(r) for r in rows],**_page(page,page_size,total)}

def get_recent_catalog(content_type=None,limit=20):
    """Return recently discovered active content, preserving provider discovery order."""
    clauses=["c.is_active=1"]; params=[]
    if content_type: clauses.append("c.content_type=?"); params.append(content_type)
    where=" AND ".join(clauses)
    with connect() as conn:
        rows=conn.execute(f"SELECT {_catalog_select()},c.first_seen_at,c.last_seen_at FROM content c LEFT JOIN content_metadata m ON m.content_id=c.id WHERE {where} ORDER BY CASE WHEN c.first_seen_at IS NULL THEN 1 ELSE 0 END,c.first_seen_at DESC,c.id DESC LIMIT ?",[*params,limit]).fetchall()
    return [dict(r) for r in rows]

def search_catalog(query,limit=50,content_type=None,page=1,page_size=None):
    q=f"%{_normalize_search(query)}%"; clauses=["c.is_active=1","c.normalized_title LIKE ?"]; params=[q]
    if content_type: clauses.append("c.content_type=?"); params.append(content_type)
    where=" AND ".join(clauses)
    with connect() as conn:
        if page_size is None:
            rows=conn.execute(f"SELECT {_catalog_select()} FROM content c LEFT JOIN content_metadata m ON m.content_id=c.id WHERE {where} ORDER BY c.normalized_title,year DESC LIMIT ?",[*params,limit]).fetchall(); return [dict(r) for r in rows]
        total=conn.execute(f"SELECT COUNT(*) FROM content c WHERE {where}",params).fetchone()[0]; offset=(page-1)*page_size
        rows=conn.execute(f"SELECT {_catalog_select()} FROM content c LEFT JOIN content_metadata m ON m.content_id=c.id WHERE {where} ORDER BY c.normalized_title,year DESC,c.id LIMIT ? OFFSET ?",[*params,page_size,offset]).fetchall()
    return {"items":[dict(r) for r in rows],**_page(page,page_size,total),"query":query}

def _version_rows(conn,content_id=None,episode_id=None):
    clauses=["v.is_active=1"]; params=[]
    if content_id is not None: clauses.append("v.content_id=?"); params.append(content_id)
    if episode_id is not None: clauses.append("v.episode_id=?"); params.append(episode_id)
    rows=conn.execute(f"SELECT v.id,v.category_id,c.name AS category_name,v.languages AS language,v.quality,v.resolution,v.video_codec,v.audio_codec,v.dynamic_range,v.languages,v.subtitles,v.label,s.id AS stream_db_id,s.provider_stream_id AS source_id,s.stream_url AS playback_url,s.container_extension AS container,s.original_name FROM versions v JOIN categories c ON c.id=v.category_id LEFT JOIN streams s ON s.version_id=v.id AND s.is_active=1 WHERE {' AND '.join(clauses)} ORDER BY CASE v.quality WHEN '8K' THEN 1 WHEN '4K' THEN 2 WHEN '1080p' THEN 3 WHEN '720p' THEN 4 ELSE 9 END,v.dynamic_range DESC,v.label",params).fetchall()
    grouped={}
    for row in rows:
        d=dict(row); vid=d.pop("id"); item=grouped.get(vid)
        if item is None:
            keys=("category_id","category_name","language","quality","resolution","video_codec","audio_codec","dynamic_range","languages","subtitles","label"); item={"id":vid,**{k:d[k] for k in keys},"streams":[]}; grouped[vid]=item
        if d.get("stream_db_id") is not None:item["streams"].append({"id":d["stream_db_id"],"source_id":d["source_id"],"playback_url":d["playback_url"],"container":d["container"],"original_name":d["original_name"]})
    return list(grouped.values())

def get_content(content_id,content_type):
    with connect() as conn:
        r=conn.execute("SELECT id,content_type,canonical_title,original_title,year,overview,poster_url,backdrop_url,first_seen_at,last_seen_at,last_detail_sync_at FROM content WHERE id=? AND content_type=? AND is_active=1",(content_id,content_type)).fetchone()
        if r is None:return None
        result=dict(r); result["provider_title"]=result.pop("canonical_title"); meta=_metadata(conn,content_id); result["metadata"]=meta; result["metadata_link"]=_metadata_link(conn,content_id)
        if meta:
            for k in ("title","original_title","year","overview","poster_url","backdrop_url"): result[k]=meta.get(k) or result.get(k)
        else: result["title"]=result["provider_title"]
        result["categories"]=[dict(x) for x in conn.execute("SELECT c.id,c.name,c.provider_category_id,c.quality,c.resolution,c.dynamic_range,c.audio,c.subtitles,c.language_hint FROM content_categories cc JOIN categories c ON c.id=cc.category_id WHERE cc.content_id=? ORDER BY c.name",(content_id,)).fetchall()]
        result["versions"]=_version_rows(conn,content_id=content_id); return result

def get_series_seasons(series_id):
    with connect() as conn:
        seasons=conn.execute("SELECT id,season_number,name,overview,poster_url FROM seasons WHERE series_id=? AND is_active=1 ORDER BY season_number",(series_id,)).fetchall(); output=[]
        for s in seasons:
            data=dict(s); eps=conn.execute("SELECT e.id,e.episode_number,e.canonical_title AS provider_title,e.overview,e.air_date,e.poster_url,em.title AS metadata_title,em.overview AS metadata_overview,em.still_url,em.runtime,em.language FROM episodes e LEFT JOIN episode_metadata em ON em.episode_id=e.id WHERE e.season_id=? AND e.is_active=1 ORDER BY e.episode_number",(s["id"],)).fetchall(); data["episodes"]=[]
            for e in eps:
                ep=dict(e); ep["title"]=ep.pop("metadata_title") or ep["provider_title"]; ep["overview"]=ep.pop("metadata_overview") or ep["overview"]; ep["versions"]=_version_rows(conn,episode_id=ep["id"]); data["episodes"].append(ep)
            output.append(data)
    return output

def get_episode(episode_id):
    with connect() as conn:
        r=conn.execute("SELECT e.id,e.episode_number,e.canonical_title AS provider_title,e.overview,e.air_date,e.poster_url,s.id AS season_id,s.season_number,s.series_id,c.canonical_title AS series_title,em.title AS metadata_title,em.overview AS metadata_overview,em.still_url,em.runtime,em.language FROM episodes e JOIN seasons s ON s.id=e.season_id JOIN content c ON c.id=s.series_id LEFT JOIN episode_metadata em ON em.episode_id=e.id WHERE e.id=? AND e.is_active=1",(episode_id,)).fetchone()
        if r is None:return None
        result=dict(r); result["title"]=result.pop("metadata_title") or result["provider_title"]; result["overview"]=result.pop("metadata_overview") or result["overview"]; result["versions"]=_version_rows(conn,episode_id=episode_id); return result
