# Ronda 1 — U08-T05

VEREDICTO: VERDE (con RL-2: no hay ningún ROJO. Quedan dos NARANJA y varios AMARILLO, todos fuera del alcance de esta tarea, para `CANDIDATAS.md`)

Revisé el SHA e4558c1 contra la base 5c91bbb. El hash de la tarea coincide (b4eebafd…). Al terminar, `git status --short` está vacío y HEAD sigue en e4558c1. No toqué ni el árbol principal ni otros worktrees. No hay contenedores míos en pie: el `testcontainers-ryuk` que aparece se creó después de mis corridas y es de otro agente. Dejé las imágenes `:dev` que reconstruí. Las transcripciones están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Imágenes | Las órdenes de CA-1 | pasa: `hadolint` rc 0; `65532:65532` en las dos, con su `Cmd`; `OK` ×2; `OK-entradas`; `OK-migraciones`; `True`; `rc=1`; 2/2 y 2/2; import-linter `5 kept, 0 broken`; `mismo commit` 1 |
| 2 | Render, kubeconform y conftest | `make … policy-chart` | pasa: Valid 22/22/16 e Invalid 0; conftest 2024/2024/1472 y `chart_set` 21 ×3 |
| 3 | Variables, base, identidad y rt5 | Extras de CA-3 y `helm template` de Argo con `probes.runId` | pasa: 2 líneas del realm, `OK-boveda`, 3 `roleConsumers`, 1 Job y ningún `ttlSecondsAfterFinished`; un `runId=manual` no rinde |
| 4 | Contenedores reales | `make … test-image` (carga 4,88) y una segunda corrida con `-s` | pasa: 13 pasan en 31 s. `case-service` sale con 0 en 0,8 s (gracia de 20 s); `case-worker` con 0 en 0,8 s (gracia de 40 s). En reposo, 62 MiB y 61 MiB |
| 5 | Admisión de U1 | `make … policy-chart-u1`; diff de `platform/policies` y `platform/network` | pasa: Kyverno pass 38/38/28 y fail 0; rego 154/154/112; `hpa` 3 ×3; `kyverno test` 81/81; diff vacío |
| 6 | Cuota y flujos | `make … quota-flows` y las greps de CA-6 | pasa: X01 = 2, ningún flujo «falta» |
| 7 | Values por entorno | `policy-chart` (values.prod y values.staging), greps de `runId` y `schedule` | pasa |
| 8 | `CoreWriteAttempt` | `make … rules` y `runbooks` | pasa: `SUCCESS`; `test_rules` incluido en `test`; un solo runbook; la alerta no aparece en el render de prod |
| 9 | OpenAPI y documentación | `check_openapi.py` y greps de `api.md` | pasa: rc 0, ningún «falta», no existe `retention.md` |
| 10 | Application | `generate.py --check`, `test_waves.py`, `kyverno apply` ×3, greps | pasa: wave `'5'` ×3; sin `automated`; `values-kind` 1/0/0; 0 Applications del mock en prod; 2 líneas en el diff de `test_platform.py` |
| 11 | Trazabilidad | `--unit case-management --all`, `--all` y el bucle de las BR | pasa: 52 identificadores; 0 líneas «U8-»; ninguna BR «sin prueba»; la última grep da rc=1 |
| 12 | Memoria de kind | Medí quitando la Application y con ella | pasa: base 10,3438 → 11,0859 (diferencia 0,7421, el esperado 0,7422 por redondeo: 760 MiB); `test_kind_profile` 6 pasan |
| 13 | Frontera del TTL | `-k ttl`; mutación `<=` → `<` en la línea 77 de `governance_client.py` | pasa, y con la mutación cae (1 falla). El diff de `src` está vacío |
| 14 | `make -C case-management check` | Una corrida completa (carga 8,18 → 6,11; 13 min 54 s) | **falló una vez** en `test`, por un PBT inestable de U08-T04 (F-01). Pasa al repetir el test, y el resto de objetivos pasa (2 min, rc 0). Cobertura 97 % y 100 % en los 8 módulos |
| 15 | `make check` de todas las unidades | No lo repetí, por instrucción | sin verificar por mí |
| 16 | Plan | Las dos órdenes del diff | pasa: 16 y 24 en `[ ]` con su nota; los demás en `[x]`; 18 líneas |

