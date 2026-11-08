# U02-T17 — Applications de GitOps de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de despliegue. Ninguna historia nueva.
**Depende de:** los Pasos 1–11 y 13 de U2, ya en `main`. Se parte de `main` (34f54c4 o posterior). **No** se usa el código del PR 75, que se cerró sin fusionar: la tarea se hace de nuevo (decisión del usuario, 2026-11-08).

Paso 12 del plan de U2.

> **Enmienda del 2026-11-08 (orquestador, decisión del usuario tras la revisión de código del PR 78, C-05; `revisiones/U02-T17/arbitraje-ronda-2.md`).** `identity-jobs` va en la **wave 4**, no en la 3, y el par `keycloak` → `identity-jobs` es `STRICT`, no «misma wave». Donde esta tarea dice wave 3 para `identity-jobs`, o espera las waves 2, 3, 3, 3, 3, 4, 4 en CA-2, rige 2, 3, 3, 3, 4, 4, 4.

Entra **completo** en el alcance de la demo (`aidlc-docs/construction/plans/demo-kind-alcance.md`, U2, Paso 12 = E).

## Alcance

**Dentro:** todo el Paso 12 del plan. Texto del plan, sin recortes:

- [ ] **Paso 12 — Applications de GitOps**
  - Entradas en `vectra-risk-gitops/components.yaml` con sus waves: Valkey (2), Keycloak + `keycloak-config-cli` y gateway + rate limit (3); los CRDs de Gateway API y el controlador (0) ya están en la entrada `envoy-gateway` de U1. `generate.py` escribe las Applications. Values por entorno en `vectra-risk-gitops/values/<env>/<componente>.yaml`: hostnames (INF-U2-01), issuer y LDAP (prod) (revisión de consistencia entre unidades, 2026-11-01).
  - **Nota del 2026-11-05 (decisión B6 del usuario al preparar U02-T13):** el paso también suma las entradas `identity-rules` e `identity-monitors` en wave 4, con las reglas y los monitores que deja el Paso 11 en `identity-edge/observability/`.
  - Diseño: P-U1-12; INF-U2-01.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`, `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync` sobre las Applications nuevas (revisión de consistencia entre unidades, 2026-11-01).

Precisiones que la tarea aplica:

- **Fuentes ya renderizadas.** Todo lo de U2 se renderiza en el repositorio por entorno, desde los values de `identity-edge/`. Las Applications apuntan a esos directorios con `path` y `{env}`, como la entrada `network` de U1:

  | Componente (nombre de la Application) | Wave | Namespace | Fuente |
  |---|---|---|---|
  | `valkey` | 2 | `vectra-edge` | `identity-edge/charts/valkey/rendered/{env}` |
  | `keycloak` | 3 | `vectra-identity` | `identity-edge/keycloak/rendered/{env}` |
  | `identity-jobs` (los CronJobs `realm-drift` y `signing-key-age` y el ConfigMap del realm; `keycloak-config-cli` es un hook `PostSync` de `keycloak` y no entra aquí) | 4 | `vectra-identity` | `identity-edge/jobs/rendered/{env}` |
  | `gateway` (Gateway, rutas y políticas) | 3 | `vectra-edge` | `identity-edge/gateway/generated/{env}` |
  | `ratelimit` (el `ExternalSecret` del servicio de rate limit; el Deployment lo crea Envoy Gateway) | 3 | `envoy-gateway-system` o donde lo diga `identity-edge/ratelimit/external-secret.yaml` | `identity-edge/ratelimit`, `include: external-secret.yaml` |
  | `identity-rules` | 4 | `vectra-observability` | `identity-edge/observability/rules`, `include: identity-edge-rules.prometheusrule.yaml` |
  | `identity-monitors` | 4 | `vectra-observability` | `identity-edge/observability/monitors`, `include: monitors.yaml` |

  Si el namespace real de un recurso no coincide con la tabla, manda el del recurso. Regístralo en la bitácora.
- **Values por entorno.** Ver la decisión V1 en las Notas.
- **Orden.** `platform/tests/test_waves.py` suma, en su tabla de dependencias, los pares de U2: `postgres` → `keycloak`; `valkey` → `gateway`; `envoy-gateway` → `gateway`; `keycloak` → `identity-jobs` (`STRICT`: `identity-jobs` va en la wave 4 y `keycloak` en la 3, porque dentro de una wave Argo CD no ordena las Applications); `prometheus-operator-crds` → `identity-rules` e `identity-monitors`. Si un par no se puede expresar con la tabla tal cual, detente y repórtalo.
- **Sin sync automático.** Ninguna Application nueva tiene `syncPolicy.automated` (NFR-U1-43).
- **README.** `vectra-risk-gitops/README.md`: la línea «Las waves 3 y 6 … las agregan U2 y U6» queda «La wave 6 la agrega U6».
- **Plan.** Marca `[x]` el Paso 12 en `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`, con `(U02-T17)`.

**Fuera** (rechazar aunque se vea roto):

- Instalar o sincronizar nada en el clúster. Eso es el Paso 16 y lo hace el operador (AUTONOMIA-01).
- Cambiar los renders de `identity-edge/` o sus values. Si un render está mal, va a `CANDIDATAS.md`.
- El endurecimiento de alertas B12–B15 y la ronda 5 de U02-T15 (PR 74 y 76, cerrados): diferidos por la demo (T2 y T3).
- Applications de otras unidades.
- Cambiar `generate.py` más allá de lo necesario para estas entradas. Si hace falta, el cambio lleva su prueba.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 12, §1 «Estructura de destino»)
- `aidlc-docs/construction/plans/demo-kind-alcance.md`
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, INF-U2-02)
- `aidlc-docs/construction/platform-foundation/nfr-design/` (P-U1-12)
- `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/generate.py`, `vectra-risk-gitops/README.md`
- `platform/tests/test_waves.py`
- `platform/policies/kyverno/disallow-argocd-auto-sync.yaml` y `platform/policies/kyverno/kyverno-test.yaml`
- `identity-edge/Makefile` (targets `render-*` y `route-gen`, para saber de dónde sale cada render)

## Criterios de aceptación

- [ ] **CA-1** — Las Applications versionadas coinciden con lo que genera `components.yaml`.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check
  ```
  Esperado: código 0.

