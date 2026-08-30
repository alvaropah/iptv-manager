from __future__ import annotations

from app.db.database import init_db, connect


def main():
    init_db()
    with connect() as conn:
        print("IPTV MANAGER — ESTADO DEL CATÁLOGO v0.3")
        for label, sql in [
            ("Películas", "SELECT COUNT(*) FROM content WHERE content_type='movie' AND is_active=1"),
            ("Series", "SELECT COUNT(*) FROM content WHERE content_type='series' AND is_active=1"),
            ("Temporadas", "SELECT COUNT(*) FROM seasons WHERE is_active=1"),
            ("Episodios", "SELECT COUNT(*) FROM episodes WHERE is_active=1"),
            ("Versiones", "SELECT COUNT(*) FROM versions WHERE is_active=1"),
            ("Streams activos", "SELECT COUNT(*) FROM streams WHERE is_active=1"),
        ]:
            print(f"  {label}: {conn.execute(sql).fetchone()[0]}")
        run = conn.execute(
            "SELECT id,status,started_at,finished_at,new_count,changed_count,removed_count,detail_requests,skipped_detail_requests,error "
            "FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if run:
            print("\nÚltima sincronización:")
            print(f"  #{run['id']} | {run['status']} | inicio={run['started_at']} | fin={run['finished_at']}")
            print(f"  nuevos={run['new_count']} cambios={run['changed_count']} eliminados={run['removed_count']}")
            print(f"  detalles={run['detail_requests']} omitidos={run['skipped_detail_requests']}")
            if run['error']:
                print(f"  error={run['error']}")


if __name__ == "__main__":
    main()
