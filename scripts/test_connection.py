from app.core.config import settings
from app.core.xtream import XtreamClient

def main():
    print("=" * 72)
    print("IPTV MANAGER — PRUEBA 1: CONEXIÓN Y CATEGORÍAS")
    print("=" * 72)
    client = XtreamClient(settings.xtream_host, settings.xtream_username, settings.xtream_password)
    print("\n1. Autenticando contra Xtream...")
    auth = client.authenticate()
    user_info = auth.get("user_info", {})
    print("   OK — autenticación correcta.")
    print(f"   Estado: {user_info.get('status', 'desconocido')}")
    for label, fn in (
        ("2. Consultando categorías LIVE...", client.live_categories),
        ("3. Consultando categorías VOD...", client.vod_categories),
        ("4. Consultando categorías SERIES...", client.series_categories),
    ):
        print(f"\n{label}")
        data = fn()
        print(f"   OK — {len(data) if isinstance(data, list) else 0} categorías.")
    print("\n" + "=" * 72)
    print("PRUEBA 1 COMPLETADA — no se ha descargado el catálogo.")
    print("=" * 72)

if __name__ == "__main__":
    main()
