# Ronda 1 — U02-T11

VEREDICTO: NO-VERDE

Revisé 54d76a3 contra la base 1cd6bfd (`main`). El hash de la tarea es 824cecf9520a31e475415bd99c8fc8acbd9ce573, el esperado. Corrí CA-1 a CA-5 desde `vectra-risk/`, uno detrás de otro y CA-4 antes que CA-5. Los cinco terminan en 0 y no hay pruebas omitidas. Al terminar, el worktree está limpio (`git status --short` vacío) y sigue en 54d76a3. Bloquea un solo hallazgo NARANJA: valores sin fuente en el diseño que el codificador no reportó.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Descriptores | `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py -q` | pasa: 34 pruebas en 31,7 s, con `egctl` real en los tres entornos. Hay casos que alteran un límite o quitan una regla de una copia de `generated/` |
| 2 | `envoy-ratelimit` | `make -C identity-edge render-envoy-gateway policy-ratelimit && uv run pytest …test_envoy_gateway_values.py …test_ratelimit_deployment.py -q` | pasa: conftest 1720/1720 y 1/1 (`--combine`); pytest 135 pruebas en 47,7 s |
| 3 | Chart de Valkey | `make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && uv run pytest …test_valkey_chart.py -q` | pasa: conftest 2592/2592 y 9/9 por entorno; kyverno `pass: 40, fail: 0` en los tres entornos; pytest 109 pruebas en 19,5 s |
| 4 | K11 | `make -C platform check-local` | pasa: 622 pruebas en 156 s y «221 archivos Markdown sin enlaces rotos» |
| 5 | Regresión | `uv sync --frozen && make -C identity-edge check` | pasa: 2297 pruebas en 813 s, sin omitidas ni deseleccionadas. Incluye `policy-ratelimit`, `check-valkey-rendered`, `policy-valkey` y `policy-valkey-u1` |

