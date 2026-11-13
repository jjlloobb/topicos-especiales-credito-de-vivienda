# Ronda 1 — U01-T09

VEREDICTO: VERDE

Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t09`, HEAD `23f5c35`, base `da15a07` (= `origin/main` del worktree). El blob de la tarea es `945bd82dc8cef0a2542ac0621573144b756481a7` y coincide. Todas las mutaciones las deshice con `git checkout HEAD -- …`. Al terminar, `git status --short` sale vacío y HEAD sigue en `23f5c35`. No usé `git stash`, no toqué ningún clúster y corrí las suites una detrás de otra.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Hipótesis | las tres órdenes de CA-1 sobre `da15a07` | pasa: sin salida (rc=1), `0`, `0` |
| 2 | Rojo primero | `git checkout 256593f -- platform/observability platform/network platform/tests/test_proxy_metrics.py`, pytest y restauración | pasa: **17 failed, 15 passed**, rc=1. Los mensajes nombran `kind/CoreWriteAttempt`, `inbound_http_authz_deny_total`, `vectra-mock`, «falta el monitor» y «falta el flujo … 4191». Prod y etiquetas pasan |
| 3 | Verde | `uv run pytest platform/tests/test_proxy_metrics.py $PYT -v` | pasa: 32 passed en 51,8 s (carga 9,3). El tiempo no es sospechoso: hay renders reales de helm |
| 4 | Mutaciones | 10 mutaciones mías sobre los archivos reales (detalle abajo) | pasa: las 10 caen y el mensaje nombra entorno, alerta y métrica |
| 5 | Etiquetas con fuente | `-k labels`, y `grep` de la URL y de `2026.10.2` | pasa (con el matiz de F-01) |
| 6 | Cambio mínimo | `generate.py --check`, `grep -l 4191` y el filtro de nombres | pasa: rc 0. Seis archivos, todos de `kind/` o `staging/`. El filtro no deja nada |
| 7 | Cierres | `grep -n U01-T09` en los 4 documentos | pasa: `CANDIDATAS.md:622`, `cierre-demo.md:69`, `cierre-acotado.md:28`, `component-dependency.md:168` |
| 8 | `make check` de U1 | `check-local` con el `TMPDIR` por omisión; `check-tools` con `TMPDIR=platform/.tools/tmp` (ignorado) | pasa. `check-local`: 903 passed, rc 0, 12 min 41 s (carga de 7,6 a 21,3). `check-tools`: kyverno `pass: 450` y `pass: 54`, conftest 707+3+385, rc 0, 7 min 16 s (carga de 23 a 18,5) |

Otras comprobaciones:
- `test_links.py`: rc 0, 553 archivos.
- Alcance: `git diff da15a07..HEAD` no toca `generate.py`, `platform/mesh`, `case-management/` (salvo la línea de `cierre-demo.md`), reglas ni los values de kps.

### Mutaciones mías (logs `u01t09-mut-*.log`)
- **M1, sin el monitor:** «falta el monitor» en kind y en staging.
- **M2, `matchNames: [vectra-app]`:** cae igual que M1.
- **M3, `keep` sin `inbound_http_authz_.+`:** «los metricRelabelings de linkerd-proxy tiran …».
- **M4, `port: admin-http`:** «apunta a un puerto que el proxy no declara».
- **M5, selector `control-plane-ns: linkerd2`:** «falta el monitor (… los que alcanzan el namespace: ['linkerd-proxy'])».
- **M6, flujo sin 4191:** «falta el flujo … por el puerto 4191 en kind (F60)».
- **M7, flujo con `envs: [staging]`:** cae solo kind.
- **M8, NetworkPolicy generada sin 4191:** «kind no tiene NetworkPolicy de entrada en vectra-mock para el puerto 4191».
- **M9, vacuidad (la regla deja de leer el proxy):** `test_the_rules_that_read_the_proxy_are_discovered[kind]` falla.
- **M10, `route_name` cambiado por una etiqueta inventada:** «filtra por la etiqueta `rutita`, que la familia no trae».

La prueba **descubre** las reglas, no las lista. Por entorno ve 70 reglas en kind y staging y 69 en prod: identity-edge 12, platform-foundation 33, product-metrics 24 y case-management 1 (esta solo en kind y staging). La única regla que no ve es `governance-rules.yaml`, que no instala ningún componente.

## Lo pedido en las prioridades

**1. ¿Funcionaría en kind?** Lo leí en lo generado y en el código de cada pieza.
- **Monitor.**
  - El selector es `linkerd.io/control-plane-ns: linkerd`, la etiqueta que el inyector pone a todo pod mallado. El chart la usa en `templates/podmonitor.yaml:116`.
  - `matchNames: [vectra-mock]` es correcto, y `kube-prometheus-stack.yaml:26-30` toma monitores de cualquier namespace y sin filtro de etiquetas.
  - El puerto `linkerd-admin`=4191 está en `_proxy.tpl:259-262`. Con `nativeSidecar: true` el proxy es un init container.
  - **Prometheus descubre los puertos de los init containers:** `discovery/kubernetes/pod.go:397` hace `append(pod.Spec.Containers, pod.Spec.InitContainers...)` y emite `__meta_kubernetes_pod_container_init`.
  - prometheus-operator v0.94.2 (el `appVersion` del chart 92.17.0) filtra solo por `__meta_kubernetes_pod_container_port_name` (`promcfg.go:1591-1597`), sin descartar init containers. El path `/metrics` es el valor por omisión.
  - El `keep` va en `metricRelabelings`, que no afectan a `up` (es sintético). Ni el proxy ni nuestros relabelings ponen la etiqueta `namespace`: sale la del pod.
- **Red.** Comparé objeto a objeto lo generado antes y después (`scripts/cmpgen.py`).
  - kind: de 751 a 754 objetos; staging: de 730 a 733; prod: 713 sin cambios.
  - Hay tres objetos nuevos por entorno: el `Server metrics-4191`, `f60-metrics-4191-mtls` y la `AuthorizationPolicy` `f60-metrics-4191`.
  - Cambian solo dos objetos: `allow-f60-to-vectra-mock-ingress` y `allow-f60-prometheus-to-vectra-mock-egress`, que suman el 4191 y conservan el 8081.
  - **No se pierde ningún objeto.**
- **`merged()`.** Intercepté `merged()` (`scripts/dups.py`) para buscar documentos distintos que se descartan por tener el mismo tipo y nombre. No sale ninguno en HEAD, en `da15a07` ni en el `main` local `210da56`, en ningún entorno: hoy no esconde ninguna otra política.
- **Malla y sondas: no hay riesgo de que el mock no llegue a `Ready`.** Lo leí en el código del policy controller de Linkerd (`main`):
  - `workload.rs:65-75` (`pod_http_probes`) recoge las sondas también de `init_containers`, así que ve `/live` y `/ready` del proxy en el 4191.
  - `index.rs:1810-1830` (`http_routes`): un `Server` sin `HTTPRoute` recibe `default_inbound_http_routes(probe_paths)`, que crea la ruta `probe` autorizada desde `probeNetworks` (`index.rs:2243-2298`).
  - `probeNetworks` vale por omisión `0.0.0.0/0, ::/0` (`values.yaml:93-97` del chart) y nuestros values no lo tocan.
  - Las NetworkPolicy solo suman permisos.
- **Prod:** no rinde ni flujo ni `Server`. El PodMonitor sí llega a prod; ver F-02.

**2. `route_name`: la serie lo trae, y la expresión de U8 puede coincidir.**
- La documentación (`linkerd.io/2-edge/reference/proxy-metrics/`, consultada hoy) solo da `authority`, `direction` y `tls`. Ahí el codificador tiene razón.
- El código del proxy (`linkerd2-proxy`, `main`) dice otra cosa:
  - `linkerd/app/inbound/src/metrics/authz.rs:49`: `deny: Mutex<HashMap<RouteKey, Counter>>`, con `RouteKey = Key<RouteLabels>` (`:77`).
  - `Key` emite `target_addr`, `target_ip` y `target_port`, luego las etiquetas de ruta y luego `TlsAccept` (`:290-300`).
  - `RouteLabels` (`app/core/src/metrics.rs:387-400`) emite `srv_group`, `srv_kind`, `srv_name` y `srv_port`, más `route_group`, `route_kind` y `route_name`.
  - `TlsAccept` (`transport/labels.rs:126-142`) emite `tls`, más `client_id` (o `no_tls_reason`/`sni`).
- Resultado: la serie trae `route_name` (= el nombre del `HTTPRoute`, `core-mock-catch-all`, `generated/kind/vectra-mock.yaml:116`) y Prometheus le añade `namespace`. **La expresión de U8 tal como está puede coincidir**, siempre que el Job haga un POST: un POST solo casa la ruta de captura, no la del GET de `case-service`.
- No trae `direction`, `route_namespace` ni `authz_*`.
- Severidad para U8: ninguna, no hay que corregirla. La prueba sí lleva un contrato de etiquetas inexacto (F-01).
- Fuentes descargadas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/r1/` (`linkerd_app_inbound_src_metrics_authz.rs`, `linkerd_app_core_src_metrics.rs`, `labels.rs`, `pc_workload.rs`, `pc_index.rs`, `pod.go`, `promop_v0942.go`, `proxy-metrics.txt`).

