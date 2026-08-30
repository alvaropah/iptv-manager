# IPTV Manager v0.3 — Arquitectura

`config.yml` sigue siendo la fuente de verdad de selección. El proveedor puede
contener muchas más categorías, pero solo las seleccionadas entran al Core.

## Flujo

Xtream → categorías seleccionadas → identidad → base de datos → API/interfaz

## Modelo

- Contenido: película o serie.
- Versión: procedencia/categoría + señales técnicas.
- Stream: entrada reproducible concreta.
- Series: temporada → episodio → versión → stream.

## Rendimiento

La primera sincronización consulta los detalles de las series necesarias y los
procesa con un número limitado de workers concurrentes.

En sincronizaciones posteriores se compara una huella de la entrada de serie.
Si no ha cambiado, no se solicita `get_series_info` otra vez. Las nuevas o
modificadas sí se consultan.

Los streams desaparecidos se marcan como inactivos en lugar de borrarse.
