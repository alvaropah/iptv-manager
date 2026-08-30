# v0.3 — Notas de implementación

La prueba 5.7 demostró que pedir `get_series_info` de forma secuencial para todas
las series es demasiado lento. En v0.3 el acceso a detalles está limitado y
concurrente, y las siguientes sincronizaciones solo lo solicitan para series
nuevas o cuya huella haya cambiado.

Importante: la base de datos de GitHub Actions se entrega como artefacto en esta
primera iteración. No se activa todavía un cron automático porque la persistencia
entre ejecuciones necesita una estrategia estable (servidor/volumen o storage
externo). Esto evita aparentar una persistencia que GitHub Actions por sí solo no
garantiza.
