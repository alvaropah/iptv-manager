from __future__ import annotations
import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

DB = Path(os.environ.get("DATABASE_PATH", "data/ui_test.db"))
DB.parent.mkdir(parents=True, exist_ok=True)
if DB.exists(): DB.unlink()

schema = Path(__file__).resolve().parents[1] / "app" / "db" / "database.py"
# Importing init_db creates the same schema used by the application.
os.environ["DATABASE_PATH"] = str(DB)
from app.db.database import init_db
init_db()
from app.main import app

with sqlite3.connect(DB) as conn:
    conn.execute("INSERT INTO providers(name,host) VALUES('Test','test.local')")
    pid=conn.execute("SELECT id FROM providers").fetchone()[0]
    conn.execute("INSERT INTO categories(provider_id,provider_category_id,name,content_type,selected) VALUES(?,?,?,?,1)", (pid,'1','TEST','movie'))
    cat=conn.execute("SELECT id FROM categories").fetchone()[0]
    conn.execute("INSERT INTO content(provider_id,content_type,canonical_title,normalized_title,original_title,year) VALUES(?,?,?,?,?,?)", (pid,'movie','Test Movie','test movie','Test Movie',2026))
    cid=conn.execute("SELECT id FROM content").fetchone()[0]
    conn.execute("INSERT INTO content_categories(content_id,category_id) VALUES(?,?)", (cid,cat))
    conn.execute("INSERT INTO versions(content_id,category_id,quality,resolution,label,source_key) VALUES(?,?,?,?,?,?)", (cid,cat,'4K','2160p','4K / 2160p','4K|2160p'))
    vid=conn.execute("SELECT id FROM versions").fetchone()[0]
    conn.execute("INSERT INTO streams(version_id,provider_id,provider_stream_id,stream_url,container_extension) VALUES(?,?,?,?,?)", (vid,pid,'123','http://example.invalid/123.mkv','mkv'))
    conn.commit()

with TestClient(app) as client:
    for path in ('/ui/','/ui/style.css','/ui/app.js'):
        r=client.get(path)
        if r.status_code != 200:
            raise RuntimeError(f'{path}: HTTP {r.status_code}')
        print(f'OK | {path}')
    r=client.get('/api/stats')
    if r.status_code != 200: raise RuntimeError(f'/api/stats: {r.status_code}')
    print('OK | UI comparte API con el catálogo')

print('='*72)
print('v0.4.2 COMPLETADA')
print('Primera interfaz web y rutas UI validadas; no consulta Xtream.')
print('='*72)
