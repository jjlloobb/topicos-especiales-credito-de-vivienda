# Revisión de Infrastructure Design — U1: flujos de `vectra-restore-drill`

**Fecha:** 2026-10-03
**Origen:** observación del usuario sobre INF-U1-06 (la fila de `vectra-restore-drill` listaba solo F75).

---

## Parte A — Hallazgos

**R1 — `flows.yaml` todavía no existe.** P-U1-01 lo define como la fuente de los flujos,
pero se crea en Code Generation, que está fuera del alcance actual. Hoy la única fuente es
`component-dependency.md`. La tabla de INF-U1-06 tiene que ser completa, no ilustrativa:
es la que va a leer quien escriba `flows.yaml`.

**R2 — A la fila le faltaban dos flujos.**
- F87 (métricas del simulacro).
- F80: el operador CloudNativePG controla también el cluster efímero, y la fila de F80 solo nombraba `vectra-data`.

Ya corregí las dos filas: INF-U1-06 y F80 en `component-dependency.md`.

**R3 — F87 está mal definido, y eso cambia la NetworkPolicy que se genera.**
- Dice «Pushgateway **o** scrape». Con *push*, el flujo sale de `vectra-restore-drill` (egress). Con *scrape*, entra desde `vectra-observability` (ingress). Son reglas opuestas.
- El scrape de un Job efímero no es confiable: el pod termina antes del siguiente scrape y la métrica se pierde.
- El puerto 8081 es el de las métricas de los servicios, no el de un Pushgateway (9091).
- No hay ningún Pushgateway en el inventario de componentes de U1.

---

## Parte B — Pregunta

## Question 1
¿Cómo publica `restore-drill` sus métricas (`vectra_restore_drill_success`, duración y LSN alcanzado)?

A) **Pushgateway** en `vectra-observability` (1 réplica, sin persistencia, prioridad `vectra-normal`).
   - **F87**: `restore-drill` → Pushgateway, puerto 9091, egress desde `vectra-restore-drill`.
   - **F88**: Prometheus → Pushgateway, puerto 9091, scrape con `honor_labels`.
   - Se agrega al inventario de componentes de U1.

   Las alertas `RestoreDrillFailed` y `RestoreDrillMissing` usan la métrica empujada y su timestamp (`push_time_seconds`) (recomendado: es el patrón estándar para métricas de jobs batch y conserva las tres métricas de P-U1-05)

B) **kube-state-metrics**, sin flujo desde el namespace:
   - el éxito o fallo sale del estado del Job (`kube_job_status_succeeded`/`failed`), porque el job termina con error si `verify_chain` no da «íntegra»;
   - se elimina F87 y se agrega kube-state-metrics con su binding K14;
   - se pierden el LSN alcanzado y la duración precisa.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte C — Resolución (Q1 = A)

- [x] F87 redefinido: `restore-drill` → Pushgateway, 9091, egress desde `vectra-restore-drill`
- [x] F88 nuevo: Prometheus → Pushgateway, 9091
- [x] Puerto 9091 en §0 de `component-dependency.md`; rangos F80–F88 / F01–F88 actualizados (`component-dependency.md`, `unit-of-work.md`, `application-design.md`, `infrastructure-design.md`)
- [x] Pushgateway en INF-U1-07 y en el inventario de `logical-components.md` (con diagrama y texto)
- [x] P-U1-05: NetworkPolicies (F75 + F87), push de métricas y `RestoreDrillMissing` sobre `push_time_seconds`
- [x] INF-U1-06: fila de `vectra-restore-drill` con F75, F87 y F80, con su dirección
