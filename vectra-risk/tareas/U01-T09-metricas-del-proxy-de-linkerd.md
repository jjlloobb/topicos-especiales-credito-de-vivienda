# U01-T09 — Métricas del proxy de Linkerd: que Prometheus raspe el 4191 de `vectra-mock`, y atarlo con una prueba

**Unidad:** U1 `platform-foundation` (la regla que lee la serie es de U8; U8 no se toca).
**Historias:** ninguna nueva. Corrige una fuente de métricas que falta y de la que depende la demo D3 (RT-5).
**Depende de:** nada. Todo lo que toca está en `main` (comprobado al redactar, sobre `4e33d39`).
**Rama:** `tarea/U01-T09`, desde `origin/main`.

**Por qué.** Hallazgo F-02 de `revisiones/U08-T05/ronda-1.md` (líneas 61 a 64; candidata en `CANDIDATAS.md`, línea 622). En D3 (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §1.3, líneas 107 a 109) el Job `rt5-demo-<runId>` intenta escribir en `core-banking-mock`, Linkerd responde 403 en la ruta `core-mock-catch-all` y la alerta `CoreWriteAttempt` debe disparar. El mock no ve la solicitud (`vectra_core_write_attempts_total` queda en 0), así que la alerta solo puede disparar por su rama de Linkerd, que lee `inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}`. El recorte atribuye esa serie a U1 (línea 108), y el oráculo de U12 la consulta con `query_range` (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, líneas 129 y 130).

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6, líneas 278 a 282): máximo 2 rondas y solo un ROJO bloquea. `CoreWriteAttempt` es una de las alertas que T2 **no** difiere (línea 43). Sin clúster (`DECISIONES-LOOP.md` §8).

---

## Lo comprobado al redactar (sobre `4e33d39`; verifícalo)

La hipótesis del revisor es **cierta**, y faltan tres capas, no una. Nada de esto se probó en clúster.

