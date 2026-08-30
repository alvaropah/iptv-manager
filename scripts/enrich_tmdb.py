from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Permite ejecutar `python scripts/enrich_tmdb.py` desde la raíz del repo.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.tmdb import TMDBClient
from app.db.database import connect
from app.services.metadata import classify_match, extract_year, score_candidate


def save_movie(conn, content_id, provider_title, result, score, status):
    tmdb_id = str(result['id'])
    credits = result.get('credits') or {}
    crew = credits.get('crew') or []
    directors = [p['name'] for p in crew if p.get('job') == 'Director']
    cast = [{k: p.get(k) for k in ('id','name','character','profile_path')} for p in (credits.get('cast') or [])[:20]]
    genres = [g.get('name') for g in result.get('genres') or []]
    poster = f"https://image.tmdb.org/t/p/w500{result['poster_path']}" if result.get('poster_path') else None
    backdrop = f"https://image.tmdb.org/t/p/w1280{result['backdrop_path']}" if result.get('backdrop_path') else None
    conn.execute("""INSERT INTO metadata_links(content_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
      VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(external_source,external_id) DO UPDATE SET content_id=excluded.content_id,provider_title=excluded.provider_title,match_status=excluded.match_status,match_score=excluded.match_score,matched_by=excluded.matched_by,updated_at=CURRENT_TIMESTAMP""", (content_id,provider_title,'tmdb',tmdb_id,status,score,'title+year'))
    if status == 'matched':
        conn.execute("""INSERT INTO content_metadata(content_id,source,external_id,title,original_title,overview,year,runtime,genres_json,director,cast_json,poster_url,backdrop_url,rating,raw_json,language,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(content_id) DO UPDATE SET source=excluded.source,external_id=excluded.external_id,title=excluded.title,original_title=excluded.original_title,overview=excluded.overview,year=excluded.year,runtime=excluded.runtime,genres_json=excluded.genres_json,director=excluded.director,cast_json=excluded.cast_json,poster_url=excluded.poster_url,backdrop_url=excluded.backdrop_url,rating=excluded.rating,raw_json=excluded.raw_json,language=excluded.language,updated_at=CURRENT_TIMESTAMP""", (content_id,'tmdb',tmdb_id,result.get('title'),result.get('original_title'),result.get('overview'),int((result.get('release_date') or '0000')[:4]) if (result.get('release_date') or '')[:4].isdigit() else None,result.get('runtime'),json.dumps(genres,ensure_ascii=False),', '.join(directors),json.dumps(cast,ensure_ascii=False),poster,backdrop,result.get('vote_average'),json.dumps(result,ensure_ascii=False),settings.tmdb_language))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--limit',type=int,default=100); p.add_argument('--type',choices=['movie','series'],default=None); args=p.parse_args()
    token=settings.tmdb_api_token or os.getenv('TMDB_API_TOKEN','')
    if not token: raise SystemExit('TMDB_API_TOKEN no está configurado. Añádelo como secret/env; nunca lo guardes en el repo.')
    client=TMDBClient(token,settings.tmdb_language)
    with connect() as conn:
        clauses=['c.is_active=1']; params=[]
        if args.type: clauses.append('c.content_type=?'); params.append(args.type)
        rows=conn.execute(f"SELECT c.id,c.content_type,c.canonical_title,c.year FROM content c WHERE {' AND '.join(clauses)} ORDER BY c.id LIMIT ?", [*params,args.limit]).fetchall()
        done=0; review=0; errors=0
        for r in rows:
            try:
                year=extract_year(r['canonical_title'],r['year'])
                candidates=client.search_movie(r['canonical_title'],year) if r['content_type']=='movie' else client.search_tv(r['canonical_title'],year)
                if not candidates:
                    continue
                ranked=sorted(((score_candidate(r['canonical_title'],year,c),c) for c in candidates),key=lambda x:x[0],reverse=True)
                score,c=ranked[0]; status=classify_match(score)
                if r['content_type']=='movie':
                    detail=client.movie(c['id']); save_movie(conn,r['id'],r['canonical_title'],detail,score,status)
                else:
                    tmdb_id=str(c['id']); poster=f"https://image.tmdb.org/t/p/w500{c['poster_path']}" if c.get('poster_path') else None; backdrop=f"https://image.tmdb.org/t/p/w1280{c['backdrop_path']}" if c.get('backdrop_path') else None
                    detail=client.tv(c['id']); credits=detail.get('credits') or {}; creators=[x.get('name') for x in detail.get('created_by') or []]; cast=[{k:p.get(k) for k in ('id','name','character','profile_path')} for p in (credits.get('cast') or [])[:20]]
                    conn.execute("""INSERT INTO metadata_links(content_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(external_source,external_id) DO UPDATE SET content_id=excluded.content_id,provider_title=excluded.provider_title,match_status=excluded.match_status,match_score=excluded.match_score,matched_by=excluded.matched_by,updated_at=CURRENT_TIMESTAMP""",(r['id'],r['canonical_title'],'tmdb',tmdb_id,status,score,'title+year'))
                    if status=='matched':
                        conn.execute("""INSERT INTO content_metadata(content_id,source,external_id,title,original_title,overview,year,runtime,genres_json,creators_json,cast_json,poster_url,backdrop_url,rating,raw_json,language,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(content_id) DO UPDATE SET external_id=excluded.external_id,title=excluded.title,original_title=excluded.original_title,overview=excluded.overview,year=excluded.year,runtime=excluded.runtime,genres_json=excluded.genres_json,creators_json=excluded.creators_json,cast_json=excluded.cast_json,poster_url=excluded.poster_url,backdrop_url=excluded.backdrop_url,rating=excluded.rating,raw_json=excluded.raw_json,language=excluded.language,updated_at=CURRENT_TIMESTAMP""",(r['id'],'tmdb',tmdb_id,detail.get('name'),detail.get('original_name'),detail.get('overview'),int((detail.get('first_air_date') or '0000')[:4]) if (detail.get('first_air_date') or '')[:4].isdigit() else None,detail.get('episode_run_time',[None])[0] if detail.get('episode_run_time') else None,json.dumps([g.get('name') for g in detail.get('genres') or []],ensure_ascii=False),json.dumps(creators,ensure_ascii=False),json.dumps(cast,ensure_ascii=False),poster,backdrop,detail.get('vote_average'),json.dumps(detail,ensure_ascii=False),settings.tmdb_language))
                done+=1
                review += status=='review'
                if done%25==0: conn.commit(); print(f'procesados={done}/{len(rows)} review={review}')
                time.sleep(0.05)
            except Exception as exc:
                errors+=1; print(f'ERROR content={r["id"]}: {exc}')
        conn.commit(); print(f'OK procesados={done} review={review} errores={errors}')

if __name__=='__main__': main()