## Hallazgos
### F-01 · NARANJA · `platform/tests/test_proxy_metrics.py:46-63` · `FAMILY_LABELS` no coincide con lo que emite el proxy
- Para `inbound_http_authz_deny_total` declara `direction` y `route_namespace`, que el proxy **no** emite.
- Le faltan `srv_*`, `target_*`, `client_id` y `tls`. `tls` sí lo lista.
- `inbound_http_authz_allow_total` está en la misma situación: el proxy emite `srv_*`, `route_*`, `authz_group`, `authz_kind`, `authz_name`, `target_*`, `tls` y `client_id`.
- Consecuencia: una regla que filtre por `direction="inbound"` pasa la prueba y nunca coincide.
- Corrección: tomar los conjuntos del código citado arriba, con la ruta y el commit, y quitar el «POR CONFIRMAR» de `route_name`. Sigue pendiente ver la serie real en U12.
- No rompe ningún criterio: CA-5 admitía «POR CONFIRMAR». Según RL-2 va a `CANDIDATAS.md`.

### F-02 · AMARILLO · `platform/observability/monitors/monitors.yaml:38-52` · el PodMonitor `linkerd-proxy` también se instala en prod
`observability-monitors` (`components.yaml:55`) no tiene `envs`. En prod el monitor queda inerte, porque `vectra-mock` no existe, pero la enmienda de F60 dice «kind y staging». Se puede documentar o limitar.

