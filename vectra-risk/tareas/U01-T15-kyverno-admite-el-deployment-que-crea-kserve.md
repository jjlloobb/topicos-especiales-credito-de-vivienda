# U01-T15 — Kyverno admite el Deployment que KServe crea para el modelo activo

**Unidad:** U1 — `platform` (costura con U6, `model-serving`)
**Historias que implementa:** ninguna nueva; cierra un defecto hallado en la auditoría entre unidades del 2026-11-16, antes de desplegar el modelo de referencia en `kind-vectra`.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> La regla `require-min-replicas` de `platform/policies/kyverno/require-spread-and-pdb.yaml` (líneas 13 a 35) exige `spec.replicas: ">=2"` en todo `Deployment` de `vectra-serving`, en `Enforce`. Solo exime al modelo inactivo y al data plane de Envoy Gateway.
>
> El perfil `prod` del `InferenceService` de U6 lleva HPA (`model-serving/chart/templates/inferenceservice.yaml`, líneas 33 a 58: la anotación `serving.kserve.io/autoscalerClass: none` solo se pone en `staging` e `inactive`). **Según el código fuente de KServe v0.21.0** (la versión de `vectra-risk-gitops/components.yaml`; `pkg/controller/v1beta1/inferenceservice/reconcilers/deployment/deployment_reconciler.go`, ≈ líneas 173 y 174), el controlador solo fija `spec.replicas` del Deployment cuando la clase de autoescalado es `none`; con HPA lo deja sin fijar y el API lo deja en 1. Es el mismo comportamiento que la propia política documenta para Envoy Gateway. Kyverno rechazaría entonces el Deployment del modelo activo: el `InferenceService` no quedaría `Ready`, y sin modelo no hay flujo base, D1 ni D2.
>
> **No está medido en un clúster** (U6 nunca corrió en kind; hoy no hay ningún `InferenceService`). El fixture `platform/policies/kyverno/fixtures/resources.yaml` (≈ línea 727, `kserve-predictor`) supone `replicas: 2`, por eso ninguna prueba lo ve.
>
> 1. **Confirma el comportamiento de KServe con su fuente**, sin clúster: lee el reconciliador de la versión exacta que fija `components.yaml` (puedes leer el código público de esa etiqueta; no descargues imágenes) y anota en la bitácora archivo, líneas y lo que hace con `replicas` en los tres perfiles (`prod` con HPA, `staging` e `inactive` con `autoscalerClass: none`), y también en una **actualización** (el rollback de D2 pasa una versión de `inactive`, 1 réplica, a `prod`). Si la fuente dice otra cosa que esta tarea, **para y dilo**: la tarea está mal.
> 2. **Fixture fiel.** Añade a los fixtures de Kyverno un `Deployment` como el que KServe genera para el perfil `prod` de kind: con las etiquetas y anotaciones que KServe copia del `InferenceService` (`serving.kserve.io/inferenceservice`, las `vectra.io/*` de la plantilla de U6), **sin** `spec.replicas`, y otro con `replicas: 1`. Parte del render real del chart de U6 con los values de kind (`helm template` de `model-serving/chart` con `vectra-risk-gitops/values/kind/model-serving.yaml`), no de un manifiesto inventado. Rojo primero: con la política de `main`, los dos fallan `require-min-replicas`.
> 3. **Exime de `require-min-replicas` los Deployment que KServe posee** (etiqueta `serving.kserve.io/inferenceservice`, acotado a `vectra-serving`), igual que se hizo con Envoy. El mínimo de 2 réplicas del modelo activo **no se pierde**: di qué regla lo sigue vigilando sobre el `InferenceService` (busca `active-inference-service-needs-two-replicas` y `require-hpa-bounds`) y demuéstralo con una mutación (un `InferenceService` `prod` con `minReplicas: 1` sigue rechazado).
> 4. **Barrido de la clase.** Evalúa **todas** las reglas de `platform/policies/kyverno/` (y las de `model-serving/` si las hay) contra los Deployment y Pod que KServe genera en `vectra-serving` y `vectra-staging` para los tres perfiles: `require-zone-spread`, `require-pdb`, `require-hpa-bounds`, `require-resources`, `require-priority-class`, `require-ro-rootfs`, `require-run-as-non-root`, `restrict-registries`, `disallow-latest`, `verify-images`, `require-criticality-label`. Incluye el init container `storage-initializer` (imagen, registro, etiqueta o digest, contexto de seguridad: `CANDIDATAS.md`, línea 839). Lo que falle y sea de la política, arréglalo aquí con su fixture; lo que sea de U6 o exija descargar algo, a `CANDIDATAS.md`.
> 5. Actualiza el comentario de la política y `platform/policies/kyverno/README.md` si describe la regla.

