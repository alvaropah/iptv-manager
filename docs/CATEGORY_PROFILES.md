# Perfiles de categorías — Paso 4

Esta prueba interpreta únicamente las 119 categorías seleccionadas en
`config.yml`.

No consulta Xtream y no descarga catálogo.

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

Los campos desconocidos quedan en `NULL`.

La categoría original del proveedor se conservará posteriormente como
procedencia. Estas inferencias serán una señal adicional, no un sustituto
del nombre original ni de otros metadatos.
