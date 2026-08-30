# Arquitectura

## Fuente de verdad de selección

`config.yml` es la fuente de verdad de qué contenido VOD entra en el sistema.
Contiene las categorías de series y películas seleccionadas manualmente.

El proveedor puede tener cientos o miles de categorías adicionales; no entran en
el catálogo por existir en Xtream.

```text
Xtream
  |
  +--> LIVE ----------------------> TV (independiente)
  |
  +--> VOD/SERIES --> config.yml -> Core -> catálogo VOD
                                  |
                                  +-> películas
                                  +-> series -> temporadas -> episodios
                                  +-> versiones -> streams
```

## Componentes

- `config.yml`: selección manual de categorías.
- `app/core/catalog_config.py`: carga, valida y expone esa selección.
- `app/core/xtream.py`: cliente Xtream.
- `app/db`: persistencia.
- `app/services`: sincronización futura.
- `app/web`: API/interfaz futura.

Todas las funciones posteriores (middleware, estadísticas, novedades, buscador y
Telegram) consumirán el catálogo filtrado por esta selección, no el catálogo
completo del proveedor.
