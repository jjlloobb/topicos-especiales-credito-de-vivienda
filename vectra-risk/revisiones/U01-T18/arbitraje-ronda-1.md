# U01-T18 — Arbitraje de la ronda 1 (orquestador, 2026-11-17)

Informe: `ronda-1.md`. NO-VERDE **sin ningún ROJO**: un NARANJA (F-01) y cuatro AMARILLO. Los cuatro criterios pasan en las corridas del revisor y el arreglo central (`--subresource`) es correcto.

**Decisión: ronda 2, la última (RL-2), acotada.** Por RL-3 un NARANJA no bloquea, pero F-01 es una regresión de detección que introduce este mismo diff en una comprobación de seguridad, y su arreglo es de tres filas. Mismo criterio que en U01-T17.

| Hallazgo | Decisión | Qué se pide |
|---|---|---|
| F-01 NARANJA: sin `clusterroles` en los namespaces no se ve `bind clusterroles` concedido por una RoleBinding | Ronda 2 | `bind clusterroles` se pregunta también en los tres namespaces (89 → 92 filas). `escalate clusterroles`, `nodes`, `nodes/proxy` y `nodes/log` siguen solo en `cluster`. Corrige en el documento la frase «la respuesta no añade nada» y la cifra. Una prueba con un falso que contesta `yes` a `bind clusterroles` solo con `-n vectra-app` debe dar rc 1 |
| G-02 AMARILLO: la tabla mínima no fija 5 filas de «no» frente a un intercambio | Ronda 2 | La prueba compara con el conjunto exacto de tuplas (ámbito, verbo, recurso, subrecurso, esperado). Las cinco mutaciones del revisor deben morir |
| G-03 AMARILLO: a la orden para el orquestador le falta el directorio | Ronda 2 | En la bitácora: la orden con `cd vectra-risk`, sin el `KUBECONFIG` que sobra, y la línea final con la cifra nueva |
| G-01 AMARILLO: `CLUSTER_SCOPED` duplicado en la prueba | Candidata | Si G-02 lo deja resuelto de paso, dilo |
| G-04 AMARILLO: `impersonate users` por namespace | Candidata | No da falsos verdes |

A `CANDIDATAS.md`, al final: G-01 y G-04 (si no quedan cerrados de paso) y las tres candidatas del informe (`escalate`/`bind roles` y `create rolebindings` por namespace; `delete *` solo mira el grupo núcleo; rojo en falso si falta una CRD).
