from app.core.content_identity import analyze_title

GROUPS = [
    ("CLARAMENTE IGUALES", ["The Last of Us", "4K-The Last of Us", "The Last of Us 4K"], "same"),
    ("IGUALES CON IDIOMA / TÉCNICA", ["The Last of Us", "The Last of Us (ES)", "The Last of Us 4K Dolby Vision"], "same"),
    ("IGUALES CON AÑO", ["Love & Death (2023)", "Love & Death 2023"], "same"),
    ("EPISODIO: MISMA OBRA BASE", ["The Last of Us S01E01", "The Last of Us S01E01 4K"], "same"),
    ("DIFERENTES — NO FUSIONAR", ["The Office (US)", "The Office (UK)"], "different"),
    ("DIFERENTES — AÑO DIFERENTE", ["The Equalizer (2014)", "The Equalizer (2021)"], "different"),
    ("AMBIGUO — NO DECIDIR AUTOMÁTICAMENTE", ["Avatar", "Avatar (2009)"], "ambiguous"),
]

def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 5.2: IDENTIDAD Y VARIACIONES DE TÍTULO")
    print("=" * 72)
    failures = 0
    for label, titles, expected in GROUPS:
        analyses = [analyze_title(t) for t in titles]
        keys = [a.canonical for a in analyses]
        years = [a.year for a in analyses]
        same_key = len(set(keys)) == 1

        if expected == "same":
            ok = same_key
            result = "CANDIDATO IGUAL"
        elif expected == "different":
            ok = (not same_key) or years[0] != years[1]
            result = "NO FUSIONAR"
        else:
            # One title has an explicit year while the other does not.
            # They must not be auto-merged.
            ok = (not same_key) and years[0] is None and years[1] is not None
            result = "AMBIGUO — REQUIERE RESOLUCIÓN"

        print(f"\n{label}")
        for a in analyses:
            print(f"  {a.original} -> canonical='{a.canonical}' | year={a.year}")
        print(f"  resultado: {result} | {'OK' if ok else 'ERROR'}")
        if not ok:
            failures += 1

    print("\n" + "=" * 72)
    if failures:
        print(f"PRUEBA 5.2 FALLIDA — {failures} caso(s)")
        raise SystemExit(1)
    print("PRUEBA 5.2 COMPLETADA — todos los casos pasan.")
    print("La normalización genera candidatos; no fusiona automáticamente los ambiguos.")
    print("=" * 72)

if __name__ == "__main__":
    main()
