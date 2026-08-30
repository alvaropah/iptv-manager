# Paso 5.1 — Episodios y versiones

Esta prueba comprueba una relación crítica para el modelo de series:

`Serie → versión → temporada → episodio`

Busca dos categorías seleccionadas consecutivas que compartan una serie,
consulta ambas series y compara sus episodios por `temporada + episode_num`.

Para cada episodio común muestra el ID del episodio y las señales de categoría
de cada versión.

También informa de episodios que solo aparecen en una de las dos versiones.

No se sincroniza el catálogo completo ni se modifica ninguna playlist.
