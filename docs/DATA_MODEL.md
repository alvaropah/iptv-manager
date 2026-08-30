# Modelo de datos v0.3

```text
CONTENIDO
  ├── VERSION ── STREAM
  │
  └── TEMPORADA ── EPISODIO ── VERSION ── STREAM
```

## Contenido
Una identidad canónica de película o serie.

## Versión
Representa una combinación de procedencia/categoría y señales técnicas.
Puede diferenciar, por ejemplo, una entrada estándar de una entrada 4K Dolby.

## Stream
La entrada reproducible concreta del proveedor. Se conserva su `source_id`,
URL construida, extensión y JSON original.

## Series
Una serie tiene temporadas y episodios. Cada episodio puede disponer de varias
versiones y streams, igual que una película.

## Sincronización incremental
`series_sources` conserva una huella de cada `series_id` por categoría. Si la
huella no cambia y ya existe detalle sincronizado, la siguiente ejecución no
hace `get_series_info` para esa fuente.
