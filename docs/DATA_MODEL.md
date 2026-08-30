# Modelo de datos v0.2

La base de datos ya no trata la M3U como el catálogo. La M3U/Xtream es una
fuente de streams; el Core construye encima un catálogo normalizado.

## Jerarquía principal

```text
CATÁLOGO
├── CANALES
│   └── STREAMS
│
├── PELÍCULAS
│   ├── COLECCIONES / SAGAS
│   └── VERSIONES
│       └── STREAMS
│
└── SERIES
    └── TEMPORADAS
        └── EPISODIOS
            └── VERSIONES
                └── STREAMS
```

## Entidades

### `providers`
Proveedor de origen. Permite que el Core pueda soportar más de una fuente en
el futuro.

### `categories`
Categorías originales del proveedor. Se conservan como procedencia y no como
estructura principal del catálogo.

### `content`
Entidad canónica para canales, películas y series.

Un mismo título canónico no debería duplicarse simplemente porque exista en
varias categorías o con varias calidades.

### `collections`
Agrupa películas relacionadas, especialmente sagas.

Ejemplo:

```text
Marvel
├── Iron Man
├── Iron Man 2
├── The Avengers
└── ...
```

Una película puede pertenecer a una colección y también relacionarse con otras
películas mediante futuras tablas de relaciones.

### `seasons`
Temporadas de una serie.

### `episodes`
Episodios identificados por serie + temporada + número de episodio.

Esto permite detectar correctamente que una nueva entrada corresponde, por
ejemplo, a `S02E07` aunque el proveedor modifique ligeramente el nombre.

### `versions`
Representa una variante técnica del mismo contenido/episodio:

- calidad
- resolución
- códec de vídeo
- códec de audio
- HDR/Dolby Vision u otra característica de rango dinámico
- idiomas
- subtítulos

### `streams`
Es el enlace real proporcionado por el proveedor.

Así separamos:

```text
The Last of Us S02E07
        ↓
     versión
   1080p / ES
        ↓
      stream
       URL
```

Una misma versión podría tener más de un stream/proveedor.

### `sync_runs`
Histórico de sincronizaciones.

Permitirá saber cuánto contenido había en cada ejecución y calcular crecimiento.

### `change_events`
Registro de novedades:

- `added`
- `changed`
- `removed`

Será la base del futuro detector de novedades y de las estadísticas.

## Decisión importante

No intentaremos adivinar todavía toda la metadata externa. Primero sincronizaremos
fielmente lo que Xtream proporciona y después añadiremos un módulo de enriquecimiento
para posters, títulos canónicos, sagas, géneros y relaciones.

Esto evita que una fuente externa pueda alterar accidentalmente la información
original del proveedor.
