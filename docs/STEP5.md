# Paso 5 — Modelo de contenido y versiones

El objetivo de esta prueba es pasar de "entradas de proveedor" a candidatos
de contenido.

## Modelo conceptual

Películas:

`Película → Versiones → Streams`

Series:

`Serie → Temporadas → Episodios → Versiones → Streams`

Una categoría del proveedor no se considera una película/serie diferente.
Se conserva como procedencia y como fuente de señales técnicas.

## Identidad

`normalize_content_title()` genera una clave de candidato conservadora.
Solo elimina prefijos de calidad explícitos `4K-` / `8K-` y normaliza espacios.
No intenta decidir por sí sola que dos títulos parecidos son la misma obra.

## Alcance de la prueba

Se consultan únicamente las dos primeras categorías seleccionadas de
películas y las dos primeras de series, hasta 20 entradas por categoría.

También se consulta el detalle de una serie de muestra para comprobar que
podemos representar temporadas y episodios.

No se genera ni modifica la playlist y no se sincroniza el catálogo completo.
