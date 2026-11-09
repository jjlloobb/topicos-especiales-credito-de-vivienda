# Arbitraje de la ronda 1 — U04-T01

Orquestador, 2026-11-09. Informe: `revisiones/U04-T01/ronda-1.md`. Salió NO-VERDE con dos NARANJA de entorno, tres AMARILLO y ningún ROJO. Los criterios 1 a 4 y el 6 pasan en las corridas del revisor: 40 pruebas de migraciones contra `postgres:17.9-trixie` y `make -C governance check` en 0.

## Decisión: no se abre ronda 2 (RL-2) y se abre el PR

- **F-01 (NARANJA, CA-5):** el clasificador de permisos de esta máquina le negó `docker run -p` al codificador y al revisor. No es un defecto del diff. Las pruebas de integración leen con SQL real la misma estructura, los índices, los triggers y los privilegios. Lo único sin cubrir es el camino `GOVERNANCE_DATABASE_URL` de `env.py`. El CA-5 queda **pendiente de que lo corra el usuario**, con el script que le entrega el orquestador. Su resultado se anota en el PR antes de fusionar. Va también como candidata: una prueba de `env.py` que use la variable.
- **F-02 (NARANJA, CA-7):** `charts.sh` falló con 504 de github.com, y `pytest platform` se cuelga sin `DOCKER_HOST`. El diff no toca `platform/`, y las piezas de `check-local` que dependen de `uv.lock` pasan. El CI corre `make -C platform check` completo en el PR, y el `pytest platform` colgado pasa a candidata.
- **F-03 a F-05 (AMARILLO)** pasan a candidatas. F-03 es un hueco de P-U4-06 y BR-U4-03, no del código, y ninguna demo pasa por `congelado → inactivo`. Se revisa con el diseño antes del Bloque D de U4.

El `uv.lock` y el `pyproject.toml` raíz chocarán con U09-T01, que se revisa en paralelo. El PR que entre segundo lo integra el orquestador con `uv lock`.
