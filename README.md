# IPTV Manager v0.2

Núcleo central para gestionar una fuente Xtream y construir un catálogo VOD
normalizado alrededor de la selección personal de categorías.

## Regla principal

`config.yml` es la fuente de verdad de la selección. Actualmente contiene las
categorías de series y películas que ya utiliza el generador estable.

- Las categorías VOD no seleccionadas por el usuario se ignoran.
- LIVE/TV queda separado y no utiliza esta selección VOD.
- Las futuras funciones reutilizarán el mismo catálogo filtrado.

```text
                    XTREAM
                       |
          +------------+------------+
          |                         |
         LIVE                     VOD/SERIES
          |                         |
         TV                    config.yml
                                    |
                                    v
                              CORE / SYNC
                                    |
                             BASE DE DATOS
                                    |
                +-------------------+-------------------+
                |         |          |        |         |
             Middleware Stats     Novedades Buscador Telegram
```

## Estado

- Conexión Xtream: probada.
- Categorías reales: probadas.
- Selección central desde `config.yml`: implementada y validada.
- Sincronización masiva: todavía no ejecutada.
