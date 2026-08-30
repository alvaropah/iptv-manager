# Paso 5.6 — Modelo de base de datos

Define la estructura persistente del catálogo sin importar todavía datos reales.

Jerarquía principal:

**Contenido → Versión → Stream**

Para series:

**Contenido → Temporada → Episodio → Versión de episodio → Stream**

Las categorías mantienen sus señales técnicas (calidad, resolución, rango
dinámico, audio, subtítulos e indicación de idioma) para poder reutilizarlas
como metadatos de las versiones.

La prueba solo crea una base SQLite temporal y valida tablas, relaciones y
estado inicial vacío. No modifica la playlist ni el catálogo real.