| # | Qué | Evidencia (ruta y línea) |
|---|---|---|
| 1 | Linkerd se instala con tres charts del canal edge, versión `2026.10.2`; **no hay `linkerd-viz`** | `vectra-risk-gitops/components.yaml` 20, 21 y 29 |
| 2 | Nuestros values no activan `podMonitor` ni anotaciones de Prometheus | `platform/mesh/linkerd-values.yaml` (21 líneas) y `platform/mesh/linkerd-kind.yaml` (4 líneas): ninguna clave `podMonitor` |
| 3 | El chart sí trae `podMonitor.enabled: false` y `podMonitor.proxy.enabled: true`. Activarlo crea **tres** PodMonitor en `linkerd` (el del proxy con `namespaceSelector: any: true`, a 10 s, sin `metricRelabelings`) | `platform/.charts/linkerd-control-plane/linkerd-control-plane/values.yaml` 708 a 740; `templates/podmonitor.yaml` 84 a 145 |
| 4 | El proxy declara el puerto `linkerd-admin` = 4191 en el contenedor `linkerd-proxy` | mismo chart, `values.yaml` 167; `charts/partials/templates/_proxy.tpl` 259 a 262 |
| 5 | Los cuatro PodMonitor de U1 raspan Kyverno, cert-manager, el `destination` de Linkerd (puerto `dest-admin`, el plano de control, no el proxy) y MinIO. Ninguno raspa el 4191 | `platform/observability/monitors/monitors.yaml` 3 a 37 |
| 6 | Tampoco los de U2 ni el `ServiceMonitor` del mock de U8 (puerto 8081) | `identity-edge/observability/monitors/monitors.yaml`; `case-management/chart/templates/servicemonitors.yaml` 1 |
| 7 | Prometheus toma los monitores de cualquier namespace y sin filtro de etiquetas | `platform/observability/values/kube-prometheus-stack.yaml` 26 a 30 |
| 8 | **No hay flujo de red al 4191.** F60 abre de `prometheus` a `ns:vectra-mock` solo el 8081; `grep -c 4191 platform/network/flows.yaml` da 0 | `platform/network/flows.yaml` 221 a 226 |
| 9 | En `vectra-mock`, lo generado solo admite el 8080 (F17) y el 8081 (F60): `NetworkPolicy` `allow-f60-to-vectra-mock-ingress` y `Server` `metrics-8081` | `platform/network/generated/kind/vectra-mock.yaml` 155 a 210 |
| 10 | **La malla niega por omisión**, y no hay `Server` para el 4191: sin autorización, el proxy respondería 403 al raspado | `platform/mesh/linkerd-values.yaml` 13; `platform/namespaces/templates/namespaces.yaml` 12 y 13 |
| 11 | El generador ya sabe hacerlo: un flujo con destino `ns:<namespace>` produce la `NetworkPolicy`, un `Server` `metrics-<puerto>` para todo el namespace, **sin rutas**, y la autorización por identidad de `prometheus` | `platform/network/generate.py` 343 a 348 y 447 a 451 |
| 12 | `vectra-mock` existe en kind y en staging, no en prod | `platform/network/flows.yaml` 125; `platform/network/tests/test_flows.py` 193 a 199 |
| 13 | La expresión exige las etiquetas `namespace` y `route_name`, nada más (ni `authz_name` ni `srv_name`) | `case-management/observability/rules/case-management.rules.yaml` 9 a 13; INF-U8-03 en `aidlc-docs/construction/case-management/infrastructure-design/infrastructure-design.md` 85 a 102 |
| 14 | El nombre de la ruta sale de U1 | `platform/network/flows.yaml` 65 y 66 |
| 15 | **Ninguna otra regla lee métricas del proxy.** `AuthDeniedBurst` (U2) usa `keycloak_user_events_total` y `vectra_authz_denied_total`; `platform-rules.yaml` solo nombra a Linkerd en `up{job="linkerd-controller"}` (línea 80) y en un certificado (línea 120). Los tableros tampoco | `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` 136; `git grep` de las familias del proxy en reglas y tableros: solo U8 |
| 16 | La prueba que ata reglas y fuentes solo mira las reglas de U1 | `platform/tests/test_alert_sources.py` 11 y 15 a 22 |
| 17 | El diseño de U1 no menciona las métricas del proxy; el inventario de F60 lista puertos y no trae el 4191 | `grep` sin resultados en `aidlc-docs/construction/platform-foundation/`; `aidlc-docs/inception/application-design/component-dependency.md` 168 |
| 18 | Precedente: U01-T03 añadió F130 porque los targets de la malla sin flujo daban 504 | `tareas/U01-T03-flujos-de-metricas.md` 8 |

**Lo que no se puede saber sin clúster** (va a «Pendiente en U12», CA-7):

- Las etiquetas reales de la serie. El chart no las lista (`grep -rl route_name` sobre el chart no da nada); la fuente es la referencia «Proxy Metrics» de la documentación de Linkerd.
- Que el raspado de `prometheus` (mallado) llegue al 4191 con mTLS y la `MeshTLSAuthentication` lo reconozca. Es lo que hace `linkerd viz allow-scrapes` upstream, pero aquí no se midió.
- Que un `Server` sin rutas en el 4191 siga dejando pasar las sondas `/live` y `/ready` del propio proxy (`flows.yaml`, línea 12: Linkerd solo deja de autorizarlas en un `Server` **con** rutas).
- Que Prometheus descubra el puerto de un sidecar nativo, que es un init container (`linkerd-values.yaml`, línea 17).

---

## Alcance

**Dentro**, en este orden:

1. **Verificar** la tabla de arriba contra el `main` de tu rama y anotar en la bitácora cada fila como «igual» o corregida. Si algo ya raspa el proxy, la tarea se reduce a los pasos 2 y 5.
2. **Escribir la prueba de mundo cerrado** `platform/tests/test_proxy_metrics.py` y **verla fallar** sobre `main` (rojo primero).
3. **El cambio mínimo**, según P-1 y P-2:
   - un PodMonitor `linkerd-proxy` en `platform/observability/monitors/monitors.yaml`, que alcance a los pods de `vectra-mock` por el puerto `linkerd-admin`, con `metricRelabelings` que conserven solo las familias que alguna regla lee;
   - un flujo F60 de `prometheus` a `ns:vectra-mock` por el 4191 en `platform/network/flows.yaml`, y lo generado (`make -C platform generate`);
   - la enmienda fechada de la fila F60 en `component-dependency.md` (línea 168).
