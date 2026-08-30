from __future__ import annotations

import json
from app.services.sync import run_sync


if __name__ == "__main__":
    print("=" * 72)
    print("IPTV MANAGER — v0.3: SINCRONIZACIÓN INCREMENTAL DEL CATÁLOGO")
    print("=" * 72)
    print("Fuente de selección: config.yml")
    print("Modo: importación real / incremental")
    print("La primera ejecución puede ser larga; las siguientes omiten detalles sin cambios.")
    print()
    result = run_sync()
    print("\nRESUMEN FINAL")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nSincronización completada correctamente.")
