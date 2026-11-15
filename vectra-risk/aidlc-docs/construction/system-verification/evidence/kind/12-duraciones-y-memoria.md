# 12 — Duraciones y memoria

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, «Al terminar» (todas las fases).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: —; la guía pide anotarla).

Esta plantilla no tiene entradas K: recoge lo que la guía pide medir en toda la corrida (CA-O9) para corregir después el README, la guía y, si hace falta, `BUDGET_GIB`.

## Duración de cada fase

| Fase | Estimada | Real | Observación |
|---|---|---|---|
| F0 Prerrequisitos | 30 min | _pendiente_ | _pendiente_ |
| F1 Imágenes y digests | 60 a 90 min | _pendiente_ | _pendiente_ |
| F2 Sync y arranque | 2 a 3 h | _pendiente_ | _pendiente_ |
| F3 Identidad y acceso | 40 min | _pendiente_ | _pendiente_ |
| F4 Flujo base | 15 min | _pendiente_ | _pendiente_ |
| F5 `prepare` y D3 | 20 min | _pendiente_ | _pendiente_ |
| F6 `decisions` | ≈ 45 min | _pendiente_ | _pendiente_ |
| F7 D1 | ≈ 50 min (≥ 19,3 de espera) | _pendiente_ | _pendiente_ |
| F8 D2 | ≈ 3 h (más de 75 min de esperas) | _pendiente_ | _pendiente_ |
| F9 D4 día D + 1 | 15 min | _pendiente_ | _pendiente_ |
| F10 Informe y estado final | 30 min | _pendiente_ | _pendiente_ |
| F11 Opcionales | 30 min | _pendiente_ | _pendiente_ |

## Memoria

| Momento | `free -m` disponible (MiB) | Comando | Observación |
|---|---|---|---|
| Al empezar la jornada 1 | _pendiente_ | `memoria.sh antes` | _pendiente_ |
| Al terminar la jornada 1 | _pendiente_ | `memoria.sh despues` | _pendiente_ |
| Al empezar la jornada 2 | _pendiente_ | `memoria.sh antes` | _pendiente_ |
| En el pico de D2 | _pendiente_ | `memoria.sh durante` | _pendiente_ |
| Al terminar la jornada 2 | _pendiente_ | `memoria.sh despues` | _pendiente_ |

| Medida | Valor | Frente a |
|---|---|---|
| Memoria del contenedor de U12 (`docker stats`, durante `decisions`) | _pendiente_ | `--memory 1g` |
| `case-service`, `case-worker`, BFF y `product-metrics` con 2 000 decisiones | _pendiente_ | request de 128 MiB |
| Constante de `guard`: 1 s por caso | _pendiente_ (real: segundos por caso) | `DECISION_SECONDS_PER_CASE` |
| Constante de `guard`: 300 s de margen | _pendiente_ | `MARGIN_SECONDS` |
| Ritmo real de `decisions` | _pendiente_ | 10/s |

## Correcciones que se derivan

_Ninguna todavía._ Lo que se mida distinto de lo estimado se corrige en el README, en la guía y, si hace falta, en `BUDGET_GIB` (`platform/tests/test_kind_profile.py`), por tarea y PR.

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
