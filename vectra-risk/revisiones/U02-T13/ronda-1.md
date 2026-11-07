# Ronda 1 — U02-T13

VEREDICTO: NO-VERDE

Los seis criterios pasan con mis propias ejecuciones. Quedan en pie dos hallazgos NARANJA, ninguno ROJO: un falso SEV1 de `BreakGlassLogin` y varios casos de promtool que no detectan las mutaciones. El worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T13` quedó limpio (`git status --short` vacío antes y después). No corrí nada contra un clúster ni contra Docker, y no toqué procesos ajenos.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`, HEAD 4f6a88b)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Reglas válidas; cada alerta dispara y no dispara | `promtool check rules … && promtool test rules identity-edge/observability/rules/tests/*.yaml` | pasa: `SUCCESS: 11 rules found`, SUCCESS en los dos archivos (exit 0) |
| 2 | Runbooks | `test_runbooks.py --root identity-edge && … --operational` | pasa: «22 alertas con su runbook en regla» y «10 runbooks operativos» (exit 0). Son 22 porque cuenta el archivo de grupos y el CR, igual que U1 (28 → 56) |
| 3 | Reglas = diseño, cada métrica con fuente | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 66 passed en 3.6 s, todo lectura de archivos, sin estado externo |
| 4 | La imagen activa las métricas de eventos | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 92 passed en 0.18 s (solo parsea el Dockerfile) |
| 5 | `check` de U2 con `rules` y `runbooks` | `uv sync --frozen && make -C identity-edge check` | pasa: 2464 passed en 26:04, sin omitidas, exit 0 |
| 6 | U1 sigue cumpliendo (en serie, después de CA-5) | `make -C platform check-local` | pasa: exit 0 (3m16s) |

## Comprobaciones contra el código de los tags (`gh api`)
- **Keycloak 26.8.1, métrica y etiquetas**:
  - el contador es `keycloak.user` con `baseUnit(EVENTS)`, que Prometheus expone como `keycloak_user_events_total`;
  - la etiqueta `client.id` sale como `client_id`;
  - `format()` quita `_ERROR` y pasa a minúsculas (`LOGIN` y `LOGIN_ERROR` son ambos `login`);
  - `error` va vacío si no hay error, y Prometheus trata la etiqueta vacía como ausente, así que `error=""` y `error!=""` funcionan;
  - el listener es global (`isGlobal()`), no hay que activarlo por realm;
  - `event-metrics-user-tags` es de ejecución.
- **Opciones de Keycloak en los renders**: `KC_EVENT_METRICS_USER_TAGS=realm,clientId` está en el contenedor `keycloak` de los tres renders, con `start --optimized`. El build solo lleva `--event-metrics-user-enabled=true`.
- **Puerto de gestión de Keycloak**: hereda el TLS y el `/auth` (`ManagementPropertyMappers.java` 67-68 y 94). El monitor usa `http-internal` 9000, HTTPS y `/auth/metrics`. El Secret `identity-ca/ca.crt` existe en `vectra-identity`, y `serverName` coincide con un dnsName del certificado.
- **Envoy Gateway v1.9.3**:
  - data plane: puerto `metrics` = `EnvoyStatsPort` (`resource.go:92-93`) y `/stats/prometheus` (`bootstrap.yaml.tpl:145`); modo `GatewayNamespace`, pods en `vectra-edge`; Prometheus no está apagado en los EnvoyProxy;
  - `envoy-ratelimit`: puerto `metrics` 19001; `enablePrometheus` es true por defecto y la config no lo apaga; la ruta por defecto de ratelimit 5ae0682e es `/metrics`.
- **Otros exporters**: `redis_up` existe en redis_exporter v1.95.0 (`exporter.go:782`). `kube_statefulset_status_replicas_{ready,available}` y `kube_deployment_status_replicas_available` existen en KSM v2.20.0, el de kube-prometheus-stack 92.17.0.
- **Prometheus de U1**: `*SelectorNilUsesHelmValues: false` y `podMonitorNamespaceSelector: {}`, así que recoge los 4 PodMonitor. Selectores, namespaces y puertos coinciden con los pods reales (Valkey `metrics` 9121 en `valkey-a/b`), y F60 abre 9000, 19001 y 9121.
- **Arbitrajes**:
  - `error=""`: correcto, por `format()`;
  - borrar `valkey-b-0` en el failback: correcto. El ACL `ratelimit` de Sentinel no tiene `+sentinel|failover`, `replica-priority` es A=10 y B=100, y el contenedor `sentinel` lleva `REDISCLI_AUTH`, así que los `valkey-cli --user ratelimit` del runbook funcionan;
  - `fixed_env` en `keycloak.rego`: correcto y necesario. Lo comprobé con una mutación: con el render en `value: realm`, conftest da `FAIL env-whitelist: KC_EVENT_METRICS_USER_TAGS debe valer realm,clientId`;
  - la rama de primera muestra: necesaria, pero con un defecto (F-01).

## Hallazgos

