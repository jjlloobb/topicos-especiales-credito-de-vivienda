VEREDICTO: VERDE

# Ronda 1 — U02-T23

Todo se comprobó con ejecuciones del revisor en una copia (`git archive c9ed403`), con `platform/.charts` copiado. El worktree quedó limpio; ningún contenedor nuevo; nada contra `kind-vectra`.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | Render de kind con `minReplicas: 1`; staging y prod sin cambios | `make -C identity-edge render-keycloak` en la copia de la rama y en otra de `origin/main` (ab734dd), con `cmp` y `diff` archivo por archivo | pasa. `staging/keycloak.yaml` y `prod/keycloak.yaml` idénticos byte a byte a main; `kind/config-cli-realm.yaml` también. `kind/keycloak.yaml` solo difiere en la línea 175 (`2` → `1`). El render fresco es igual al versionado. kind:175=1, staging:160=2, prod:160=2 |
| 2 | La política acepta 1 solo en kind, 2 en staging y prod, y rechaza 0 y 3 | `policy-keycloak` y `policy-keycloak-u1` dentro de `make check`; matriz propia con conftest | pasa. kind 0/2/3 FALLA, kind 1 PASA; staging y prod 0/1/3 FALLA, 2 PASA, todos por `hpa-min-replicas` |
| 3 | PDB, alertas y pruebas coherentes | `check-keycloak-rendered` y `rules` dentro de `make check` | pasa (`promtool` SUCCESS) |
| 4 | `make -C identity-edge check` | una sola corrida entera, con los charts presentes | **rc=0**. 2830 passed en 1228,94 s, 0 skipped, 0 xfail. Corrieron todos los objetivos, incluidos `schemas-gateway`, `kubeconform-gateway`, `render-envoy-gateway` y `policy-ratelimit` |

## Intentos de romper la política (ejecutados)

- **(a)** staging y prod con `minReplicas: 1`: FALLA por `hpa-min-replicas`.
- **(b)** staging o prod con 1 y el `KC_HOSTNAME` de kind: FALLA por `issuer-per-environment`, `config-cli-only-kind`, `documents-exact`, `bootstrap-admin` y `env-whitelist`. Con la CA interna añadida sigue fallando por las demás. Con los 6 documentos solo de kind y las 2 variables `KC_BOOTSTRAP_ADMIN_*` añadidas, PASA: ese render ya es exactamente el de kind.
- **(b), por values** (sobre `staging.yaml`): hacen falta `autoscaling.minReplicas: 1`, `vectra.publicHostname: vectra.localtest.me`, `vectra.tls.issuerRef: vectra-internal-ca` y el bloque `vectra.configCli` entero, más `--set-file vectra.configCli.realm=…` y la separación del realm, que el Makefile solo hace en kind. Son 4 claves de values más un cambio de Makefile, y el resultado es un «staging» que sirve en `vectra.localtest.me`, es decir, que no funciona como staging. **No es un descuido plausible: es un cambio deliberado.**
- **(c)** HPA de kind con 0, 2 o 3: FALLA. Con 1: PASA.
- **(d)** HPA sin `minReplicas`, en los 3 entornos: FALLA por `hpa-min-replicas`.
- **(e)** Un segundo HPA `keycloak-extra` con min 1: FALLA por `documents-exact`. El HPA renombrado: FALLA por `documents-exact` y `present`.
- **(f)** `spec.replicas` en el StatefulSet: FALLA siempre por `statefulset-spec`.
- **(g)** Sin `--combine`, staging y prod con min 1 PASAN la pasada de `keycloak.rego` sola; con `--combine` FALLAN. El único que evalúa la política es `make policy-keycloak` (las dos pasadas, líneas 87-91 del Makefile), igual que el helper `kd.conftest` de las pruebas. **Ningún workflow de `.github/workflows` evalúa la política de identity-edge**: `platform.yml` solo llama a `make -C platform check` y a pytest de `platform`. Eso ya pasaba antes de este cambio. Ver F-01.

## Comprobación previa del codificador
- **PDB:** `minAvailable 1` (leído). Con 1 réplica, un `drain` se queda esperando; registrado como candidata.
- **Caché:** `KC_CACHE_STACK=jdbc-ping` (leído); ninguna regla exige 2 miembros.
- **`topologySpreadConstraints`:** `zone-spread` no mira las réplicas (leído).
- **Alertas:** ninguna usa `< 2`; `KeycloakDown` es `replicas_ready == 0` con `for: 1m`; `promtool` pasa (ejecutado). Ver F-02.
- **Kyverno** (leído): `require-hpa-bounds` y `require-spread-and-pdb` solo miran `Deployment` e `InferenceService`; `platform/policies/rego/hpa.rego` solo mira HPA cuyo destino es un `Deployment`.
- **e2e e integración:** solo se recolectan dentro de `check` (ejecutado, rc 0).

## Alcance
El diff toca solo `identity-edge/` (values de kind, `keycloak.rego`, `set.rego`, el render de kind y la prueba), la bitácora, la tarea y `CANDIDATAS.md` (1 inserción al final: la candidata del PDB con drain). No toca `platform/` ni `DECISIONES-LOOP.md`.

## Hallazgos

### F-01 · AMARILLO · `identity-edge/keycloak/policy/keycloak.rego:108-110` · El mínimo de réplicas ya no se vigila en la pasada por documento
Antes `keycloak.rego` exigía min 2 por sí solo; ahora la regla solo vive en `set.rego` (`--combine`). Ningún consumidor corre hoy solo esa pasada. Queda un marcador `# regla: replicas` sin regla debajo (línea 108), duplicado con el de `set.rego:111`.

### F-02 · AMARILLO · `identity-edge/keycloak/values/kind.yaml:5-8` y la bitácora · Con 1 réplica, cada reinicio de Keycloak en kind es una caída
Con 1 réplica, un rollout o el reinicio del pod deja `replicas_ready == 0`: `KeycloakDown` (`for: 1m`) y `KeycloakMetricsDown` pueden dispararse si el arranque supera ese tiempo, y el login de toda la demo cae mientras tanto. Razonado, no ejecutado.

### F-03 · AMARILLO · `identity-edge/tests/unit/test_keycloak_deploy.py`, `MIN_REPLICAS` (≈ línea 579) · El 2 de staging y prod está escrito a mano
Antes se comparaba con `kd.design_replicas()[0]`. Mejor derivarlo del diseño.

## Para el orquestador
`platform/tests/test_kind_profile.py:234` en `origin/main` afirma `minimums[("StatefulSet","keycloak")] == 2`: al fusionar esta rama esa prueba falla y la CI `platform.yml` sale en rojo, hasta el ajuste de U01-T12.

## Tareas candidatas
- Ningún workflow de CI evalúa las políticas, renders ni pruebas de identity-edge: `platform.yml` solo cubre `platform`.
- `charts.sh` no baja `envoy-gateway/gateway-helm` ni `keycloakx`; sin ellos `make -C identity-edge check` no corre en un árbol limpio.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/keycloak/policy/keycloak.rego:108-110|El mínimo de réplicas ya no se vigila en la pasada por documento; queda un marcador `regla: replicas` sin regla
AMARILLO|identity-edge/keycloak/values/kind.yaml:5-8|Con 1 réplica cada reinicio en kind es una caída y KeycloakDown puede dispararse
AMARILLO|identity-edge/tests/unit/test_keycloak_deploy.py:MIN_REPLICAS|El 2 de staging y prod está escrito a mano en vez de salir del diseño
INFORME: revisiones/U02-T23/ronda-1.md
```
