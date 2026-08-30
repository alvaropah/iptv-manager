# IPTV Manager — v0.3

Primera versión funcional del Core del proyecto.

La selección continúa gobernada por `config.yml` (75 categorías de series y 44
de películas en la configuración actual). LIVE permanece independiente.

## Qué aporta v0.3

- Importación real del catálogo seleccionado.
- SQLite como catálogo central.
- Modelo Contenido → Versión → Stream.
- Series → Temporadas → Episodios → Versiones → Streams.
- Preservación de categorías como procedencia y señales técnicas.
- Primera sincronización completa.
- Sincronizaciones posteriores incrementales.
- Consultas de detalles de series concurrentes con límite de workers.
- Streams desaparecidos marcados como inactivos, no eliminados.
- Historial de sincronizaciones y cambios.

La primera ejecución puede tardar porque debe descubrir los episodios de las
series existentes. Después se evita volver a pedir el detalle de las series que
no hayan cambiado según la huella de su entrada en Xtream.

## GitHub Actions

`06-sync-catalog-v03.yml` se ejecuta manualmente durante esta etapa. Produce la
base SQLite como artefacto para poder revisar el resultado antes de activar
cualquier automatización periódica.