**Fuera:**

- Relajar el mínimo de 2 réplicas del modelo activo, el HPA o los PDB (decisión del usuario, `DECISIONES-LOOP.md` §7 y §11).
- El chart de U6 y sus values, salvo que el punto 1 demuestre que la tarea está mal.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `platform/policies/kyverno/require-spread-and-pdb.yaml`, `require-hpa-bounds.yaml`, `kyverno-test.yaml`, `fixtures/`, `README.md`
- `platform/tests/kind_serving_kyverno.py` (el patrón de U01-T13 para evaluar con Kyverno fuera de pytest), `platform/tests/test_kind_profile.py`, `platform/Makefile` (`check-tools`, `check-local`)
- `model-serving/chart/templates/inferenceservice.yaml`, `model-serving/chart/values.yaml`, `vectra-risk-gitops/values/kind/model-serving.yaml`, `model-serving/Makefile` (`policy-chart`, `policy-chart-u1`)
- `vectra-risk-gitops/components.yaml` (versión de KServe), `platform/operators/kserve.yaml`
- `CANDIDATAS.md` (líneas 834 a 839), `DECISIONES-LOOP.md` §7 y §11

---

## Criterios de aceptación

- [ ] **CA-1** — Las pruebas de Kyverno pasan con los fixtures nuevos, y esos fixtures fallan contra la política de `main`.
  ```bash
  cd vectra-risk && make -C platform check-tools
  ```
  Esperado: rc 0. En la bitácora, la salida de la misma evaluación con la política de `main` y los fixtures nuevos: `require-min-replicas` en `fail`. Di qué entrada de `kyverno-test.yaml` cubre cada fixture.

- [ ] **CA-2** — El mínimo de 2 del modelo activo sigue vigilado: un `InferenceService` `prod` con `minReplicas: 1` se rechaza.
  ```bash
  cd vectra-risk && make -C platform check-tools && make -C model-serving policy-chart policy-chart-u1
  ```
  Esperado: rc 0, con un caso `fail` esperado para ese `InferenceService` (nuevo o existente: di cuál).

- [ ] **CA-3** — El pytest completo de `platform` pasa **como lo corre la CI**: sin `platform/.tools` en el árbol ni en el PATH, con `platform/.charts` presente.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: pasa. (Mueve `platform/.tools` FUERA del árbol para esta corrida y devuélvelo.)

- [ ] **CA-4** — `platform` y `model-serving` siguen en verde.
  ```bash
  cd vectra-risk && make -C platform check && make -C model-serving check
  ```
  Esperado: rc 0. Una sola vez, al final.

- [ ] **CA-5** — El barrido está en la bitácora: una tabla regla × recurso generado por KServe (perfil y namespace), con `pasa`, `falla (arreglado)` o `candidata`.
  ```bash
  cd vectra-risk && grep -n -c 'storage-initializer' bitacoras/U01-T15.md && uv run python platform/tests/test_links.py
  ```
  Esperado: al menos 1; enlaces en rc 0.

---

## Plan de pruebas

Las de CA-1 y CA-2. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`** ni contra `vectra.localtest.me`. No descargues imágenes.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts` (43 MiB). No van en el commit.
- En cada criterio, comprueba que el comando ejecuta de verdad tus fixtures y pruebas nuevas.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t15-`, y borra tus copias al terminar.
- En paralelo corren U01-T16 (`platform/kind/`, `platform/runbooks/install.md`) y U12-T09 (`system-verification/`): no toques esos archivos.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes (uno por bloque terminado). No hagas push, no fusiones, no muevas el estado de la tarea.
