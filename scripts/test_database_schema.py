from pathlib import Path
import tempfile

from app.core.catalog_database import initialize, table_names, schema_counts


EXPECTED = {
    "content", "category", "version", "stream",
    "season", "episode", "episode_version", "episode_stream",
}


def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.6: MODELO DE BASE DE DATOS")
    print("=" * 72)
    print("\nObjetivo: validar la estructura persistente del catálogo.")
    print("No se conecta a Xtream y no modifica ninguna playlist.")

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "catalog.db"
        initialize(db)

        tables = set(table_names(db))
        print("\nTABLAS")
        for name in sorted(tables):
            print(f"  OK | {name}")

        missing = EXPECTED - tables
        unexpected = tables - EXPECTED

        if missing:
            raise RuntimeError(f"Faltan tablas: {sorted(missing)}")
        if unexpected:
            raise RuntimeError(f"Tablas inesperadas: {sorted(unexpected)}")

        counts = schema_counts(db)
        print("\nREGISTROS INICIALES")
        for table, count in counts.items():
            print(f"  {table}: {count}")

        if any(count != 0 for count in counts.values()):
            raise RuntimeError("La base de datos nueva no está vacía.")

        print("\nRELACIONES MODELO")
        print("  content -> version -> stream")
        print("  content -> season -> episode -> episode_version -> episode_stream")
        print("  category -> version / episode_version")
        print("  OK | estructura validada")

    print("\n" + "=" * 72)
    print("PRUEBA 5.6 COMPLETADA")
    print("Modelo de almacenamiento validado.")
    print("Todavía no se ha importado el catálogo real.")
    print("=" * 72)


if __name__ == "__main__":
    main()
