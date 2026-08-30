import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

DB = Path("data/iptv_manager.db")

def main():
    print("=" * 72)
    print("IPTV MANAGER — v0.4.3: UI SOBRE CATÁLOGO REAL")
    print("=" * 72)
    client = TestClient(app)

    for path in ("/ui/", "/ui/style.css", "/ui/app.js"):
        r = client.get(path)
        assert r.status_code == 200, f"{path}: HTTP {r.status_code}"
        print(f"  OK | {path}")

    if not DB.exists():
        raise RuntimeError("No se encontró data/iptv_manager.db")

    conn = sqlite3.connect(DB)
    try:
        tables = ("content", "version", "stream", "season", "episode", "category")
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        row = conn.execute(
            "SELECT normalized_title FROM content "
            "WHERE is_active=1 AND normalized_title IS NOT NULL "
            "AND length(trim(normalized_title)) >= 3 ORDER BY id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    print(f"  BD real encontrada: {DB} ({DB.stat().st_size / 1024 / 1024:.1f} MB)")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    assert counts["content"] > 0 and counts["version"] > 0 and counts["stream"] > 0
    assert counts["category"] > 0

    r = client.get("/api/stats")
    assert r.status_code == 200, r.text
    print("  OK | API stats")

    seed = row[0][:3] if row else None
    if not seed:
        raise RuntimeError("No hay semilla de búsqueda válida")
    r = client.get("/api/search", params={"q": seed})
    assert r.status_code == 200, r.text
    payload = r.json()
    results = payload.get("results", payload) if isinstance(payload, dict) else payload
    assert results, f"La búsqueda real no devolvió resultados para '{seed}'"
    print(f"  OK | búsqueda real '{seed}' → {len(results)} resultados")

    print("=" * 72)
    print("v0.4.3 COMPLETADA")
    print("Interfaz web validada contra el catálogo real.")
    print("No se consulta Xtream ni se modifica el catálogo.")
    print("=" * 72)

if __name__ == "__main__":
    main()
