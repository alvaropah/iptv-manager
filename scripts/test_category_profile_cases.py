from app.core.category_profiles import infer_category_profile


CASES = {
    "ESPAÑA SERIES ⁴ᴷ ᴴᴰᴿ ᴰᴼᴸᴮʸ ⱽᴵˢᴵÓᴺ": {
        "quality": "4K", "resolution": "2160p",
        "dynamic_range": "Dolby Vision", "language_hint": "es",
    },
    "PARAMOUNT+ ⁴ᴷ ³⁸⁴⁰ᴾ ᴰᵒˡᵇʸ ⱽᶦˢᶦᵒⁿ": {
        "quality": "4K", "resolution": "2160p",
        "dynamic_range": "Dolby Vision",
    },
    "CRUNCHYROLL SERIES (MULTI-SUBS)": {
        "subtitles": True,
    },
    "ES - PELÍCULAS 2026": {
        "language_hint": "es",
    },
    "ES - PELÍCULAS SUBTITLES": {
        "subtitles": True, "language_hint": "es",
    },
}


def main():
    print("IPTV MANAGER — PRUEBA 4.1: CASOS CORREGIDOS")
    print("=" * 72)
    failed = 0

    for name, expected in CASES.items():
        p = infer_category_profile(name)
        actual = {
            "quality": p.quality,
            "resolution": p.resolution,
            "dynamic_range": p.dynamic_range,
            "audio": p.audio,
            "subtitles": p.subtitles,
            "language_hint": p.language_hint,
        }
        ok = all(actual.get(k) == v for k, v in expected.items())
        print(f"{'OK' if ok else 'ERROR'} | {name}")
        print(f"  esperado: {expected}")
        print(f"  obtenido: {actual}")
        if not ok:
            failed += 1

    print("=" * 72)
    if failed:
        print(f"PRUEBA 4.1 FALLIDA — {failed} caso(s)")
        raise SystemExit(1)
    print("PRUEBA 4.1 COMPLETADA — todos los casos corregidos funcionan.")


if __name__ == "__main__":
    main()
