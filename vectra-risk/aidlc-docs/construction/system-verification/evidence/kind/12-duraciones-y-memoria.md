# 12 — Duraciones y memoria

**Estado: completa.** Llenada el 2026-11-22 (UTC) con lo medido contra `kind-vectra` el 20 y el 21 de noviembre.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, «Al terminar» (todas las fases).
- Fecha: 2026-11-20 (jornada 1) y 2026-11-21 a 2026-11-22 UTC (jornada 2).
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: de 9dc027f a fd33db6.
- Duración real de la fase: unas 5 h de órdenes repartidas en dos jornadas, sin contar esperas de aprobación ni las correcciones (estimada: —; la guía pide anotarla).

Esta plantilla no tiene entradas K: recoge lo que la guía pide medir en toda la corrida (CA-O9) para corregir después el README, la guía y, si hace falta, `BUDGET_GIB`.

## Duración de cada fase

| Fase | Estimada | Real | Observación |
|---|---|---|---|
| F0 Prerrequisitos | 30 min | unos 15 min | solo comprobaciones: el clúster ya estaba instalado |
| F1 Imágenes y digests | 60 a 90 min | unos 10 min | solo se reconstruyó la imagen de U12; los servicios venían de dos commits (H-2) |
| F2 Sync y arranque | 2 a 3 h | unos 15 min | solo lecturas; nada que sincronizar |
| F3 Identidad y acceso | 40 min | unos 10 min | la parte del presentador se confirmó el 21 de noviembre |
| F4 Flujo base | 15 min | unos 5 min | — |
| F5 `prepare` y D3 | 20 min | unos 16 min | con la espera del PR #226 |
| F6 `decisions` | ≈ 45 min | unos 17 min | `decisions` sola: 15 min 28 s; la estimación de 42 min sobra por un factor de 2,7 |
| F7 D1 | ≈ 50 min (≥ 19,3 de espera) | unos 30 min la primera pasada y 28 min la repetición | escalada a `no_disponible` en unos 16 min; se repitió tras corregir el oráculo (PR #229) |
| F8 D2 | ≈ 3 h (más de 75 min de esperas) | unos 2 h 5 min | `rt2` sola: 1 h 38 min 35 s; cierre 13 min 48 s tras el aviso |
| F9 D4 día D + 1 | 15 min | unos 5 min | más la búsqueda del tablero por las carpetas duplicadas (H-13) |
| F10 Informe y estado final | 30 min | unos 5 min | sin contar el llenado de plantillas |
| F11 Opcionales | 30 min | no ejecutada | opcional |

## Memoria

| Momento | `free -m` disponible (MiB) | Comando | Observación |
|---|---|---|---|
| Al empezar la jornada 1 | unos 3500 | `memoria.sh antes` | con el clúster ya instalado; la puerta era de 8 GiB (H-1, corregida en el PR #223) |
| Al terminar la jornada 1 | 3431 | `memoria.sh despues` | tras el ensayo de 20 casos |
| Al empezar la jornada 2 | 3231 | `memoria.sh antes` | puerta de 3072 |
| En el pico de D2 | 2637 | `memoria.sh durante` | 52 pods: los dos modelos completos más el de staging; puerta de 1536 |
| Al terminar la jornada 2 | 2711 | `memoria.sh despues` | 48 pods; 2925 al cerrar D2 |

| Medida | Valor | Frente a |
|---|---|---|
| Memoria del contenedor de U12 (`docker stats`, durante `decisions`) | 321,5 MiB | `--memory 1g` |
| `case-service`, `case-worker`, BFF y `product-metrics` con 2 000 decisiones | 75 y 76; 71 y 72; 68 y 70; 64 y 65 MiB | request de 128 MiB |
| Constante de `guard`: 1 s por caso | 0,46 s por caso (928 s para 2 000, envío incluido) | `DECISION_SECONDS_PER_CASE` |
| Constante de `guard`: 300 s de margen | no se midió aparte | `MARGIN_SECONDS` |
| Ritmo real de `decisions` | no se midió aparte; cero 429 | 10/s |

## Correcciones que se derivan

Tres, ya aplicadas: la puerta de memoria de `memoria.sh antes` (PR #223), la estimación de `decisions` (sobra por 2,7; no se cambió) y los oráculos de RT-5 y RT-3 (PR #229). Lo que se mida distinto de lo estimado se corrige en el README, en la guía y, si hace falta, en `BUDGET_GIB` (`platform/tests/test_kind_profile.py`), por tarea y PR.

## Hallazgos

H-1 a H-13, cada uno en la plantilla de su fase. Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
