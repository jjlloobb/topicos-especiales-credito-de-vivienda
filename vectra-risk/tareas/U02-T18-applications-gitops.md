# U02-T18 — Applications de GitOps de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de instalación. Ninguna historia nueva.
**Depende de:** U02-T13 (Paso 11) en `main`, en 0e3a1f3. Nada de U2 se sincroniza en esta tarea: el sync lo hace un operador en el Paso 16.

Paso 12 del plan de U2. El 2026-11-07 el orquestador comparó el paso con el diseño y con el código. Esto es lo que encontró:

- los values por entorno ya viven en `identity-edge/` y el Makefile los renderiza a directorios versionados que conftest y Kyverno verifican;
- el Job de `keycloak-config-cli` está bloqueado (INF-U2-05a) y no existe;
- los CronJobs `realm-drift` y `signing-key-age` no tienen Application en el plan;
- `platform/tests/test_platform.py` fija la lista exacta de componentes por wave, así que una entrada nueva lo rompe.

El usuario decidió M1–M3. Están en la nota del Paso 12 del plan.

## Alcance

**Dentro:** todo el Paso 12 del plan, con su nota del 2026-11-07. Texto del plan, sin recortes:

- [ ] **Paso 12 — Applications de GitOps**
  - Entradas en `vectra-risk-gitops/components.yaml` con sus waves: Valkey (2), Keycloak + `keycloak-config-cli` y gateway + rate limit (3); los CRDs de Gateway API y el controlador (0) ya están en la entrada `envoy-gateway` de U1. `generate.py` escribe las Applications. Values por entorno en `vectra-risk-gitops/values/<env>/<componente>.yaml`: hostnames (INF-U2-01), issuer y LDAP (prod).
  - Nota del 2026-11-05 (B6): también `identity-rules` e `identity-monitors` en wave 4.
  - Nota del 2026-11-07 (M1–M3): directorios renderizados en lugar de `values/<env>/`; sin `keycloak-config-cli`; `identity-jobs` en wave 4.
  - Diseño: P-U1-12; INF-U2-01.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`, `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync` sobre las Applications nuevas.

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Entradas de `components.yaml`**. Los nombres de las cuatro primeras son los de `FIXED_WAVES` de `platform/tests/test_waves.py`. Los tres entornos, salvo que el render de un entorno no exista.

  | Nombre | Wave | Namespace de destino | Fuente |
  |---|---|---|---|
  | `valkey` | 2 | `vectra-edge` | `identity-edge/charts/valkey/rendered/{env}` (M1) |
  | `keycloak` | 3 | `vectra-identity` | `identity-edge/keycloak/rendered/{env}` (M1, M2) |
  | `api-gateway` | 3 | `vectra-edge` | `identity-edge/gateway/generated/{env}` (M1) |
  | `rate-limit` | 3 | `envoy-gateway-system` | `identity-edge/ratelimit`, solo `external-secret.yaml` (el servicio `envoy-ratelimit` lo despliega el controlador de la entrada `envoy-gateway`, U02-T11) |
  | `identity-rules` | 4 | `vectra-observability` | `identity-edge/observability/rules`, solo `identity-edge-rules.prometheusrule.yaml` (B6) |
  | `identity-monitors` | 4 | `vectra-observability` | `identity-edge/observability/monitors`, solo `monitors.yaml` (B6) |
  | `identity-jobs` | 4 | `vectra-identity` | `identity-edge/jobs/rendered/{env}` (M3) |

  - Un directorio con más de un archivo se filtra con `include` o `exclude`, como las entradas de U1, para que la Application solo vea YAML de Kubernetes (ni values, ni pruebas, ni políticas).
  - El backend de eco de `identity-edge/tests/e2e/echo/` **no** entra: lo aplica el operador en el Paso 16 (H1).
- **Dependencias de waves** (P-U1-12). Agrega a `STRICT` o `SAME_WAVE_OK` de `test_waves.py` los pares que hagan falta, con la razón en un comentario, como los de U1. Como mínimo: `namespaces` y `secret-store` antes de `valkey` y de `keycloak`; `postgres` (el de `keycloak-db`) antes de `keycloak`; `valkey` antes de `rate-limit`; `envoy-gateway` antes de `api-gateway` y de `rate-limit`; `pushgateway` y `kube-prometheus-stack` con `identity-jobs`, `identity-rules` e `identity-monitors`. Si alguno no se sostiene con el código, dilo en la bitácora; no lo inventes.
- **Un recurso, una Application.** Argo CD no admite que dos Applications del mismo entorno manejen el mismo recurso. Comprueba que ningún `(apiVersion, kind, namespace, name)` aparece en dos Applications de un mismo entorno, en especial los `ServiceMonitor`/`PodMonitor` de `keycloak/rendered`, `charts/valkey/rendered` y `observability/monitors`. Si hay uno repetido, **detente y repórtalo**: elegir cuál lo pierde es una decisión de diseño.
- **AppProject**: cada recurso de cluster que traigan los directorios nuevos (por ejemplo, el `GatewayClass` de `gateway/generated`) debe estar en `CLUSTER_KINDS` o en `NAMED_CLUSTER_RESOURCES` de `generate.py`, y cada namespace de destino en las `destinations`. No agregues tipos que no se usen.
- **Sin `syncPolicy.automated`** en ninguna Application (NFR-U1-43).
- **Regresiones de U1**. `EXPECTED_WAVES` de `platform/tests/test_platform.py` se actualiza con las siete entradas. `platform/tests/integration.py` empieza a ver los manifiestos de U2: si una política de U1 falla sobre ellos, es del diff (`DECISIONES-LOOP.md` §1) y se arregla en esta tarea; si el arreglo toca `identity-edge/` fuera de lo que esta tarea nombra, detente y repórtalo.
- **`vectra-risk-gitops/README.md`**: la línea de las waves 3 y 6 dice qué agregó U2.

**Fuera:**

- El Job y el hook `PostSync` de `keycloak-config-cli` (M2). Siguen en `CANDIDATAS.md`.
- `vectra-risk-gitops/values/<env>/` para U2 (M1).
- Cambiar los values, los charts, los renders o las políticas de `identity-edge/`, salvo lo que exija una regresión de U1 (ver arriba).
- Las waves 5 y 6 de otras unidades.
- Las decisiones de staging y prod sobre MinIO y K11 (issue 26).
- Cualquier `kubectl`, `argocd app sync` o acción contra un clúster o contra Docker.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 12 y sus notas)
- `aidlc-docs/construction/identity-edge/infrastructure-design/deployment-architecture.md` (§2, orden de instalación)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, INF-U2-05a)
- `aidlc-docs/construction/platform-foundation/nfr-design/logical-components.md` y `aidlc-docs/construction/platform-foundation/infrastructure-design/deployment-architecture.md` (P-U1-12)
- `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/generate.py`, `vectra-risk-gitops/README.md`
- `platform/tests/test_waves.py`, `platform/tests/test_platform.py`, `platform/tests/integration.py`, `platform/tests/test_integration.py`
- `platform/policies/kyverno/disallow-argocd-auto-sync.yaml` y `platform/Makefile` (`check-local`)
- `identity-edge/Makefile` (los targets `render-*` y `check-*-rendered`)
- `tareas/U02-T11-rate-limit-y-valkey.md` (dónde corre `envoy-ratelimit`)

## Criterios de aceptación

Todos los comandos se corren desde `vectra-risk/`.

- [ ] **CA-1** — Las Applications versionadas son las que genera `components.yaml`, con las siete entradas nuevas en los tres entornos.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && \
  for env in kind staging prod; do for app in valkey keycloak api-gateway rate-limit identity-rules identity-monitors identity-jobs; do \
    test -f vectra-risk-gitops/apps/$env/$app.yaml || echo "falta $env/$app"; done; done
  ```
  Esperado: exit 0 y ninguna línea `falta`.

