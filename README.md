# IPTV Manager — v0.4.3

Primera base de API del producto.

## Arquitectura

`Xtream → sincronizador → SQLite → Repository → FastAPI → futura interfaz`

La API sirve el catálogo desde la BD y no consulta Xtream al navegar.

## Incluye

- Capa Repository para aislar el acceso a la BD.
- FastAPI 0.4.3.
- Health check.
- Estadísticas.
- Categorías seleccionadas.
- Búsqueda de películas y series.
- Detalle de películas con categorías, versiones y streams.
- Detalle de series con temporadas, episodios, versiones y streams.
- Detalle individual de episodio.
- Prueba automatizada de API con BD SQLite temporal.
- Workflow de GitHub Actions para ejecutar la prueba.

La configuración central continúa en `config.yml`. LIVE permanece independiente
del catálogo VOD en esta fase.

## Ejecutar

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Documentación interactiva: `/docs`.

## Importante

Esta versión todavía no incorpora la interfaz gráfica definitiva ni cambia el
alojamiento de la BD. Es la base sobre la que se construirá el frontend.
