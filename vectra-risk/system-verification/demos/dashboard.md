# D4: el dashboard de producto (dashboard, U11)

Historias: US-503, US-504 y US-505.

## Prerrequisitos

- `decisions` terminó el día D: es lo que alimenta a U11. La sección `u11` **no corre** hasta el día UTC siguiente.
- Aviso del arranque: si `product-metrics` arrancó antes que el registro de decisiones, el dashboard **sale vacío hasta 30 min**. Aviso del día 1 del mes: falta el acumulado del mes (`month_to_date`).

## Tiempo real

Día D: `decisions` estima 2 000 / 10 + 2 000 × 1 s + 300 s ≈ 42 min y **no empieza si no termina antes de las 23:00 UTC** (18:00 de Colombia): hay que lanzarla antes de ≈ 22:18 UTC. Día D + 1: la pasada completa de U11 es a las **02:30 UTC** más hasta 10 min de desfase (≈ 21:30 a 21:40 de Colombia del día D); `u11` se corre después.

## Acceso a Grafana

Grafana no tiene OIDC ni `root_url`: el presentador entra por `port-forward` al pod de Grafana en `vectra-observability` con la cuenta `grafana-admin`. **Los permisos por carpeta y rol no se enseñan en la demo** (Grafana no tiene OIDC: es una candidata abierta de U1).

## Pasos

| N | Quién | Qué hace | Qué se ve y dónde | Verify |
|---|---|---|---|---|
| 1 | operador | Día D, antes de las 22:18 UTC: corre `vectra-verification decisions`. | SIM-NORMAL en la salida. | `dashboard.sh 5` |
| 2 | operador | Comprueba que Grafana está arriba. | — | `dashboard.sh 1` |
| 3 | operador | Día D + 1, tras las 02:40 UTC: corre `vectra-verification u11`. | `dashboard` en la salida. | `dashboard.sh 2` |
| 4 | presentador | Abre Grafana por `port-forward` con `grafana-admin`; muestra el dashboard `Producto` (uid `vectra-producto-panel`) en la carpeta `Vectra / Producto`. | Paneles: panel `North Star de ayer`, panel `Recomendaciones sostenidas (aproximación)`, panel `Tasa de consulta de la explicación y piso F` y panel `Días bajo el piso`. | `dashboard.sh 3` |
| 5 | operador | Comprueba la evidencia. | — | `dashboard.sh 4` |

## Qué deja sucio y cómo se limpia

Nada en el clúster. Las series de U11 se alimentan solas cada día.

## Qué saldrá `no ejecutado`

`u11` sale `no ejecutado` el mismo día UTC de `decisions` (`u11_antes_de_d_mas_1`) y antes de las 02:40 UTC más el plazo de la pasada (`u11_pasada_pendiente`). La evidencia dice que `RuidoExplicacion` no se verifica en kind (se verifica con `promtool`).