- [ ] **CA-2** — Cada Application está en su wave y el orden respeta las dependencias.
  ```bash
  uv run python platform/tests/test_waves.py
  ```
  Esperado: exit 0. La bitácora muestra el rojo de cada par nuevo de `STRICT` en una copia con la wave invertida.

- [ ] **CA-3** — Ninguna Application nueva sincroniza sola.
  ```bash
  for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env || exit 1; done
  platform/.tools/bin/kyverno test platform/policies/kyverno
  ```
  Esperado: exit 0, `fail: 0` en los tres entornos. La bitácora muestra el `fail` con `syncPolicy.automated` agregado a una Application nueva en una copia.

- [ ] **CA-4** — Cada Application de directorio ve YAML de Kubernetes que existe, y ningún recurso está en dos Applications del mismo entorno.
  ```bash
  uv run pytest platform/tests/test_platform.py platform/tests/test_integration.py -q
  ```
  Esperado: 0 failed. Hay un caso nuevo para el recurso repetido, y la bitácora lo muestra en rojo con un `ServiceMonitor` duplicado en una copia.

- [ ] **CA-5** — U2 sigue en verde.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: exit 0.

- [ ] **CA-6** — U1 sigue cumpliendo, ahora viendo los manifiestos de U2. Va en serie, después de CA-5.
  ```bash
  make -C platform check-local
  ```
  Esperado: exit 0.

