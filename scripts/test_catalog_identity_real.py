from __future__ import annotations
from collections import defaultdict
from app.core.catalog_config import load_catalog_selection
from app.core.category_profiles import infer_category_profile
from app.core.config import settings
from app.core.content_identity import analyze_title
from app.core.normalization import normalize_category_name
from app.core.xtream import XtreamClient

def cmap(items):
    return {normalize_category_name(str(x.get("category_name",""))): {"name":str(x.get("category_name","")), "id":str(x.get("category_id",""))} for x in (items or [])}

def selected(names, provider):
    return [(n, provider[normalize_category_name(n)]) for n in names if normalize_category_name(n) in provider]

def main():
    print("="*72)
    print("IPTV MANAGER — PRUEBA 5.3: IDENTIDAD SOBRE CATÁLOGO REAL")
    print("="*72)
    print("\nAplica la identidad canónica de 5.2 a muestras reales.")
    print("No fusiona registros ni modifica playlists.")

    cfg = load_catalog_selection()
    client = XtreamClient(settings.xtream_host, settings.xtream_username, settings.xtream_password)
    print("\nAutenticando...")
    client.authenticate()
    print("  OK")

    ps, pv = cmap(client.series_categories()), cmap(client.vod_categories())
    sc, vc = selected(cfg.series_categories, ps), selected(cfg.movie_categories, pv)
    print(f"\nSeries: {len(sc)}/{len(cfg.series_categories)} categorías")
    print(f"VOD:    {len(vc)}/{len(cfg.movie_categories)} categorías")

    for label, cats, method, idkey in [
        ("SERIES", sc[:6], client.series_streams, "series_id"),
        ("VOD", vc[:6], client.vod_streams, "stream_id"),
    ]:
        print("\n"+"-"*72); print(label); print("-"*72)
        occ = defaultdict(list)
        for cname, cat in cats:
            items = method(cat["id"]) or []
            print(f"{cname}: {len(items)} entradas")
            profile = infer_category_profile(cname)
            for item in items:
                a = analyze_title(item.get("name",""))
                if a.canonical:
                    occ[a.canonical].append((cname, str(item.get(idkey,"")), profile))
        multi = [(k,v) for k,v in occ.items() if len(v)>1]
        print(f"\nCandidatos únicos: {len(occ)}")
        print(f"Candidatos en 2+ categorías: {len(multi)}")
        for key, entries in sorted(multi)[:8]:
            print(f"\n  CANDIDATO: {key}")
            for cname, sid, p in entries:
                sig = []
                for n,v in (("quality",p.quality),("resolution",p.resolution),("dynamic_range",p.dynamic_range),("audio",p.audio),("subtitles",p.subtitles),("language",p.language_hint)):
                    if v is not None: sig.append(f"{n}={v}")
                print(f"    - {cname} | source_id={sid} | {', '.join(sig) if sig else 'sin señales'}")

    print("\n"+"="*72)
    print("PRUEBA 5.3 COMPLETADA")
    print("Identidad medida sobre datos reales; sin sincronización.")
    print("="*72)

if __name__ == "__main__":
    main()
