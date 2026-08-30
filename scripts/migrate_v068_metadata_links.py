from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings


def main() -> None:
    db = Path(settings.database_path)
    with sqlite3.connect(db, timeout=120) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("PRAGMA busy_timeout=120000")
        cols = con.execute("PRAGMA table_info(metadata_links)").fetchall()
        if not cols:
            print("metadata_links no existe; init_db lo creará con el esquema nuevo")
            return
        indexes = con.execute("PRAGMA index_list(metadata_links)").fetchall()
        unique_external = False
        for idx in indexes:
            # PRAGMA index_info: seqno, cid, name
            if idx[2]:
                info = con.execute(f'PRAGMA index_info("{idx[1]}")').fetchall()
                names = [cols[r[1]][1] for r in info if r[1] >= 0]
                if idx[2] and idx[3] and names == ["external_source", "external_id"]:
                    unique_external = True
        if not unique_external:
            print("v0.6.8 migration: metadata_links already allows shared external IDs")
            return
        con.execute("ALTER TABLE metadata_links RENAME TO metadata_links_v067")
        con.execute("""CREATE TABLE metadata_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            provider_title TEXT,
            external_source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            match_status TEXT NOT NULL CHECK(match_status IN ('matched','review','rejected')),
            match_score REAL,
            matched_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(content_id, external_source),
            FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_content ON metadata_links(content_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_status ON metadata_links(match_status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_metadata_links_external ON metadata_links(external_source, external_id)")
        con.execute("""INSERT INTO metadata_links
            (id,content_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at)
            SELECT id,content_id,provider_title,external_source,external_id,match_status,match_score,matched_by,updated_at
            FROM metadata_links_v067""")
        con.execute("DROP TABLE metadata_links_v067")
        con.commit()
        print("v0.6.8 migration: metadata_links rebuilt; shared external IDs allowed")


if __name__ == "__main__":
    main()
