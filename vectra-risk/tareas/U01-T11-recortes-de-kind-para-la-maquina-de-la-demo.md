# U01-T11 — Recortes de kind para que el sistema completo quepa en la máquina de la demo

**Unidad:** U1 — `platform-foundation` (con values de kind de U2 y de U6)
**Historias que implementa:** ninguna nueva; hace que el perfil de kind quepa en la máquina de la demo (auditoría entre unidades del 2026-11-14).
**Depende de:** U01-T10 (esta rama nace de `tarea/U01-T10`: usa su prueba de presupuesto, que ya cuenta las réplicas mínimas de los HPA)

---

## Alcance

**Dentro:**

> La máquina de la demo tiene 15 GiB de RAM y 8 núcleos, que los tres nodos de kind comparten. Tras U01-T10 el perfil completo pide 13,4 GiB de memoria en el peor momento (promoción de U6), y la auditoría calculó ≈ 11,4 CPU pedidos sin InferenceService y ≈ 19 en el pico de D2, contra 16 programables (2 workers × 8): el segundo modelo de D2 quedaría `Pending`. El usuario aprobó el 2026-11-14 estos recortes, **solo en kind**:
>
> 1. **Sin Tempo, Loki ni Alloy en kind.** `install.md` ya permite dejarlos para el final; ahora no se instalan. Sus Applications salen de kind (o quedan fuera del orden de instalación de la demo, con una forma explícita de activarlas), y lo que dependa de ellos en kind no queda roto: fuentes de datos de Grafana, `otel-collector` (exportadores), reglas y monitores, flujos de red, `ExternalSecret` y usuarios de MinIO que solo servían a ellos.
> 2. **Keycloak con una réplica en kind.** Hoy su HPA pide mínimo 2 (`identity-edge/keycloak/values/common.yaml:38`) y eso cuesta ≈ 1 GiB.
> 3. **Menos CPU reservada.** El request de CPU del proxy de Linkerd en kind (`platform/mesh/linkerd-kind.yaml`; hoy 100m por pod en ≈ 48 pods) baja a un valor justificado (la auditoría propone 10m a 20m), y el request de CPU de los pods de serving en kind (`vectra-risk-gitops/values/kind/model-serving.yaml`; hoy 500m) baja a ≈ 100m. Los limits no bajan.
>
> `BUDGET_GIB` y la prueba del presupuesto reflejan la cifra nueva, y hay una prueba equivalente para la CPU pedida frente a lo programable en kind.

**Antes de recortar, comprueba y, si algo choca, PARA y devuélvelo como pregunta con las opciones:**

- **¿Alguna demo o U12 lee Loki o Tempo?** `system-verification/src/vectra_verification/clients/loki.py` existe y la guía de U12 lista el selector de Loki (K-20). Busca qué sección de la CLI, qué `verify`, qué paso de una demo (`system-verification/demos/`) y qué panel del dashboard de producto los usan. Si alguno lo necesita para pasar, ese componente **no** se quita: dilo y recorta el resto.
- **¿Las políticas admiten Keycloak con una réplica?** `platform/policies/kyverno/require-hpa-bounds.yaml` y `require-pdb` pueden exigir mínimo 2. Si lo exigen para Keycloak, no relajes la política por tu cuenta.
- **¿Algo más depende de 2 réplicas de Keycloak?** (PDB, caché distribuida, pruebas de U2).

**Fuera** (recházalo aunque lo veas roto):

- Bajar a una réplica los servicios de U3 a U11 o los InferenceService: es una excepción distinta, que el usuario no ha aprobado.
- Staging y prod: no cambian. Compruébalo comparando su render con el de `origin/main`.
- Cualquier cosa de U01-T10 (ya está en esta rama): no la rehagas.
- Argo CD sin dex, notifications ni applicationset: candidata, no entra.
- El gateway, las imágenes y los digests.

---

## Archivos de contexto

