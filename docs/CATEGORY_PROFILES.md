# Perfiles de categorías — Paso 4

Las categorías seleccionadas en `config.yml` son una fuente de metadata para
interpretar las versiones del contenido.

El sistema conserva siempre el nombre original del proveedor. El perfil es una
inferencia auxiliar, no una sustitución.

## Señales

- 4K / 3840p → 4K / 2160p
- 8K → 8K / 4320p
- 1080p / FHD → 1080p
- 720p / HD → 720p
- HDR → HDR
- Dolby Vision → Dolby Vision
- Dolby Audio → Dolby Audio
- Subtitles / Subtitle → subtítulos
- España → `es` como pista de idioma

## Regla de seguridad

Si una categoría no contiene una señal explícita, el campo queda `NULL`.

No se debe asumir que una categoría "España" significa que todos los streams
tienen audio español. Por eso el idioma se guarda como `language_hint` hasta
que una fuente más fiable lo confirme.

En el futuro, estas señales se combinarán con:

1. nombre original del stream/episodio;
2. metadatos de Xtream;
3. metadata externa, si se incorpora;
4. reglas de confianza.

Así podremos distinguir, por ejemplo, un episodio idéntico en nombre pero
procedente de categorías 1080p y 4K.