**Mutaciones propias**, las cuatro cayeron:
- M1, sin `CASE_SCORING_URL` en el worker: falla conftest en los 3 entornos y falla `test_chart`.
- M2, el worker con `pg-role-case-app`: el conftest por documento no lo ve, pero sí `chart_set` (`--combine`). Además fallan 7 casos (`dsn_*`, `as_is`, `rt5`).
- M3, gracia del worker en 30: cae `test_probes_the_termination_grace…` ×3. El conftest con 30 pasa, como pide la tarea (≥ 30).
- M4, `coreMock.enabled: true` en prod: falla `values.prod` (`prod-switches`), el render de prod trae 5 recursos en `vectra-mock` y fallan 6 casos.

**Prioridad 1, kind:**
- Cada variable que leen `Settings.from_env`, `WorkerSettings.from_env`, `migrations/env.py`, `authn.py`, `service_token.py` y `deps.py` está en el render que usa Argo CD.
- `CASE_ALLOW_TEST_SCENARIOS` vale `"true"` en kind (por `values/kind`) y `false` en prod. `core` y `coreMock` son verdaderos en kind y falsos en prod.
- Las URL `governance-service`, `decision-registry-service` y `scoring-service` :8080 coinciden con los Service de `main`. El mock es `core-banking-mock.vectra-mock`:8080. F15, F16, F17, F40 y F104 tienen los orígenes correctos.
- `pg-role-case-{app,worker,migrator}` son ExternalSecret de U1 en `vectra-app`, con las claves `username` y `password`, y ningún rol está cruzado.
- El DSN usa `verify-full` y su `sslrootcert` apunta a `/etc/vectra/ca/ca.crt`, que el chart monta desde el ConfigMap `vectra-internal-ca`. Ese ConfigMap llega a `vectra-app` y a `vectra-mock` porque ambos tienen `vectra.io/mesh: enabled`.
- `postgres-server-tls` tiene `dnsNames: *.vectra-data.svc.cluster.local` y lo firma el ClusterIssuer `vectra-internal-ca`. Leyendo los manifiestos, cubre `case-db-rw.vectra-data.svc.cluster.local`; la conexión real solo se puede comprobar en el clúster.
- El Job de migración es un hook `Sync` en la wave 1, con la SA `migration-case`, la etiqueta `vectra.io/workload: migration-case` y `alembic -c /app/alembic.ini upgrade head`. `test_image` lo corre de verdad contra Testcontainers, pero con `sslmode=disable` (lo anota).

**Prioridad 3, D3:**
- El Job `rt5-demo` lleva `app.kubernetes.io/name: case-service`, no lleva `vectra.io/workload`, y usa la SA `case-service`.
- El Service y el PDB seleccionan las dos etiquetas, así que no le mandan tráfico.
- Las NetworkPolicy de U1 seleccionan por `app.kubernetes.io/name`, así que el Job llega al mock.
- Kyverno estático y el rego de U1 sobre el render con el Job: pass 46 y fail 0; 161/161.
- `medium` en el mock no afecta la prioridad ni la cuota. La cuota no depende de la etiqueta y `priorityClassName` sigue en `vectra-low`. Solo lo lee `require-criticality-label`, que admite `critical`, `high` y `medium`.

**Prioridad 4, D1:** la regla es `max(vectra_cases_failclosed_persistent) > 0`, sin etiquetas. La métrica existe en `vectra_case/metrics.py:55` y `test_image` la ve en `/metrics`.

**Prioridad 5:** kind difiere de staging solo en el request de memoria (128 frente a 256 MiB ×2) y en el registro.

## Hallazgos
### F-01 · NARANJA · case-management/tests/property/test_evaluation.py:105 · PBT-U8-05 inestable (de U08-T04, fuera del diff)
Mi corrida completa de `make check` terminó con `1 failed, 669 passed` y RC=2. El contraejemplo fue `free_text='3'` y `socioeconomic_stratum='3'`. La aserción `value != text` compara contra la etiqueta legítima `.monitoring_labels.estrato`, sin el umbral `len(text) < 4` que sí se aplica a la subcadena.

Al repetirla con `HYPOTHESIS_PROFILE=ci … -k pbt_u8_05` pasan las 2. La semilla es aleatoria, así que el fallo es intermitente. El defecto está en el oráculo de la prueba, no en el código.

Va como candidata. Como no hay otra tarea de U8, el `make check` de U8 puede fallar al azar en RL-4 y en U12.

