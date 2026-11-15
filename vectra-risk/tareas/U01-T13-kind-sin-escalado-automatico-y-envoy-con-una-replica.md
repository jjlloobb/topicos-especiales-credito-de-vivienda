# U01-T13 — En kind ningún HPA puede crecer más allá de lo contado, y el gateway de Envoy corre con una réplica

**Unidad:** U1 — `platform-foundation` (con values de kind de U2, U3, U4, U7, U8 y U10)
**Historias que implementa:** ninguna nueva; decisiones del usuario del 2026-11-14 para que el pico de la demo D2 quepa con margen en la máquina de 15 GiB.
**Depende de:** U01-T12 (esta rama nace de `tarea/U01-T12`, en revisión). U02-T23 (Keycloak con una réplica en kind) está en su propio PR y no se toca aquí.

---

## Alcance

**Dentro:**

> 1. **Ningún HPA de kind puede escalar más allá de lo que el presupuesto cuenta.** U01-T12 lo cerró para serving (`maxReplicas` = `minReplicas` en kind). Queda el mismo riesgo en los HPA de los Deployments de U3 a U11 y en Keycloak: el presupuesto los cuenta a `minReplicas`, y si todos subieran a su máximo serían +7,51 GiB y +7,32 CPU (bitácora de U01-T12, candidata 1). En kind, y solo en kind, cada HPA queda con `maxReplicas` igual a su `minReplicas`. Ya hay un precedente: `console/chart/bff/values-kind.yaml` (`maxReplicas: 2`). Alcanza a todos los HPA que rinde el perfil de kind: `decision-registry`, `governance`, `scoring-service`, `explainability-service`, `case-service`, `case-worker`, `console-bff` (ya está), Keycloak (su máximo; el mínimo es de U02-T23) y cualquier otro que encuentres: lístalos a partir del render, no de esta lista.
> 2. **Una prueba lo garantiza para todos, también los futuros:** en `platform/tests/test_kind_profile.py`, todo HPA del render de kind tiene `maxReplicas == minReplicas`, o el presupuesto lo cuenta a `maxReplicas`. Un HPA nuevo que pueda crecer sin estar contado hace fallar la prueba.
> 3. **El data plane de Envoy corre con una réplica en kind.** Hoy el `EnvoyProxy` de kind pide 2 réplicas y HPA de 2 a 6 (`identity-edge/gateway/generated/kind/envoyproxies.yaml:64-74`): ≈ 0,30 GiB y 0,13 CPU por réplica. En kind pasa a 1 réplica fija (mínimo y máximo 1). Staging y prod no cambian.
> 4. `BUDGET_GIB` y `CPU_BUDGET` bajan a lo medido, con el desglose en la bitácora (con Keycloak en 2 y en 1).
> 5. **El README de system-verification dice la cifra del presupuesto.** `system-verification/tests/unit/test_demos_closed_world.py::test_readme_has_the_prerequisites…` compara la memoria que anuncia `system-verification/README.md` con `BUDGET_GIB`; cada vez que el presupuesto cambia, esa prueba se rompe en `main`. Actualiza esa cifra del README (y solo esa frase) al `BUDGET_GIB` que fijes, y deja que siga siendo verdad lo que dice de la máquina necesaria.

**Antes de cambiar nada, comprueba y, si algo choca, PARA y devuélvelo como pregunta con las opciones:**

- **Envoy con una réplica.** Qué lo exige en 2: la política de U2 (`identity-edge/gateway/policy/edge.rego`), Kyverno (`require-hpa-bounds`, `require-spread-and-pdb`: el Deployment lo crea Envoy Gateway en tiempo de ejecución), el PDB, las pruebas de U2 y el generador de rutas (`route-gen`). Si una política lo exige sin distinguir entorno, hazla sensible al entorno **con la misma señal `is_kind` que U02-T23 usa para Keycloak** (lee `identity-edge/keycloak/policy/set.rego` en `origin/tarea/U02-T23`) o con la que la política del gateway ya tenga; no la relajes para staging ni prod. Si no hay forma limpia, para y pregunta.
- **Las políticas de cada unidad** (conftest/rego y pruebas de chart de U3, U4, U7, U8, U10) que supongan `maxReplicas > minReplicas` o un máximo concreto: ajústalas solo para kind, o di por qué no aplican a kind.
- **Kyverno `require-hpa-bounds`:** que `maxReplicas == minReplicas` cumple para Deployment.