## Plan de pruebas

- Rojo primero: correr CA-1 y `test_waves.py` antes de las entradas nuevas; registrar qué falla.
- El caso del recurso repetido (CA-4), con su rojo.
- Las mutaciones de CA-2 y CA-3.

## Notas

- Archivos que se modifican en su sitio: `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/generate.py` (solo si hace falta un tipo de cluster), `vectra-risk-gitops/README.md`, `vectra-risk-gitops/apps/**` (los escribe `generate.py`, no a mano), `platform/tests/test_waves.py` y `platform/tests/test_platform.py`. Más la bitácora `bitacoras/U02-T18.md`.
- `generate.py` sin `--check` borra y reescribe `apps/` y `envs/`: córrelo y revisa el `git diff` de `envs/`, que no debe cambiar.
- El plan (`aidlc-docs/…/identity-edge-code-generation-plan.md`) no se toca: el orquestador marca el Paso 12.
- Lo que encuentres fuera de alcance va a la sección de candidatas de tu bitácora.

## Enmienda del 2026-11-07, después de la ronda 1 (decisión M4 del usuario)

CA-6 falló en `test_kind_profile.py`: con U2, las requests de memoria de kind suman 5,47 GiB contra `BUDGET_GIB = 5.0`. El arbitraje está en `revisiones/U02-T18/arbitraje-ronda-1.md`.

**M4**: las requests de **memoria** de los componentes de U2 se bajan **solo en kind** hasta que el perfil quepa, sin cambiar `BUDGET_GIB` ni las requests de staging y prod (INF-U2-06).

- **Dentro** (amplía «Fuera»): los values y los archivos de kind de donde salen esas requests, con su render regenerado por el target `render-*` correspondiente y sin editarlo a mano. Por ejemplo `identity-edge/keycloak/values/kind.yaml`, `identity-edge/charts/valkey/values/kind.yaml`, `identity-edge/gateway/values/kind.yaml` (y `route-gen` si el EnvoyProxy sale de ahí) y `platform/operators/envoy-gateway-kind.yaml` (`envoy-ratelimit`).
- Las requests de **CPU** y todos los **limits** no cambian. Keycloak conserva un limit con el que `-XX:MaxRAMPercentage=70` le deja heap para arrancar.
- Cada request nueva lleva al lado un comentario `# kind (M4): …` con el valor de staging y prod.
- Si alguna política de U1 o de U2 exige una request mínima o una relación request/limit que M4 rompe, **detente y repórtalo**.

Criterios adicionales:

- [ ] **CA-7** — El perfil cabe y las requests de staging y prod no cambiaron.
  ```bash
  uv run pytest platform/tests/test_kind_profile.py -q && \
  git diff 0cf1238 -- identity-edge/keycloak/rendered/staging identity-edge/keycloak/rendered/prod identity-edge/charts/valkey/rendered/staging identity-edge/charts/valkey/rendered/prod identity-edge/gateway/generated/staging identity-edge/gateway/generated/prod --stat
  ```
  Esperado: 0 failed, y el `git diff` vacío. La bitácora trae una tabla con cada componente, su request de memoria en kind antes y después, el total del perfil y el margen que queda hasta 5,0 GiB.

CA-5 y CA-6 se vuelven a correr en serie, después de CA-7.

### Ampliación de M4 (2026-11-07, después de la ronda 2; decisión del usuario)

En la ronda 2 el codificador se detuvo, como pedía M4. `identity-edge/keycloak/policy/keycloak.rego:343-346` fija las requests exactas de INF-U2-06 en todos los entornos. Y el recorte solo puede venir de Keycloak: Valkey y Sentinel suman 0,50 GiB, y Envoy no cuenta en `test_kind_profile.py`.

- **Dentro**:
  - la request de memoria de Keycloak baja a **512 Mi solo en kind**;
  - `keycloak.rego` acepta esa request únicamente cuando el render es de kind. En staging y prod sigue exigiendo los valores exactos de INF-U2-06;
  - la regla nueva lleva casos de conftest que fallan en dos situaciones: con 512 Mi en staging o en prod, y con una request de kind distinta de 512 Mi;
  - las CPU, los limits, Valkey, Sentinel y `valkey.rego` no cambian.
- El margen esperado es ≈ 0,03 GiB. El presupuesto de kind para U3 a U12 ya está en `CANDIDATAS.md`; no lo resuelvas aquí.
- El rojo de cada caso nuevo de conftest va en la bitácora, sección «Ronda 3».
- CA-7, y después CA-5 y CA-6 en serie.