4. **`make -C platform check`** completo (RL-4).
5. **Cierres:** `CANDIDATAS.md` y los dos «pendientes» (CA-7).

**Fuera** (recházalo aunque lo veas roto):

- Todo `case-management/`: la expresión de `CoreWriteAttempt`, su prueba de `promtool`, el chart y el runbook. Si la expresión te parece mal, **para y reporta**.
- Instalar `linkerd-viz`, o activar `podMonitor.enabled` del chart de Linkerd (P-1 c).
- `platform/network/generate.py`. Si el flujo con `ns:` no genera lo que hace falta, **para y reporta** (P-2).
- Raspar el proxy de otros namespaces, tableros de la malla, reglas nuevas, runbooks.
- `platform/mesh/`, los values de `kube-prometheus-stack` y `BUDGET_GIB`.
- `system-verification/` (U12) y `tareas/U12-T03-*.md`.
- Desplegar, sincronizar o tocar el clúster.

---

## La prueba de mundo cerrado

`platform/tests/test_proxy_metrics.py`. Corre con `make -C platform check-local`, sin clúster y sin Docker. Modelo: `platform/tests/test_token_issuer.py` (descubre con `integration.chart_renders`, que da los values que Argo CD pasa a cada chart; mutaciones sobre copias en memoria).

Para cada entorno (kind, staging, prod):

1. **Reglas, descubiertas y no listadas:** toda `PrometheusRule` que ese entorno instala, sea archivo de un componente de `vectra-risk-gitops/components.yaml` o render de un chart. De cada `expr` salen los nombres de métrica y sus selectores de etiquetas.
2. **Familias del proxy:** una constante con los prefijos que emite el proxy (como mínimo `inbound_`, `outbound_`, `request_total`, `response_total`, `response_latency_ms`, `route_`, `tcp_`, `identity_cert_`), con la URL y la versión de la fuente en un comentario. Las métricas de la aplicación (`vectra_…`) no entran.
3. **Por cada métrica del proxy que una regla lee** hay, en lo que ese entorno instala:
   - **un monitor** (`PodMonitor` o `ServiceMonitor`) cuyo `namespaceSelector` incluye el namespace que la regla filtra (`namespace="vectra-mock"`) y cuyo `selector` casa con un pod de ese namespace con el proxy inyectado. El pod inyectado se modela desde las fuentes, sin copiarlas: el namespace lleva `linkerd.io/inject: enabled` (`platform/namespaces/`), el workload no lo desactiva, y la etiqueta y el puerto que añade el inyector se leen del chart fijado (`platform/.charts/linkerd-control-plane/`: `proxy.ports.admin` y el nombre `linkerd-admin`). Si falta el chart, la prueba falla y pide `make -C platform charts`;
   - **un puerto** del endpoint que existe en ese pod (por nombre o por número);
   - **la etiqueta `namespace` del pod:** el monitor no reescribe `namespace` ni usa `honorLabels`;
   - **la familia sobrevive** a los `metricRelabelings` (se evalúan las acciones `keep` y `drop` sobre `__name__`);
   - **un flujo** de `prometheus` a ese namespace por ese puerto, habilitado en ese entorno, y en `platform/network/generated/<env>/` su `NetworkPolicy` de entrada, su `Server` y una autorización para la identidad de `prometheus`;
   - **las sondas siguen vivas:** ese `Server` no tiene `HTTPRoute`, o tiene también las de `/live` y `/ready`.
4. **Etiquetas (`labels`):** cada etiqueta que la regla exige de una métrica del proxy está en la unión de las etiquetas de target (`namespace`, `pod`, `container`, `job`, `instance`) y las que la documentación de Linkerd da para esa familia en la versión de `components.yaml`. La lista es una constante con su fuente; la serie real queda para U12.
5. **No pasa en vacío:** en kind hay al menos una regla que lee una métrica del proxy (`CoreWriteAttempt`). En prod, donde no hay mock ni regla, la prueba no exige flujo.

