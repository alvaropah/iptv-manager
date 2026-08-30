# IPTV Manager v0.1

Núcleo central para gestionar una fuente Xtream y añadir progresivamente:

- Middleware IPTV
- Buscador web
- Estadísticas
- Detector de novedades
- Bot de Telegram

## Importante

El repositorio estable `alvaropah/iptv` no se modifica desde este proyecto.
Este proyecto es independiente y reutilizará sus ideas y lógica cuando corresponda.

## Arquitectura

```text
XTREAM
   |
   v
CORE / SYNC
   |
   v
BASE DE DATOS
   |
   +--> Middleware
   +--> Estadísticas
   +--> Novedades
   +--> Buscador
   +--> Telegram
```

La fuente se sincroniza una vez y las funciones posteriores reutilizan esos datos.

## Seguridad

Las credenciales nunca se guardan en el código.
Para desarrollo local se usa `.env`; en producción se usarán secretos/variables del servicio de hosting.

## Estado

Esta versión añade el modelo de datos central: proveedor, categorías, contenido,
sagas/colecciones, temporadas, episodios, versiones, streams, sincronizaciones y eventos de cambios. Todavía no sustituye al generador estable.

## Arranque local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

En Windows, activar el entorno con `.venv\Scripts\activate`.

Abrir `http://127.0.0.1:8000` y la documentación en `/docs`.

## Próximo hito

Implementar la sincronización real de categorías, TV, películas, series y episodios,
guardando snapshots para detectar altas, bajas y cambios.
