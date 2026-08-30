# IPTV Manager — v0.2 / Paso 4

Repositorio completo desde cero hasta la Prueba 4.

## Selección central

`config.yml` es la fuente de selección del catálogo VOD:
- 75 categorías de series
- 44 categorías de películas
- 119 categorías VOD

LIVE queda independiente.

## Workflows

Hay exactamente cuatro pruebas independientes:

1. **01 - Prueba conexión Xtream**
2. **02 - Prueba configuración central**
3. **03 - Descubrimiento catálogo**
4. **04 - Perfiles de categorías**

Para la prueba actual ejecuta **04 - Perfiles de categorías**.

La prueba 4 no se conecta a Xtream y no necesita Secrets.

## Arquitectura

Contenido ≠ versión ≠ stream.

Series:
Serie → Temporada → Episodio → Versión → Stream

Películas:
Película → Colección/Saga → Versión → Stream

Las categorías del proveedor se conservarán como procedencia y como señales
auxiliares para interpretar calidad, resolución, HDR, Dolby, subtítulos, etc.

## Estado

Hasta el Paso 4 solo hacemos pruebas. No se sincroniza el catálogo completo
ni se modifica la playlist estable.