---

## Criterios de aceptación

Desde `vectra-risk/`. Guarda los logs con el prefijo `u01t09-`. `PYT="-q -p no:cacheprovider --rootdir=platform --import-mode=importlib"`.

- [ ] **CA-1 — La hipótesis está verificada sobre tu `main`.**
  ```bash
  git grep -nE "4191|linkerd-admin|linkerd-viz|inbound_http_authz" origin/main -- . ':(exclude)*.md' ':(exclude)*.lock' ':(exclude)case-management'
  git show origin/main:vectra-risk/platform/network/flows.yaml | grep -c 4191
  git show origin/main:vectra-risk/platform/mesh/linkerd-values.yaml | grep -ciE "podMonitor|prometheus"
  ```
  Esperado: sin salida; `0`; `0`. La bitácora trae la tabla con cada fila marcada. Si alguna orden da otra cosa, anótalo y aplica el paso 1 del alcance.
- [ ] **CA-2 — Rojo primero.** Con la prueba escrita y **sin** el cambio (el commit de la prueba va antes):
  ```bash
  uv run pytest platform/tests/test_proxy_metrics.py $PYT
  ```
  Esperado: termina en 1. El mensaje nombra `CoreWriteAttempt`, `inbound_http_authz_deny_total`, `vectra-mock` y `kind`, y dice que faltan el monitor y el flujo. Los casos de prod y el de etiquetas pasan. La salida va en la bitácora con el hash del commit.
- [ ] **CA-3 — Verde tras el cambio.** La misma orden con `-v` termina en 0 y muestra al menos un caso por entorno y, en kind, el de `CoreWriteAttempt`.
- [ ] **CA-4 — La prueba detecta cada desajuste.**
  ```bash
  uv run pytest platform/tests/test_proxy_metrics.py $PYT -k mutation -v
  ```
  Esperado: pasan, como mínimo, estos casos, cada uno con un mensaje que nombra la regla, la métrica y el entorno: (a) sin el monitor; (b) `namespaceSelector` que no incluye `vectra-mock`; (c) `selector` con una etiqueta que el pod inyectado no tiene; (d) puerto que el proxy no declara (`admin-http`, `4190`); (e) `metricRelabelings` con un `keep` que no incluye la familia, y otro con un `drop` que la tira; (f) sin el flujo al 4191, y con el flujo deshabilitado en kind; (g) un `relabeling` que fija `namespace` a `vectra-observability`; (h) un `HTTPRoute` de `/metrics` colgado del `Server` sin las rutas de sondas; (i) la regla filtra por una etiqueta que la familia no trae (`route` en vez de `route_name`).
- [ ] **CA-5 — Las etiquetas de `CoreWriteAttempt` tienen fuente.**
  ```bash
  uv run pytest platform/tests/test_proxy_metrics.py $PYT -k labels -v
  grep -nE "https://linkerd\.io/|2026\.10\.2" platform/tests/test_proxy_metrics.py
  ```
  Esperado: 0, y al menos una línea con la URL de la referencia y la versión. La bitácora copia el párrafo de la fuente que da `route_name` para `inbound_http_authz_deny_total`. Si no consigues la fuente, la constante lleva `POR CONFIRMAR EN U12` y lo dices en el informe.
- [ ] **CA-6 — Cambio mínimo y lo generado al día.**
  ```bash
  uv run python platform/network/generate.py --check
  grep -l 4191 platform/network/generated/*/*.yaml
  git diff --name-only origin/main | grep -vE '^vectra-risk/(platform/(observability/monitors/monitors\.yaml|network/flows\.yaml|network/generated/(kind|staging)/[a-z-]+\.yaml|tests/test_proxy_metrics\.py|network/tests/test_flows\.py)|aidlc-docs/inception/application-design/component-dependency\.md|aidlc-docs/construction/(case-management/evidence/cierre-demo|platform-foundation/evidence/cierre-acotado)\.md|bitacoras/U01-T09\.md|CANDIDATAS\.md)$'
  ```
  Esperado: 0; solo archivos de `kind/` y `staging/` (`vectra-mock.yaml`, `vectra-observability.yaml` y, si el generador lo añade, `connectivity-suite.yaml`), ninguno de `prod/`; la tercera sin salida.
