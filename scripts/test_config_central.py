from app.core.catalog_config import load_catalog_selection

def main():
    cfg = load_catalog_selection()
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 2: CONFIGURACIÓN CENTRAL")
    print("=" * 72)
    print("\nConfiguración cargada desde: config.yml")
    print(f"   Series seleccionadas: {len(cfg.series_categories)}")
    print(f"   Películas seleccionadas: {len(cfg.movie_categories)}")
    print(f"   Total categorías VOD seleccionadas: {cfg.total_vod_categories}")
    print("   LIVE: independiente del catálogo VOD.")
    print("\nPRUEBA 2 COMPLETADA — todavía no se descarga el catálogo.")
    print("=" * 72)

if __name__ == "__main__":
    main()
