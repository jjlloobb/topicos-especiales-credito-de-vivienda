# Arbitraje de la ronda 1 — U04-T02

Orquestador, 2026-11-09. Informe: `revisiones/U04-T02/ronda-1.md`. VERDE, sin ROJO ni NARANJA, con cinco AMARILLO.

## Decisión: se abre el PR

- Los siete criterios pasan en las corridas del revisor. CA-7 pasa por el plan B de la tarea: `check-tools` no corre en el worktree porque `platform/.tools` no existe, el diff no toca `platform/`, y el CI del PR corre `make -C platform check` completo.
- F-01 a F-05 (AMARILLO) y las candidatas del codificador pasan a `CANDIDATAS.md`. Las de `reason` y justificación son del Paso 10 y se nombran en la tarea del Bloque D.