- [ ] **CA-2** — Las 7 Applications de U2 existen en los tres entornos, con su wave, su namespace y su fuente.
  ```bash
  for env in kind staging prod; do for a in valkey keycloak identity-jobs gateway ratelimit identity-rules identity-monitors; do \
    yq -e '.metadata.annotations["argocd.argoproj.io/sync-wave"]' vectra-risk-gitops/apps/$env/$a.yaml || echo "FALTA $env/$a"; done; done
  ```
  Esperado: 21 waves (2, 3, 3, 3, 3, 4, 4 por entorno) y ningún `FALTA`. Además, `spec.source.path` de cada una lleva el entorno correcto (por ejemplo `identity-edge/keycloak/rendered/staging` en staging).

- [ ] **CA-3** — El orden de waves respeta P-U1-12 y las dependencias de U2.
  ```bash
  uv run python platform/tests/test_waves.py
  ```
  Esperado: código 0. **Rojo primero:** con la wave de `keycloak` puesta en 2, o la de `valkey` en 3, la prueba falla y nombra el par.

- [ ] **CA-4** — Ninguna Application nueva sincroniza sola.
  ```bash
  kyverno test platform/policies/kyverno/   # con los recursos de prueba que incluyen las Applications nuevas
  ```
  Esperado: `pass` en las Applications de U2, y `fail` en una copia con `syncPolicy.automated` (caso negativo en el `kyverno-test.yaml`).

- [ ] **CA-5** — Las verificaciones de U1 y U2 siguen en verde.
  ```bash
  make -C platform check && make -C identity-edge check
  ```
  Esperado: código 0 en los dos.

- [ ] **CA-6** — Decisión V1-a: sin values de U2 en GitOps y con la nota en el plan.
  ```bash
  test ! -e vectra-risk-gitops/values && grep -c "decisión V1-a" aidlc-docs/construction/plans/identity-edge-code-generation-plan.md
  ```
  Esperado: código 0 y un conteo ≥ 1.

## Plan de pruebas

- La tabla de dependencias de `test_waves.py` con los pares de U2, y su caso rojo (CA-3).
- Caso negativo de `disallow-argocd-auto-sync` sobre una Application de U2 con `syncPolicy.automated` (CA-4).
- Si `generate.py` cambia: prueba de ese cambio.

**Rojo primero:** registra en la bitácora la salida de `test_waves.py` en rojo antes de corregir las waves, y la de `kyverno test` con el caso negativo.

## Notas

- Archivos que se modifican en su sitio: `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/README.md`, `platform/tests/test_waves.py`, `platform/policies/kyverno/kyverno-test.yaml` (o su recurso de prueba), el plan de U2. `vectra-risk-gitops/apps/<env>/` lo escribe `generate.py`.
- **V1 — Values por entorno (decisión del usuario, 2026-11-08: V1-a).** El plan pide `vectra-risk-gitops/values/<env>/<componente>.yaml` con hostnames, issuer y LDAP. Pero ningún componente de U2 los leería: todos se renderizan en el repositorio, y esos valores ya están en `identity-edge/gateway/values/<env>.yaml`, `identity-edge/keycloak/values/<env>.yaml` y `identity-edge/jobs/values/<env>.yaml`. Por eso:
  - **no** se crean archivos en `vectra-risk-gitops/values/` para U2;
  - se agrega al Paso 12 del plan la nota: «Nota del 2026-11-08 (decisión V1-a del usuario al preparar U02-T17): sin `vectra-risk-gitops/values/<env>/` para U2. Todo U2 se renderiza en el repositorio, y hostnames, issuer y LDAP tienen una sola fuente: los values de `identity-edge/`.»;
  - CA-6 lo comprueba.