### F-03 · AMARILLO · `test_proxy_metrics.py:147` · la clave de la etiqueta del pod sale de una coincidencia
La prueba saca la clave de las `metadata.labels` del PodMonitor del chart, no de la `sourceLabel` `__meta_kubernetes_pod_label_linkerd_io_control_plane_ns` del `keep`. Hoy da el mismo valor por coincidencia.

### F-04 · AMARILLO · `test_proxy_metrics.py:427-432` · la vacuidad solo se exige en kind
Si staging perdiera `CoreWriteAttempt`, su caso pasaría sin haber comprobado nada.

### F-05 · AMARILLO · `bitacoras/U01-T09.md` («Candidatas») · candidata anotada solo en la bitácora
La candidata de `merged()` está en la bitácora, pero no se añadió a `CANDIDATAS.md`.

## Tareas candidatas (defectos reales fuera de alcance)
- `platform/network/generate.py:351-362` (`merged()`): descarta en silencio un documento repetido por tipo y nombre aunque difieran los puertos. Hoy no esconde nada (comprobado en tres revisiones), pero debería fallar o unir los puertos.
- F-01 y F-02, según RL-2.

## Rutas de transcripciones largas
- Logs (todos en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/r1/`):
  - `u01t09-verde.log`
  - `u01t09-rojo.log`
  - `u01t09-mut-M1-sin-monitor.log` … `u01t09-mut-M10-route-namespace.log`
  - `u01t09-check-local.log`
  - `u01t09-check-tools.log`
  - `u01t09-links.log`
- Scripts:
  - `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/scripts/cmpgen.py`
  - `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/scripts/dups.py`
  - `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/scripts/mut.sh`
  - `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/scripts/rules.py`

```
VEREDICTO: VERDE
NARANJA|platform/tests/test_proxy_metrics.py:46-63|FAMILY_LABELS no coincide con las etiquetas que emite el proxy (direction/route_namespace de más; srv_*, target_*, client_id de menos)
INFORME: revisiones/U01-T09/ronda-1.md
```