**Fuera:**

- Bajar `minReplicas` de ninguna unidad (siguen en 2; la excepción de una réplica es solo Envoy aquí y Keycloak en U02-T23).
- `identity-edge/keycloak/` salvo el `maxReplicas` de su HPA en kind; si eso choca con lo que U02-T23 cambia en la política de Keycloak, déjalo fuera y dilo (lo resuelvo yo al fusionar).
- Código de las unidades, límites de memoria, M1 inactivo antes de M2, el request del Job de validación.
- Staging y prod: su render no cambia ni un byte en ninguna unidad.
- `system-verification/` (salvo la frase del README del punto 5) y `DECISIONES-LOOP.md`.

---

## Archivos de contexto

- `platform/tests/test_kind_profile.py`, `bitacoras/U01-T12.md`, `tareas/U01-T12-…`
- `vectra-risk-gitops/values/kind/*.yaml`, `vectra-risk-gitops/apps/kind/`, `generate.py`
- Charts y values: `decision-registry/chart`, `governance/chart`, `scoring-explainability/chart`, `case-management/chart`, `console/chart/bff` (precedente), `bias-monitoring/chart`, `product-metrics/chart`
- `identity-edge/gateway/` (`generated/kind/envoyproxies.yaml`, el generador, `policy/edge.rego`), `identity-edge/Makefile`
- `platform/policies/kyverno/require-hpa-bounds.yaml` y `require-spread-and-pdb`
- `DECISIONES-LOOP.md` §7, §9, §10; `CANDIDATAS.md`

---

## Criterios de aceptación

- [ ] **CA-1** — En el render de kind, todo HPA tiene `maxReplicas == minReplicas`.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "hpa"
  ```
  Esperado: pasa, con la prueba nueva; contra la base (`tarea/U01-T12`) falla y lista los HPA que podían crecer. Mutación: un HPA de kind con máximo 6 la hace fallar.

- [ ] **CA-2** — El `EnvoyProxy` de kind pide una réplica; los de staging y prod no cambian; las políticas de U2 pasan.
  ```bash
  cd vectra-risk && make -C identity-edge check-route-gen kubeconform-gateway policy-gateway xds-gateway && git diff --stat tarea/U01-T12 -- identity-edge/gateway/generated
  ```
  Esperado: rc 0; solo cambia `generated/kind/`. Ajusta los objetivos al nombre real y dilo.

- [ ] **CA-3** — Las pruebas de chart y las políticas de cada unidad tocada siguen en verde, y su render de staging y prod es idéntico al de la base.
  ```bash
  cd vectra-risk && for u in decision-registry governance scoring-explainability case-management console; do make -C $u policy-chart || echo "FALLA $u"; done
  ```
  Esperado: ninguna «FALLA». Ajusta el objetivo por unidad (no todas lo llaman igual) y dilo; no corras las suites con contenedores.

- [ ] **CA-4** — El presupuesto baja a lo medido.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib
  ```
  Esperado: pasa entero. La bitácora da el pico de D2 con Keycloak en 2 y en 1, frente a 15 GiB.

- [ ] **CA-6** — El README de system-verification anuncia el presupuesto nuevo.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_demos_closed_world.py -q -p no:cacheprovider -k "readme"
  ```
  Esperado: pasa; antes del cambio del README, falla. Si `main` trae otra cifra en el README cuando fusiones o rebases, la que vale es la de tu `BUDGET_GIB`.

- [ ] **CA-5** — Todo sigue en verde.
  ```bash
  cd vectra-risk && uv run python vectra-risk-gitops/generate.py --check && make -C platform check-local
  ```
  Esperado: rc 0.

---

## Plan de pruebas

La prueba general de los HPA de kind (CA-1) y lo que cada política necesite. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** La máquina tiene poca memoria y hay otros agentes trabajando: suites pesadas una sola vez; nada de suites de integración con contenedores salvo `check-local` de `platform`.
- `platform/.charts` y `platform/.tools` no están versionados: cópialos del worktree `u01-t12`. No descargues imágenes.
- Scratchpad compartido: prefijo `u01t13-`. `CANDIDATAS.md`: solo añadir al final.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
