# Roadmap

## v0.3 — Core funcional
- [x] Selección central desde `config.yml`
- [x] Identidad de contenido
- [x] Contenido / versiones / streams
- [x] Temporadas / episodios
- [x] Importación real
- [x] Sincronización incremental
- [x] Consultas de detalle concurrentes y limitadas
- [x] Soft-delete de streams desaparecidos
- [x] Historial básico de sincronización y cambios
- [x] Base local persistente durante la ejecución
- [ ] Persistencia compartida entre ejecuciones de GitHub
- [x] API de catálogo base

## Beta — Biblioteca utilizable
- [x] Interfaz web
- [x] Buscador
- [x] Navegación por películas, series y categorías
- [x] Detalle de películas y series
- [x] Temporadas y episodios con fuentes de reproducción
- [x] Metadatos TMDB persistentes
- [x] Fallback TVmaze para episodios
- [x] Regresión combinada TMDB + TVmaze
- [x] Endpoint de novedades por fecha de descubrimiento
- [ ] Detector de novedades persistente entre sincronizaciones
- [ ] Estadísticas de catálogo y cobertura de metadatos
- [ ] Middleware / URLs estables
- [ ] Autenticación y configuración de acceso
- [ ] Exportación M3U / catálogo para clientes IPTV
- [ ] Telegram

## Estabilización pre-1.0
- [ ] Pruebas de integración API + UI
- [ ] Pruebas de regresión de catálogo a gran escala
- [ ] Observabilidad y logs estructurados
- [ ] Gestión de errores y reintentos de proveedores
- [ ] Optimización de consultas e índices
- [ ] Backups/versionado de la base persistente
