# IPTV Manager — v0.2 / Paso 5

Proyecto central del catálogo IPTV.

La selección sigue gobernada por `config.yml`:
- 75 categorías de series
- 44 categorías de películas
- LIVE independiente

## Paso 5

**05 - Modelo de contenido y versiones**

Esta prueba empieza a transformar las entradas Xtream en un modelo de
contenido:

Películas → versiones → streams

Series → temporadas → episodios → versiones → streams

Las categorías se conservan como procedencia y como señales de calidad,
resolución, HDR, Dolby, subtítulos e idioma.

La prueba usa una muestra pequeña y no modifica la playlist estable.