### F-01 · NARANJA · identity-edge/observability/rules/identity-edge-rules.yaml (`BreakGlassLogin`) · Falso SEV1 tras un hueco de scrape de más de 5 min
La rama `X > 0 unless X offset 5m` toma por nueva cualquier serie que vuelve después de quedar stale. Si Keycloak sigue vivo pero no se raspa durante más de unos 5 min (reinicio o reprogramación de Prometheus, cambio de NetworkPolicy, fallo del TLS del 9000), al volver salta un SEV1 por un login antiguo, sin que haya ningún login nuevo.

Lo comprobé con promtool sobre una copia y la serie `'1x5 stale _x8 1x10'` (eval 16m, sin ningún incremento). Resultado: `FAILED … got: BreakGlassLogin{client_id="security-admin-console",…,severity="SEV1"}`.

El arbitraje aprobó la rama, pero no este modo de fallo. Además, el runbook `break-glass-login.md` no lo menciona. Hay que acotar la rama a que el target se haya raspado sin hueco (por ejemplo, con `up{job="keycloak"}` y la cuenta de muestras de la ventana), o, si el orquestador lo acepta como riesgo, documentarlo en el diseño y en el runbook.

### F-02 · NARANJA · identity-edge/observability/rules/tests/*.yaml · Casos de promtool que no detectan las mutaciones
Hice 30 mutaciones de la regla sobre una copia (`scratchpad/scripts/mut.py`). Sobreviven a promtool:
- **`for` de `KeycloakDown` y de `RateLimitBackendDown`** (quitarlo, o pasar a 4m en RateLimit). Los casos `'1 1 0 1 1 1'` (eval 4m) y `'1 1 0 0 1 1 1 1'` (eval 5m) se evalúan después de que la serie se recupera, así que no prueban «antes de cumplir el `for`».
- **Ventanas**: `RoleConflict [15m]→[5m]` y `LdapUnavailable [5m]→[15m]`.
- **`GatewayHighLatency` `> 5` → `> 20` o `> 0`**. El caso de no-disparo tiene una diferencia de 0 y el que dispara una de unos 23 ms. Falta un caso cerca del umbral.
- **`BreakGlassLogin` con `realm="vectra"` en la rama de `increase`**. El caso de «otro realm» lo cubre la rama de primera muestra.
- **Bordes de los stale**: `RealmDriftStale` a 25h y `SigningKeyAgeStale` a 2h, porque el no-disparo cae justo en el borde estricto.

`test_alert_rules.py` sí detecta los literales (umbral, `for`, ventana). Pero el CA-1 y P-U2-09 piden que promtool demuestre el disparo y el no-disparo, y estos casos no discriminan. Sí detecta las demás: los umbrales de AuthDenied, SigningAge, `error=""` y `error!=""`, la rama de primera muestra, `client_id`, la rama de redis, el `sum` de Valkey, la severidad y los `for` de AuthDenied, RoleConflict, Ldap, Gateway y SigningAge.

### F-03 · AMARILLO · tests (barrido de clase) · Literales de valores que fija el diseño en pytest
- `test_alert_rules.py`: 180-185 (20, 5, 80 días, 26h, 3h, SEV1/0m, `security-admin-console`), 370, 374, 446 (`{"metrics": 19001}` inyectado en el «pod real» del data plane: el puerto del modelo es inventado) y 513.
- `test_keycloak_deploy.py`: `value.split(",") == ["realm","clientId"]`.
- `test_keycloak_image.py`: la lista de `OPTIONS`.

Son controles del parser: las comprobaciones de fondo sí leen el diseño, y siguen una convención anterior. Aun así contradicen la nota de la tarea.

### F-04 · AMARILLO · CANDIDATAS.md · Candidata obsoleta
La entrada «`BreakGlassLogin` escribe `error=""`… Confirmar con el usuario» ya está resuelta: el orquestador la dio por buena y está en el diseño corregido de B10.

### F-05 · AMARILLO · `GatewayHighLatency` · Sin filtro por listener ni cluster
El `sum by (le)` mezcla el listener de stats/readiness y los clusters de ratelimit y OTel. La aproximación es la que fija el diseño, pero conviene acotarla.

## Tareas candidatas (defectos reales fuera de alcance)
- Revisar la rama de primera muestra de `BreakGlassLogin` en el diseño (P-U2-09 B10) para tener en cuenta los huecos de scrape (F-01), si el orquestador decide que el arreglo no entra en esta tarea.
- Leer el puerto del data plane (19001) de una fuente versionada en lugar de inyectarlo en el modelo de `test_data_plane_policies`.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca5.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca6.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/scripts/mut.py (mutaciones de promtool; resultado en /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/tasks/b0ygvn0ch.output)

No escribí `revisiones/U02-T13/ronda-1.md` porque mis herramientas son de solo lectura sobre el repositorio. El texto de arriba es el informe para que el orquestador lo registre.

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/observability/rules/identity-edge-rules.yaml (BreakGlassLogin)|falso SEV1 tras un hueco de scrape de más de 5 min en la rama de primera muestra
NARANJA|identity-edge/observability/rules/tests/*.yaml|casos de promtool que no detectan mutaciones de for, ventana y umbral
INFORME: revisiones/U02-T13/ronda-1.md
```
