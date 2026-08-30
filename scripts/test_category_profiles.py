from __future__ import annotations
from collections import Counter
from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile

def show(section, categories):
    print("\n" + "=" * 72)
    print(section)
    print("=" * 72)
    counters = Counter()
    for name in categories:
        p = infer_category_profile(name)
        signals = []
        for label, value in (
            ("quality", p.quality),
            ("resolution", p.resolution),
            ("dynamic_range", p.dynamic_range),
            ("audio", p.audio),
            ("subtitles", p.subtitles),
            ("language_hint", p.language_hint),
        ):
            if value is not None:
                signals.append(f"{label}={value}")
                counters[label] += 1
        print(name)
        print("  " + (", ".join(signals) if signals else "sin señales técnicas explícitas"))
    print("\nRESUMEN")
    for key in ("quality", "resolution", "dynamic_range", "audio", "subtitles", "language_hint"):
        print(f"  {key}: {counters[key]} categorías")

def main():
    cfg = load_catalog_selection()
    print("IPTV MANAGER — PRUEBA 4: INTERPRETACIÓN DE CATEGORÍAS")
    print("=" * 72)
    print(f"Series configuradas: {len(cfg.series_categories)}")
    print(f"Películas configuradas: {len(cfg.movie_categories)}")
    print("\nNo se consulta Xtream en esta prueba.")
    print("Se prueban las reglas sobre las categorías seleccionadas.")
    show("SERIES", cfg.series_categories)
    show("PELÍCULAS / VOD", cfg.movie_categories)
    print("\n" + "=" * 72)
    print("PRUEBA 4 COMPLETADA")
    print("=" * 72)

if __name__ == "__main__":
    main()
