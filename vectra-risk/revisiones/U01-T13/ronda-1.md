VEREDICTO: VERDE

# Ronda 1 — U01-T13

Revisada `293f0ac` en tres copias privadas (como la CI, para mutaciones y fusionada con U02-T23), ya borradas. Nada contra `kind-vectra`. El worktree del codificador quedó limpio. Mientras se revisaba, el PR #181 se fusionó (`2752490`); las comparaciones «contra main» usan `656c0b7`, la merge-base.

**[E]** = ejecutado por el revisor. **[L]** = solo leído.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| CA-1 | Todo HPA de kind con max = min | suite `platform` entera; mutación: `decision-registry/chart/values-kind.yaml` con max 6 y el `envoyHpa` de kind con max 2 | pasa [E]. La mutación da `1 failed`: `['vectra-app/decision-registry-service min 2 max 6', 'vectra-edge/api-gateway-data-plane min 1 max 2']` |
| CA-2 | EnvoyProxy de kind con 1 réplica; U2 en verde | `make -C identity-edge check-route-gen kubeconform-gateway policy-gateway xds-gateway`; `git diff --stat 656c0b7 HEAD -- identity-edge/gateway/generated` | rc 0 [E]: `14061 passed`, 3×`42 passed`, kubeconform 3×32 válidos. Solo cambia `generated/kind/envoyproxies.yaml` (3 líneas) |
| CA-3 | `policy-chart` de las unidades tocadas | `make -C <u> policy-chart` para las 5 unidades; en console, con `node_modules` de `npm ci --offline` en la copia | pasan U3, U4, U7 y U8 [E]. Console: conftest y kubeconform pasan, vitest `chart-config` da 10 passed, y `test_chart.py` da `1 failed, 179 passed`; ese fallo ya existía en main (punto 10) |
| CA-3b | Render de staging y prod idéntico al de main | `integration.py --env {staging,prod,kind}` de los 4 charts en `656c0b7` y en HEAD, con `diff -r` | staging y prod idénticos byte a byte [E]. En kind solo cambia `maxReplicas: 6 → 2` |
| CA-4 | Presupuesto a lo medido | `pytest platform ...` entero (copia tipo CI) | `952 passed in 222s`, sin skips [E] |
| CA-5 | `generate.py --check` y `check-local` | paso a paso (ruff, network/quotas `--check`, helm lint, traceability, runbooks, waves, links) | rc 0 [E]: 618 Markdown sin enlaces rotos |
| CA-6 | README con 14,8 GiB | `pytest system-verification/... -k readme`, y otra vez con el README de main | `9 passed`; con el README de main, `1 failed` [E] |