- `platform/tests/test_kind_profile.py`, `platform/mesh/linkerd-kind.yaml` y `linkerd-values.yaml`, `platform/observability/values/*-kind.yaml`, `platform/runbooks/install.md`, `platform/network/` (flujos), `platform/policies/kyverno/`
- `vectra-risk-gitops/` (`components.yaml`, `generate.py`, `apps/kind`, `values/kind/model-serving.yaml`), `model-serving/chart/values.yaml`
- `identity-edge/keycloak/values/common.yaml` y `kind.yaml`, `identity-edge/keycloak/rendered/kind/`, `identity-edge/Makefile`
- `system-verification/src/vectra_verification/clients/`, `system-verification/demos/`, `product-metrics/` (dashboard)
- `DECISIONES-LOOP.md` §7, §9 y §10 (presupuesto de memoria y excepciones de kind), `CANDIDATAS.md`
- `bitacoras/U01-T10.md` (cómo se compone el 13,4)

---

## Criterios de aceptación

- [ ] **CA-1** — En kind no se instalan Tempo, Loki ni Alloy (los que la comprobación previa permita quitar), y nada en kind los referencia roto.
  ```bash
  cd vectra-risk && uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py && uv run python platform/network/generate.py --check
  ```
  Esperado: rc 0; `kind:` con las Applications que correspondan; una prueba nueva falla si una fuente de datos de Grafana, un exportador del colector o un flujo de red de kind apunta a un componente que kind ya no instala.

- [ ] **CA-2** — Keycloak rinde con una réplica mínima en kind y cumple las políticas; staging y prod siguen con 2.
  ```bash
  cd vectra-risk && make -C identity-edge render-keycloak && git diff --stat -- identity-edge/keycloak/rendered && grep -n -E 'minReplicas|replicas:' identity-edge/keycloak/rendered/kind/keycloak.yaml
  ```
  Esperado: solo cambia el render de kind; la bitácora trae el resultado de Kyverno sobre ese render. (Ajusta el objetivo de `make` si se llama distinto y dilo.)

- [ ] **CA-3** — La CPU pedida en kind cabe en lo programable, también en el pico de D2 (dos InferenceService en `vectra-serving`, uno en `vectra-staging` y el Job de validación).
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "cpu"
  ```
  Esperado: pasa, con una prueba nueva que suma los requests de CPU del perfil de kind (pods y proxies, réplicas mínimas de los HPA) y la compara con un tope declarado y justificado; contra `main` falla.

- [ ] **CA-4** — El presupuesto de memoria baja a lo medido tras los recortes.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k budget
  ```
  Esperado: pasa con el `BUDGET_GIB` nuevo; la bitácora desglosa cuánto ahorra cada recorte. Di también lo que la prueba sigue sin contar (data plane de Envoy, controlador de Envoy Gateway, ratelimit, Jobs) y su estimación.

- [ ] **CA-5** — Staging y prod no cambian.
  ```bash
  cd vectra-risk && make -C platform render && git diff --stat origin/main -- platform/rendered/staging platform/rendered/prod
  ```
  Esperado: las únicas diferencias son las de U01-T10 (la política de MinIO), ninguna de esta tarea.

- [ ] **CA-6** — `install.md` dice lo que kind instala ahora y cómo volver a activar lo recortado; `DECISIONES-LOOP.md` no se toca (lo anota el orquestador).
  ```bash
  cd vectra-risk && uv run python platform/tests/test_runbooks.py --operational && uv run python platform/tests/test_links.py
  ```
  Esperado: rc 0.

- [ ] **CA-7** — Todo sigue en verde.
  ```bash
  cd vectra-risk && make -C platform check-local
  ```
  Esperado: rc 0. Si tocas `identity-edge` o `model-serving`, corre además sus pruebas de chart o de render (no sus suites con contenedores) y dilo.

---

## Plan de pruebas

- Prueba de referencias colgantes en kind (CA-1).
- Prueba de la CPU pedida frente a lo programable (CA-3).
- Presupuesto de memoria con la cifra nueva (CA-4).

**Rojo primero:** cada prueba nueva se ve fallar antes del cambio; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** No levantes contenedores. La máquina tiene poca memoria libre.
- En el clúster real Tempo, Loki y Alloy están instalados hoy; retirarlos es una operación del operador (borrar las Applications con sus recursos). Escribe ese paso en `install.md`, no lo ejecutes.
- El scratchpad es compartido entre agentes: nombra tus archivos temporales con el prefijo `u01t11-`.
- Se modifican en su sitio los archivos citados. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