- [ ] **CA-7 — Cierres.**
  ```bash
  grep -n "U01-T09" CANDIDATAS.md aidlc-docs/construction/case-management/evidence/cierre-demo.md aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md aidlc-docs/inception/application-design/component-dependency.md
  ```
  Esperado: la entrada de F-02 de `CANDIDATAS.md` termina en «**Atendida en U01-T09**» con una línea de qué se hizo; «Pendiente en U12» de `cierre-demo.md` (línea 64) y «No comprobado o incompleto» de `cierre-acotado.md` (línea 18) nombran lo que solo se ve en kind: el target `linkerd-proxy` en `up == 1` (no 403), la serie con `namespace="vectra-mock"` y `route_name="core-mock-catch-all"` tras el 403 real, y los pods de `vectra-mock` `Ready` con el `Server` del 4191; y la fila F60 trae la enmienda con fecha.
- [ ] **CA-8 — `make check` de U1.**
  ```bash
  uptime; export TMPDIR=$PWD/platform/.tools/tmp; mkdir -p $TMPDIR; make -C platform check
  ```
  Esperado: 0. Incluye `test_alert_sources.py`, `test_kind_profile.py` y `platform/network/tests`. Anota `uptime` y la duración. Ningún `check` de otra unidad: no cambia nada suyo.

---

## Cambios permitidos, archivo por archivo

| Archivo | Qué |
|---|---|
| `platform/tests/test_proxy_metrics.py` | nuevo; la prueba |
| `platform/observability/monitors/monitors.yaml` | un PodMonitor más, con la forma de los otros cuatro (namespace `vectra-observability`, etiqueta `vectra.io/criticality`, `relabelings` con `job`) |
| `platform/network/flows.yaml` | una línea F60 al 4191 |
| `platform/network/generated/{kind,staging}/` | solo lo que escribe `make -C platform generate` |
| `platform/network/tests/test_flows.py` | solo si una prueba existente fija los puertos de F60 o del mock; añade, no relajes |
| `aidlc-docs/inception/application-design/component-dependency.md` | enmienda fechada en la fila F60 (línea 168), con la forma de la del 2026-11-05 |
| `CANDIDATAS.md`, `cierre-demo.md` de U8, `cierre-acotado.md` de U1 | una línea en los dos primeros y una fila en la tabla del tercero (CA-7) |
| `bitacoras/U01-T09.md` | nuevo |

---

## Preguntas abiertas

**P-1 — Qué se raspa y por dónde. NECESITA AL USUARIO** (abre un puerto nuevo en el inventario de flujos; el precedente del 2026-11-05 fue decisión suya).
- (a) **Solo `vectra-mock`, con un PodMonitor propio y `metricRelabelings` que conservan las familias `inbound_http_authz_…` y `inbound_http_route_not_found_total`** (recomendada). Es el único namespace que una regla filtra (fila 15). Un pod, pocas decenas de series. El flujo existe en kind y en staging, como el mock.
- (b) Toda la malla (nueve namespaces), con el mismo filtro. Pide nueve destinos más en F60 y un `Server` del 4191 en cada namespace. Sin filtro, cada proxy emite del orden de cientos a miles de series (estimación, sin medir) y Prometheus en kind tiene 1 GiB de límite (`platform/observability/values/kube-prometheus-stack-kind.yaml`, línea 8); `BUDGET_GIB` (`platform/tests/test_kind_profile.py`, línea 34; `DECISIONES-LOOP.md` §7) cuenta requests, no series, y no lo vería.
- (c) `podMonitor.enabled` del chart de Linkerd. Raspa todos los namespaces a 10 s, sin filtro, duplica el monitor `linkerd-controller` y no resuelve la red.