## Comprobado aparte
- **Como lo corre la CI [E].** Sin `platform/.tools` en el árbol ni en el PATH, `uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider` da **952 passed**. Kyverno sí corre en la CI: `platform.yml` llama a `policies.yml`, que hace `make -C platform check` (incluye `check-tools`); en el log del job `policies` sobre `293f0ac` aparece `kind_serving_kyverno.py` con `pass: 2, fail: 0`.
- **Fusión con U02-T23 (`48c4b9f`) [E].** Conflicto solo en `CANDIDATAS.md`. `test_kind_profile.py` entero: **29 passed**. `make -C identity-edge policy-keycloak policy-gateway`: rc 0. Keycloak queda en HPA **1-4** y la prueba sigue pasando, porque `PENDING_UNBOUNDED` solo exige que pueda crecer. En cifras: cada réplica de Keycloak pide 1,0195 GiB y 0,52 CPU; si sube a 4, el pico pasa a **16,79 GiB y 12,225 CPU**, ≈ 1,98 GiB por encima de la máquina. `keycloak.rego:123-125` fija `maxReplicas` en 4.
- **Envoy con una réplica solo en kind [E].** Staging o prod con 1 réplica, con HPA 1-1 o con las dos cosas: falla `edge.rego`. Con la imagen de `kind-registry:5000/`: falla `set.rego` (`environment-issuer`), también con 1 réplica y HPA 1-1. En kind fallan 2 réplicas, HPA 1-2, 0 réplicas, HPA 0-0, la forma de staging y la imagen del banco. Para que staging o prod pasaran con 1 réplica habría que cambiar **tres cosas a la vez**: la imagen en los values, `envoy_scaling` y el mapa `images` de `set.rego`. Ningún objetivo de make evalúa `edge.rego` sin `set.rego`. Ningún job de la CI corre `policy-gateway` (ya era así).
- **HPA de kind [E].** Los 7 de U3, U4, U7, U8 y U10 en 2-2; el data plane de Envoy en 1-1; Keycloak en 2-4 (1-4 tras U02-T23).
- **U7 y U8 con `data.env` [E].** Render de kind sin `--data`: falla (`maxReplicas es 6, no 2`), fallo cerrado. Render de prod o staging con `--data kind`: falla (`es 2, no 6`). Staging y prod exigen exactamente 6. La CI no evalúa estas políticas (ya era así).
- **Hallazgos de U01-T12 [E].** F-01: la mutación de `product-metrics/chart/files/product.json` a Loki da `1 failed`. F-02: `install.md` usa `uv run python` y la prueba ejecuta el texto tal cual. F-03: `MACHINE_GIB` lo usa `test_the_peak_fits_the_machine`. F-04: `job_cpu()` sale del render (1,42); `uncounted_cpu` = 2,07.
- **Pico de D2, con un guion propio [E].** Keycloak en 2: **14,7539 GiB y 11,185 CPU**. Keycloak en 1: **13,7344 GiB** y **10,665 CPU** (no 10,585: F-02). Margen contra la máquina: 0,062 GiB.
- **Alcance [E].** Sin cambios en `identity-edge/keycloak/`, `DECISIONES-LOOP.md` ni código de unidades; en `system-verification/` solo la frase del README.
- **Lo que el codificador no comprobó [E].** El paso vitest pasa (10 tests). El fallo `KeyError: 'port'` de `test_flows_f10…` existe en `656c0b7`; lo introdujo `8938a23` (2026-11-13, U01-T09: entrada F60 con `ports: [8081, 4191]`).

## Hallazgos
### F-01 · AMARILLO · `platform/tests/test_kind_profile.py:60` y `bitacoras/U01-T13.md:55` · 15535356 / 1024² = 14,8157, no 14,8166 (solo comentarios)
### F-02 · AMARILLO · `bitacoras/U01-T13.md:51` · La CPU con Keycloak en 1 es 10,665, no 10,585 (el proxy de kind pide 20m)
### F-03 · AMARILLO · `platform/tests/test_kind_profile.py:422` · `test_kind_serving_render_passes_the_kyverno_hpa_bounds_policy` ya no ejecuta Kyverno: solo comprueba la receta
### F-04 · AMARILLO · `identity-edge/gateway/policy/edge.rego:349` · El literal `"kind-registry:5000/"` duplica el de `set.rego`

## Tareas candidatas
- **U1/U2:** el `maxReplicas` de Keycloak en kind (puede llevar el pico a 16,79 GiB). Urge con U02-T23 en main.
- **U12:** «14 GiB como mínimo» en el README, fijado por `test_demos_closed_world.py:1181`.
- **U3/U4:** `hpa-doc` exige 6 (`decision-registry/chart/policy/service.rego:458`, `governance/.../service.rego:515`) y fallaría sobre el render de kind; hoy no se evalúa sobre kind.
- **U2 (ya existía):** `envoy-scaling` deja pasar un `EnvoyProxy` sin `replicas` o con el HPA sin `maxReplicas`.
- **U10/U1:** el flujo F60 con `ports:` rompe `test_flows_f10…` de console desde `8938a23`.
- **CI:** ningún workflow corre `identity-edge policy-gateway` ni los `policy-chart` de U3, U4, U7, U8 y U10.

```
VEREDICTO: VERDE
AMARILLO|platform/tests/test_kind_profile.py:60|MACHINE_GIB son 14,8157 GiB, no 14,8166 (comentario y bitácora)
AMARILLO|bitacoras/U01-T13.md:51|CPU con Keycloak en 1 es 10,665, no 10,585
AMARILLO|platform/tests/test_kind_profile.py:422|la prueba se llama «passes the kyverno policy» y ya no ejecuta Kyverno
AMARILLO|identity-edge/gateway/policy/edge.rego:349|literal kind-registry:5000/ duplicado de set.rego
INFORME: revisiones/U01-T13/ronda-1.md
```
