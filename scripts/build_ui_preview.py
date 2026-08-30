from __future__ import annotations
import json, os, shutil, sqlite3
from pathlib import Path
DB=Path(os.environ.get('DATABASE_PATH','data/iptv_manager.db')); OUT=Path('preview/data'); PAGE=100; CHUNK=50

def write(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

def cats(conn,cid):
    return [dict(r) for r in conn.execute('''SELECT c.id,c.name,c.content_type,c.quality,c.resolution,c.dynamic_range,c.audio,c.subtitles,c.language_hint FROM content_categories cc JOIN categories c ON c.id=cc.category_id WHERE cc.content_id=? ORDER BY c.name''',(cid,)).fetchall()]

def versions(conn,content_id=None,episode_id=None):
    where=['v.is_active=1']; p=[]
    if content_id is not None: where.append('v.content_id=?'); p.append(content_id)
    if episode_id is not None: where.append('v.episode_id=?'); p.append(episode_id)
    rows=conn.execute(f'''SELECT v.id,v.category_id,c.name category_name,v.languages language,v.quality,v.resolution,v.video_codec,v.audio_codec,v.dynamic_range,v.subtitles,v.label,COUNT(s.id) stream_count FROM versions v JOIN categories c ON c.id=v.category_id LEFT JOIN streams s ON s.version_id=v.id AND s.is_active=1 WHERE {' AND '.join(where)} GROUP BY v.id ORDER BY CASE v.quality WHEN '8K' THEN 1 WHEN '4K' THEN 2 WHEN '1080p' THEN 3 WHEN '720p' THEN 4 ELSE 9 END,v.dynamic_range DESC,v.label''',p).fetchall()
    return [dict(r) for r in rows]

def base(conn,row):
    d=dict(row); d['overview']=d.get('overview') or ''; d['categories']=cats(conn,d['id']); return d

def movie(conn,cid):
    r=conn.execute("SELECT id,content_type,canonical_title title,original_title,year,overview,poster_url,backdrop_url FROM content WHERE id=? AND content_type='movie' AND is_active=1",(cid,)).fetchone()
    if not r:return None
    d=base(conn,r); d['versions']=versions(conn,content_id=cid); return d

def series(conn,cid):
    r=conn.execute("SELECT id,content_type,canonical_title title,original_title,year,overview,poster_url,backdrop_url FROM content WHERE id=? AND content_type='series' AND is_active=1",(cid,)).fetchone()
    if not r:return None
    d=base(conn,r); d['seasons']=[]
    for s in conn.execute('SELECT id,season_number,name,overview,poster_url FROM seasons WHERE series_id=? AND is_active=1 ORDER BY season_number',(cid,)).fetchall():
        sd=dict(s); sd['overview']=sd.get('overview') or ''; sd['episodes']=[]
        for e in conn.execute('SELECT id,episode_number,canonical_title title,overview,air_date,poster_url FROM episodes WHERE season_id=? AND is_active=1 ORDER BY episode_number',(s['id'],)).fetchall():
            ed=dict(e); ed['overview']=ed.get('overview') or ''; ed['versions']=versions(conn,episode_id=e['id']); sd['episodes'].append(ed)
        d['seasons'].append(sd)
    return d

def pages(items,path):
    n=(len(items)+PAGE-1)//PAGE
    for i in range(n): write(path/f'page-{i+1:03d}.json',{'page':i+1,'pages':n,'page_size':PAGE,'total':len(items),'items':items[i*PAGE:(i+1)*PAGE]})
    return n

def chunks(items,path):
    idx={}; n=(len(items)+CHUNK-1)//CHUNK
    for i in range(n):
        part=items[i*CHUNK:(i+1)*CHUNK]; write(path/f'chunk-{i+1:03d}.json',{str(x['id']):x for x in part})
        for x in part: idx[str(x['id'])]=i+1
    write(path/'index.json',{'chunk_size':CHUNK,'items':idx}); return n

def main():
    if not DB.exists(): raise SystemExit(f'No existe {DB}')
    if OUT.exists(): shutil.rmtree(OUT)
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        stats={k:c.execute(q).fetchone()[0] for k,q in {'movies':"SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1",'series':"SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1",'seasons':'SELECT COUNT(*) FROM seasons WHERE is_active=1','episodes':'SELECT COUNT(*) FROM episodes WHERE is_active=1','versions':'SELECT COUNT(*) FROM versions WHERE is_active=1','streams':'SELECT COUNT(*) FROM streams WHERE is_active=1','categories':'SELECT COUNT(*) FROM categories WHERE selected=1'}.items()}
        categories=[dict(r) for r in c.execute('SELECT id,provider_category_id,name,content_type,quality,resolution,dynamic_range,audio,subtitles,language_hint FROM categories WHERE selected=1 ORDER BY content_type,provider_order,name').fetchall()]
        mr=c.execute("SELECT id,content_type,canonical_title name,original_title,year,poster_url,backdrop_url,overview FROM content WHERE content_type='movie' AND is_active=1 ORDER BY normalized_title,year DESC,id").fetchall()
        sr=c.execute("SELECT id,content_type,canonical_title name,original_title,year,poster_url,backdrop_url,overview FROM content WHERE content_type='series' AND is_active=1 ORDER BY normalized_title,year DESC,id").fetchall()
        movies=[base(c,r) for r in mr]; series_list=[base(c,r) for r in sr]
        md=[movie(c,r['id']) for r in mr]; sd=[series(c,r['id']) for r in sr]
    OUT.mkdir(parents=True,exist_ok=True); write(OUT/'stats.json',stats); write(OUT/'categories.json',categories)
    mp=pages(movies,OUT/'movies'); sp=pages(series_list,OUT/'series'); mc=chunks(md,OUT/'details'/'movies'); sc=chunks(sd,OUT/'details'/'series')
    write(OUT/'manifest.json',{'preview':True,'catalog_complete':True,'playback_urls_included':False,'playback_note':'Stream URLs are not published in the public preview.','stats':stats,'movie_pages':mp,'series_pages':sp,'movie_detail_chunks':mc,'series_detail_chunks':sc,'page_size':PAGE,'detail_chunk_size':CHUNK})
    print(json.dumps({'stats':stats,'movie_pages':mp,'series_pages':sp,'movie_detail_chunks':mc,'series_detail_chunks':sc},indent=2))
if __name__=='__main__': main()
