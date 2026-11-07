# Ronda 1 — U02-T17

VEREDICTO: NO-VERDE

Los cinco criterios pasan en mis propias corridas. Las pruebas nuevas de B12, B13 y B14 caen con todas las mutaciones que quitan cada parte, y las etiquetas de B14 salen del código pinneado. Queda en pie un NARANJA: el runbook `rate-limit-backend-down` da a entender que la alerta por ausencia cubre la falta de un solo StatefulSet de Valkey, y promtool muestra que no.

Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T17` en `f211f2a`. Hash de la tarea `51f9db01…` (coincide). Al terminar, `git status --short` sale vacío: el worktree queda limpio.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | promtool check + test | `promtool check rules … && promtool test rules identity-edge/observability/rules/tests/*.yaml` | pasa: 12 reglas, 5 archivos SUCCESS, rc=0, 17 s |
| 2 | runbooks | `test_runbooks.py --root identity-edge` y `--operational` | pasa: 24 y 11, rc=0 |
| 3 | pytest de reglas | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 103 passed en 28.8 s (el tiempo lo explican 3 traducciones con `egctl`) |
| 4 | U2 | `uv sync --frozen && make -C identity-edge check` | pasa: 2671 passed en 18 min 30 s, rc=0. Ninguna omitida: las 17 apariciones de «skip» son contadores en 0 o flags de helm |
| 5 | U1, en serie después de CA-4 | `make -C platform check-local` | pasa: 272 archivos Markdown sin enlaces rotos, rc=0 |

**Evidencia del codificador.** Su CA-4 terminó a las 11:18 y duró 23 min, así que empezó hacia las 10:55. La última edición de código es de las 10:53 y el commit, de las 11:23 (solo la bitácora). Esa evidencia puede venir del diff actual. Los logs del rojo existen en `U02-T17-r1-cod/`.

**Mutaciones de promtool** sobre una copia de las reglas (16 en total): las 16 hacen fallar la suite.
- B12, en las dos alertas: sin rama nueva, sin `increase`, sin `unless` y sin `> 0`.
- B13: sin `absent` del Deployment, del StatefulSet y de cada `*Stale`.
- B14: sin filtro de listener o de cluster, el cluster con `ratelimit_cluster` o con los de JWKS, y el listener con `eg-stats-http` o con `eg-ready-http`.

**Mutaciones de `rule_problems`**: 15 de 17 dan error. Las dos que pasan se ven en F-02.

**Etiquetas de B14**, descargadas con `gh api` en los tags y comprobadas línea por línea. Todo coincide con la bitácora:
- `shared_types.go:30`: Envoy v1.39.5, con el mismo digest.
- `well_known_names.h:91,95` y `.cc:149,163`: los tags `envoy.cluster_name` y `envoy.http_conn_manager_prefix`.
- `prometheus_stats.cc:908`: `formattedTags` → `sanitizeNameInPlace`, que cambia el punto por `_`.
- `listener.go:561-571`: `hcmStatPrefix`.
- `gatewayapi/listener.go:1432-1454`, `translator.go:51-55` y `envoyproxy_helpers.go:61-73`: el puerto 443 pasa a 10443.
- `bootstrap.yaml.tpl:20-21,129,189,302`: los `stats_tags` propios son solo de zona, socket y prioridad, y no tocan estas etiquetas.
- `listener_ready.go:41`, `helpers.go:564-566` y `ratelimit.go:1036-1038`: `eg-ready-http`, los clusters `httproute/…` y `ratelimit_cluster`.

`gateway_facts()` corrido por mí da `https-10443` en kind, staging y prod. Da 9 clusters `httproute/vectra-edge/…`, y como ajenos `ratelimit_cluster`, los `securitypolicy/…/jwt/0`, `tracing`, `xds_cluster` y `prometheus_stats`.

**Casos cambiados en `identity-edge-rules-test.yaml`.** Dos casos pasaron de «no dispara» a «dispara»: `RoleConflict` (`0 0 0 1 1…` a 4m) y `LdapUnavailable` (`0+1x4 4x20` a 3m). Solo probaban que el `for` de 5m retenía la alerta, y B12 fija ahora `for` 0m. La tabla enmendada lo exige. El `for` sigue comprobado contra el diseño en `rule_problems`, y los casos de contador quieto (`3x30`, `4x20`) siguen en «no dispara».

A los casos viejos de `RateLimitBackendDown` se les agregaron las series sanas de los otros componentes. Hacía falta, porque con `absent()` las ausentes darían alertas extra, y sus `exp_labels` siguen siendo exactos. A los de `GatewayHighLatency` solo se les agregaron las etiquetas del filtro. Nada de esto los debilita.

**Etiquetas de la alerta por `absent()`, según promtool** (que compara `exp_labels` exactos):
- Deployment: `namespace` y `deployment`.
- StatefulSet: solo `namespace`.
- Las dos `*Stale`: solo `job`.

Lo que dicen de esto `realm-drift`, `signing-key-rotation` y `rate-limit-backend-down` coincide. El matiz que no coincide va en F-01.

## Hallazgos
### F-01 · NARANJA · identity-edge/runbooks/rate-limit-backend-down.md:9-10 · El runbook sugiere que la falta de un solo StatefulSet de Valkey dispara la alerta
El runbook dice que kube-state-metrics «dejó de exponer … la `kube_statefulset_status_replicas_available` del StatefulSet de Valkey» y que «la alerta de Valkey no dice cuál StatefulSet falta: mira ambos (`valkey-a` y `valkey-b`)».

Hay dos StatefulSets (`valkey-a` y `valkey-b`, en `charts/valkey`). `absent(…{statefulset=~"valkey-.+"})` solo dispara si no queda **ninguno**. Lo probé con promtool: con `valkey-a` presente y sin `valkey-b`, `RateLimitBackendDown` da `exp_alerts: []` y SUCCESS a 10m (`U02-T17-r1-rev-probe-valkey-b.log`).

La tarea pide que el runbook diga qué significa la alerta por ausencia. Hoy le hace creer al operador que la pérdida de una sola serie está cubierta. Debe decir que la rama por ausencia de Valkey dispara solo si faltan las series de los dos StatefulSets.

### F-02 · AMARILLO · identity-edge/tests/unit/test_alert_rules.py `hardening_problems` · La comprobación de B12 y B13 busca subcadenas y no ve el operador
Cambiar `or` por `and` entre `increase` y la rama nueva de `RoleConflict`, o antes del `absent` de `RealmDriftStale`, pasa `rule_problems` sin error. Las dos mutaciones las atrapa promtool (14 y 8 fallos), así que la defensa conjunta aguanta. No bloquea.

### F-03 · AMARILLO · identity-edge-rules-b12-b14-test.yaml:159 · Comentario engañoso
El comentario dice «el contador quieto … no dispara», pero el caso `7x40` espera disparo a 2m, por el límite aceptado de serie nueva. Conviene separarlo o renombrarlo.

## Tareas candidatas (defectos reales fuera de alcance)
- **Valkey: si desaparece un solo StatefulSet, ninguna alerta avisa.** Ni la rama `sum(…) == 0` ni la rama `absent` cubren la pérdida de `valkey-b` si queda `valkey-a`, y con él desaparece también su `redis_up`. Hace falta una decisión de diseño: un `absent` por StatefulSet, o un conteo de series menor que el esperado.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T17-r1-rev/`:
- `U02-T17-r1-rev-ca1.log`
- `U02-T17-r1-rev-ca2.log`
- `U02-T17-r1-rev-ca3.log`
- `U02-T17-r1-rev-ca4.log`
- `U02-T17-r1-rev-ca5.log`
- `U02-T17-r1-rev-promtool-mut.log`
- `U02-T17-r1-rev-pytest-mut.log`
- `U02-T17-r1-rev-facts.log`
- `U02-T17-r1-rev-probe-valkey-b.log`
- `src/` (el código pinneado de Envoy Gateway v1.9.3 y Envoy v1.39.5)

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/runbooks/rate-limit-backend-down.md:9-10|El runbook sugiere que la falta de un solo StatefulSet de Valkey dispara la alerta
INFORME: revisiones/U02-T17/ronda-1.md
```