Transcripciones en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca1.log` a `ca5.log`, en ese mismo directorio.

## Hallazgos

### F-01 · NARANJA · `identity-edge/charts/valkey/values/{staging,prod}.yaml` y `values.yaml:43-45` · valores sin fuente en el diseño, sin reportar y fuera del oráculo
Es una clase de hallazgo; estas son todas las apariciones que encontré:
- **Zonas de staging y prod.** Valen `zone-a` y `zone-b`. El diseño solo fija las de kind: INF-U2-04 dice «`zone-a` y `zone-b` en kind; las zonas de cada entorno van en los values». U1 tampoco da nombres de zona para el banco. La `nodeAffinity` es obligatoria, así que con un nombre que no coincida los cuatro StatefulSets se quedan en Pending. Entonces el rate limit queda abierto (`failClosed: false`) y `/auth/**` responde 503.
  - La prueba mira la zona solo en kind: `test_valkey_chart.py:143` dice `... and env == "kind"`.
  - Lo comprobé en una copia: puse `banco-z1` y `banco-z2` en `values/prod.yaml` y volví a renderizar. `check-valkey-rendered`, `policy-valkey` y `policy-valkey-u1` terminan en 0, y `test_valkey_chart.py` da `109 passed`. Nada lo detecta.
- **Tiempos de Sentinel.** `downAfterMilliseconds: 5000`, `failoverTimeout: 60000` y `parallel-syncs 1` (este último es el default de Valkey). No están en INF-U2-04, NFR-U2 ni P-U2-04; ningún grep los encuentra en `aidlc-docs/construction/identity-edge/`. Deciden cuánto dura el 503 de una conmutación, y ni el oráculo ni conftest los fijan.
- La tarea manda: «falta un dato → detente y repórtalo». La bitácora no menciona ninguno de estos valores. Hay dos salidas: que el orquestador fije los valores en el diseño y el oráculo los lea de ahí, o que la bitácora los registre como un dato faltante que tiene que decidir el usuario.

### F-02 · AMARILLO · `bitacoras/U02-T11.md:57-78` · el rojo se escribió después del código, pero se reprodujo
Reproduje el rojo declarado en una copia (`git archive 54d76a3`), con los archivos de la base:
- K11 de 1cd6bfd: `3 failed, 77 deselected`.
- `envoy-gateway*.yaml` de 1cd6bfd: `89 failed, 46 passed`. Son las mismas cifras de la bitácora.

Para el chart no hay un rojo de verdad. Lo sustituyen las pruebas de mutación: cada regla de conftest tiene un caso que falla, y `test_every_conftest_rule_has_a_failing_case` lo comprueba. El defecto de `hardening` que esos casos destaparon (`!=` indefinido en Rego) muestra que muerden. Mi juicio: la evidencia basta para este diff. La desviación del plan está declarada, y no bloquea.

### F-03 · AMARILLO · `platform/tests/test_integration.py:202-210` · el cambio es correcto y mínimo, pero ata U1 al render de U2
- **Es necesario.** Con los values nuevos y la prueba de la base, falla con `AssertionError: ('envoy-gateway.yaml', ('vectra-edge', 'sentinel-a'))`.
- **Sigue mordiendo.** Con el cambio y el puerto de `sentinel-b-1` alterado a 26380, falla con `('vectra-edge', 'sentinel-b'), '26380', {26379}`.
- **Alcance.** La tarea admite «las pruebas de U1 que fijan esas listas». Lo acepto. El orquestador debería ratificarlo, porque la lista es de Services, no de namespaces.
- **Pendiente.** Lee solo `rendered/prod`. La candidata del codificador (quitarlo en el Paso 12) es la correcta.

### F-04 · AMARILLO · `templates/valkey.yaml:76` y `templates/sentinel.yaml` · los pods de Valkey y Sentinel llevan la credencial de Sentinel de `envoy-ratelimit`
`REDISCLI_AUTH` sale de `sentinel-lookup-password`, que es `{{ .sentinelRatelimit }}`. Con las listas de R5 es el único usuario que tiene `+sentinel|master`, así que hace falta para «al reiniciar, cada nodo pregunta a Sentinel». Aun así, el diseño no lo dice y la bitácora no lo menciona. Que lo ratifique el orquestador.

### F-05 · AMARILLO · `bitacoras/U02-T11.md:112` · la candidata de `readOnlyRootFilesystem` y `RUNTIME_ROOT` no aplica
En `ratelimit` `5ae0682e`, `src/server/server_impl.go:147-153` solo usa el directorio de runtime con `CONFIG_TYPE=FILE`. v1.9.3 fija `GRPC_XDS_SOTW`. No hace falta comprobarlo en vivo.

### Lo comprobado sin hallazgo
- **K11.** `vectra-risk-gitops/apps/{kind,staging,prod}/secret-store.yaml` incluyen `eso-rbac-k11.yaml`. `-kind` y `-staging` solo agregan `vectra-mock`, y van por `secret-store-env` (`components.yaml:38`). Los AppProject de los tres entornos admiten `envoy-gateway-system`. Basta cambiar el archivo común, y la prueba nueva lee el `include` de verdad.
- **ACL contra R5.**
  - `users.acl`, `sentinel-users.conf` y `sentinel-auth.conf` coinciden línea por línea con INF-U2-04 «ACL definitivas».
  - El master es `ratelimit`, y las propiedades de `edge/valkey` son las seis.
  - Contrasté las listas con `sentinel.c` 8.1.11:
    - comandos que Sentinel envía: AUTH, CLIENT, CONFIG, EXEC, INFO, MULTI, PING, PUBLISH, SCRIPT, SENTINEL, SLAVEOF y SUBSCRIBE;
    - a los pares no envía INFO (línea 3005);
    - usa `is-master-down-by-addr` (4535).
  - `sentinel-user` y `sentinel-pass` se aplican antes de `monitor`, y `auth-user` y `auth-pass` después.
- **Envoy Gateway v1.9.3**, contra el código del tag con `gh api`:
  - `RateLimit`, `RateLimitTracing.SamplingRate *uint32`, `RateLimitRedisSettings.URL`, `FailClosed`, `RateLimitDeployment`, `RateLimitHpa`, `RateLimitPDB` y `KubernetesDeploymentSpec.Patch` existen;
  - `KubernetesPodSpec` tiene `Labels`, `PriorityClassName` y `TopologySpreadConstraints`;
  - los puertos 8081, 8080, 19001 y 18001 y `rateLimitLabels()` coinciden con `resource.go`;
  - `OTEL_EXPORTER_OTLP_ENDPOINT` y la sustitución de env por nombre coinciden con el modelo.
- **Literales en Rego.** Los de `ratelimit.rego` y `valkey.rego` son la política misma y cada uno tiene su caso que falla. No los cuento como hallazgo.

## Tareas candidatas (defectos reales fuera de alcance)
- **El tracing de `envoy-ratelimit` no llegaría al colector.** `ratelimit` `5ae0682e` usa `TRACING_EXPORTER_PROTOCOL` con default `"http"` (`src/settings/settings.go:316`). v1.9.3 pone `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector…:4317`, y el 4317 es OTLP gRPC. El defecto está en el diseño (INF-U2-03 fija el 4317), no en el diff. Hay dos arreglos: `TRACING_EXPORTER_PROTOCOL=grpc` en `container.env`, o el puerto 4318. Lo decide el usuario antes del Paso 16.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/all.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca1.log` a `ca5.log`
- Copia de las reproducciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/copy/vectra-risk`

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/charts/valkey/values/{staging,prod}.yaml y values.yaml:43-45|zonas del banco y tiempos de Sentinel sin fuente en el diseño, sin reportar y fuera del oráculo
INFORME: revisiones/U02-T11/ronda-1.md
```
