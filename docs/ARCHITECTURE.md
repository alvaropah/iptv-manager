# Arquitectura

## Core

El núcleo será responsable de autenticación, sincronización, normalización,
identificación estable, snapshots y detección de cambios.

## Base de datos

SQLite se utiliza inicialmente para el prototipo. Antes de desplegarlo de forma
permanente decidiremos si conviene mantenerlo o migrar a PostgreSQL.

## Middleware

Generará playlists derivadas del catálogo, por ejemplo:

- completa
- solo TV
- solo películas
- solo series
- perfiles personalizados

## Estadísticas

Utilizarán el historial de sincronizaciones y snapshots.

## Novedades

Compararán snapshots y las fechas `first_seen_at` / `last_seen_at`.

## Buscador

Consultarará la base de datos local y no hará una llamada a Xtream por cada búsqueda.

## Telegram

Será otra interfaz sobre el mismo Core.