**Recomendación: (a).** Si no hay respuesta, el codificador entrega la prueba en rojo (CA-2) y **para**: no abre el flujo sin la decisión.

**P-2 — Cómo se autoriza el 4191 en Linkerd.**
- (a) **El flujo con destino `ns:vectra-mock`, tal como lo genera hoy `generate.py`:** `Server` `metrics-4191` sin rutas e identidad de `prometheus` (recomendada). No toca el generador y deja las sondas en la autorización por omisión.
- (b) Un `HTTPRoute` de `/metrics` más las rutas de sondas, como `linkerd viz allow-scrapes`. Más estricto, pero cambia el generador y arriesga las sondas del proxy.

**Recomendación: (a).** Si no hay respuesta, rige (a). Si en U12 el raspado llega sin mTLS, la salida es `unmeshed_source` con `pod_cidr` (`flows.yaml`, líneas 7 a 9), en otra tarea.

**P-3 — Dónde queda el contrato de etiquetas.**
- (a) **Constante en la prueba, con fuente, y la serie real en «Pendiente en U12»** (recomendada).
- (b) Solo en U12.

**Recomendación: (a).** Si no hay respuesta, rige (a).

**P-4 — Intervalo de raspado.** El de por omisión de Prometheus (no hay `scrapeInterval` en nuestros values) frente a los 10 s del chart de Linkerd. La alerta compara con `offset 5m` y el oráculo mira hasta t1 + 15 min: **el de por omisión basta** (recomendada). Si no hay respuesta, rige esa.

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota.** No copies el repositorio allí. `export TMPDIR=$PWD/platform/.tools/tmp` para `promtool`, `check-tools` y `check-local`.
- **Máquina compartida y cargada.** Anota `uptime` junto a cada `make`. Corre los `make` en serie.
- **Sin clúster.** Nada de `kubectl`, `helm install`, `argocd` ni sync; tampoco contra el kind de la máquina. `helm template` sí.
- **`platform/.tools` y `platform/.charts` no están versionados.** En tu worktree, crea `platform/.tools/` real y copia o enlaza **solo** `platform/.tools/bin`. Llena `platform/.charts` con `make -C platform charts` (`platform/charts.sh` baja también los OCI) o cópialo del árbol principal. No enlaces los directorios enteros.
- **No uses `make -C platform check-chart`:** comparte `platform/.tools/integration` con otros agentes.
- **No toques el árbol principal ni otros worktrees. No uses `git stash`:** la pila se comparte. Para el rojo de CA-2, ordena los commits.

---

## Notas

- **Bitácora:** `bitacoras/U01-T09.md`, con el acuse de lectura (hash de este archivo), la tabla verificada, el rojo de CA-2 con su hash, los rojos de CA-4, la fuente de las etiquetas, la respuesta aplicada a cada P-n y la carga de cada corrida.
- **Trampa:** `platform/tests/test_alert_sources.py` (línea 36) recorre `e["relabelings"]` de cada endpoint: un monitor sin `relabelings` la rompe con `KeyError`.
- **Trampa:** el proxy es un init container (sidecar nativo). La prueba modela el pod inyectado; no busques el contenedor `linkerd-proxy` en los renders, porque lo añade el inyector en la admisión.
- **Trampa:** la etiqueta `namespace` la pone el relabeling de Prometheus Operator con el namespace del **pod**; el proxy no la emite. El PodMonitor del chart de Linkerd la fija a mano (`templates/podmonitor.yaml`, líneas 118 a 120); el nuestro no lo necesita.
- **La serie nace en 1** con la primera denegación; por eso la expresión de U8 resta con `offset` y no usa `increase()`. No es asunto de esta tarea.
- **Lo que esta tarea no demuestra:** que la alerta dispare en kind. Quedan atados el monitor, el selector, el puerto, el filtro de familias, el flujo y la autorización; el resto es U12 Paso 18.
- Archivos que se **modifican en su sitio**: los de la tabla. Nada de duplicados con sufijo.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