### F-02 · NARANJA (candidata de U1, afecta a D3) · platform/observability/monitors · nadie raspa el proxy de Linkerd
Ningún PodMonitor ni ServiceMonitor del repositorio raspa el puerto de administración del proxy (4191). Lo comprobé con `git grep -nE "4191|linkerd-admin|linkerd-viz|inbound_http_authz_deny" origin/main`, que no devuelve nada fuera de la documentación de U8. Sin ese raspado, `inbound_http_authz_deny_total{namespace="vectra-mock",…}` no existe en Prometheus. La rama de Linkerd de `CoreWriteAttempt` nunca dispara, y el oráculo de D3 («`CoreWriteAttempt` en Prometheus») fallaría.

El recorte (`demo-recorte-funcional.md` §1.3) atribuye esa serie a U1, así que no es de esta tarea. Sin clúster no lo puedo confirmar, y el cierre no lo lista en «Pendiente en U12».

### F-03 · NARANJA (candidata de U0, ya anotada por el codificador) · vectra_common.ops_server.run_service · arranque fallido con salida 0
Lo reproduje con `pytest test_image.py -s -k without_the_key`: «case-service sin llave (file-not-mounted): termina con codigo 0» y lo mismo con `variable-missing`.

En Kubernetes, un Deployment con `restartPolicy: Always` reinicia el contenedor sea cual sea el código, y la espera exponencial termina en `CrashLoopBackOff`. Pero `lastState.terminated` queda como `reason: Completed, exitCode: 0`, y el registro es un `level: error` sin mensaje: el diagnóstico apunta a «terminó bien». Con `maxUnavailable: 0`, el rollout se queda colgado sin que se vea la causa.

No rompe la demo si la llave existe, pero ante el fallo de `aud` (U00-T04) el síntoma en kind será justo este.

### F-04 · AMARILLO · case-management/tests/integration/test_image.py · C-1 sin el caso peor
El apagado se mide sin trabajo en vuelo (0,8 s). Los 40 s frente a los ≈ 34 s del peor caso se apoyan en las constantes, con una prueba de ≥ `WORKER_TERMINATION_GRACE`, no en una ejecución. Para C-1 basta como margen razonado; el `rollout restart` real queda en U12, como dice el cierre.

### F-05 · AMARILLO · chart/templates/case-*.yaml · sin `VECTRA_OTLP_ENDPOINT`
U7 lo inyecta y U8 no, así que U8 no emitirá trazas. La lista de variables de la tarea tampoco lo pide. Va como candidata.

### F-06 · AMARILLO · test_image.py:263 · `verify-full` y `sslrootcert` no se ejercen localmente
El DSN se cambia a `sslmode=disable`. Está anotado en el módulo y en «Pendiente en U12»; lo señalo solo para que quede explícito.

## Tareas candidatas (defectos reales fuera de alcance)
- U8: el oráculo de PBT-U8-05 compara `free_text` corto por igualdad con etiquetas legítimas (F-01).
- U1: un PodMonitor del proxy de Linkerd en `vectra-mock`, con la etiqueta `namespace`, para `inbound_http_authz_deny_total`. Bloquea la lectura de la alerta en D3 (F-02).
- U0: `run_service` debe salir con un código distinto de 0 y con mensaje cuando el arranque falla (F-03).
- U8: `VECTRA_OTLP_ENDPOINT` en el chart (F-05).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/check.log` (`make check` completo, el fallo de F-01)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/check2.log` (lint, imágenes, `test-image`, chart, admisión, cuota, reglas, runbooks, OpenAPI, enlaces y trazabilidad, rc 0)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/image-s.log` (apagados, memoria y salida 0 sin llave)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/static.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/ca2.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08/kind.yaml` (render de kind con los values de Argo CD y `probes.runId`)

```
VEREDICTO: VERDE
NARANJA|case-management/tests/property/test_evaluation.py:105|PBT-U8-05 inestable: make check de U8 falla al azar (fuera del diff, candidata)
NARANJA|platform/observability/monitors|Nadie raspa el proxy de Linkerd: la rama de CoreWriteAttempt de D3 no dispara (U1, candidata)
NARANJA|vectra_common.ops_server.run_service|case-service sale con 0 al fallar el arranque (U0, candidata)
AMARILLO|test_image.py|Apagado del worker con trabajo en vuelo no ejercido (C-1)
AMARILLO|chart/templates|Sin VECTRA_OTLP_ENDPOINT
AMARILLO|test_image.py:263|verify-full no ejercido localmente
INFORME: revisiones/U08-T05/ronda-1.md
```
