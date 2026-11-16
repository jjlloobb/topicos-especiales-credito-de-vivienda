# U04-T11 — El Job de validación cumple la admisión del clúster

**Unidad:** U4 — `governance`
**Historias que implementa:** ninguna nueva; cierra un defecto medido al validar el modelo de referencia en `kind-vectra` el 2026-11-16.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> `governance-service` crea el Job de validación en `vectra-staging` por la API de Kubernetes (`governance/src/vectra_governance/k8s_jobs.py`, ≈ líneas 150 a 200). El namespace aplica `pod-security.kubernetes.io/enforce: restricted`, y el Pod del Job **no pasa la admisión**: el Job queda creado, sin ningún pod, para siempre.
>
> **Medido** (`kubectl -n vectra-staging describe job validation-65243983-65ad`):
> ```
> Warning  FailedCreate  job-controller  Error creating: pods "validation-65243983-65ad-…" is forbidden: violates PodSecurity "restricted:latest":
>   seccompProfile (pod or container "model-validation-job" must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
> ```
> El Job que se creó lleva `securityContext: {"runAsNonRoot": true}` en el pod y `{"allowPrivilegeEscalation": false, "capabilities": {"drop": ["ALL"]}, "readOnlyRootFilesystem": true}` en el contenedor: falta `seccompProfile`. `POST /v1/models/{id}/validations` respondió 200 (`state: lanzado`, `deadline_at` dos horas después) y el modelo quedó `en_validacion` con un Job que nunca corre.
>
> 1. El Pod del Job cumple **PodSecurity `restricted`** completo (no solo `seccompProfile`: revisa la lista entera del estándar para el pod y para cada contenedor, incluidos los que la malla inyecta si la plantilla los condiciona) **y las políticas de Kyverno de la plataforma** que aplican a `vectra-staging` (`platform/policies/kyverno/`: prioridad, recursos, digest, registro, etiquetas de criticidad, lo que corresponda a un Job).
> 2. **Una prueba lo demuestra sin clúster:** el manifiesto del Job que arma `k8s_jobs.py` (el real, no un doble) se valida contra PodSecurity `restricted` y contra las políticas de Kyverno. Para Kyverno, sigue el patrón del repositorio (los objetivos `policy-chart-u1` y el `check-tools` de `platform`: la evaluación con el binario corre en un objetivo de `make` que la CI ejecuta, **no** dentro de pytest, que corre sin `platform/.tools`). Para PodSecurity, una comprobación en pytest de los campos que exige `restricted` basta si es completa; di de dónde sale la lista. Hoy `governance/tests/unit/test_validation_job_template.py` no lo ve: di por qué.
> 3. **Barrido de la clase:** cualquier otro recurso que el código de una unidad cree por la API de Kubernetes en tiempo de ejecución (busca clientes de la API en `governance/`, `case-management/`, `bias-monitoring/`, `system-verification/`, `model-serving/`); y los `InferenceService` de staging que crea la promoción. Di cuáles hay y si cumplen; arregla los de U4; los demás, a `CANDIDATAS.md`.
> 4. **Qué pasa con una validación cuyo Job no llegó a tener pod.** Lee el código (`background.py`, `model_fsm.py`, `api.py`): con el Job atascado, ¿el modelo sale de `en_validacion` (cuándo: `deadline_at`, a las dos horas)?, ¿se puede volver a pedir la validación antes?, ¿qué debe hacer el operador con el Job viejo? Documenta el procedimiento en `governance/docs/paso-20-kind.md` (§5.2, «Si el Job no arranca») con órdenes concretas. Si el servicio no detecta nunca un Job sin pods, dilo: es candidata, no lo arregles aquí salvo que sea de pocas líneas y con su prueba.

**Fuera:**

- Las políticas de la plataforma y la etiqueta de PodSecurity del namespace (no se relajan).
- El contenido del Job de validación (`governance/validation_job/`), salvo que su imagen no pueda correr con el contexto de seguridad exigido: en ese caso, dilo y para.
- Reconstruir imágenes, digests y el clúster: lo hace el orquestador.

---

## Archivos de contexto

- `governance/src/vectra_governance/k8s_jobs.py`, `api.py`, `background.py`, `model_fsm.py`
- `governance/tests/unit/test_validation_job_template.py`, `validation_support.py`, `governance/Makefile` (`policy-chart`, `policy-chart-u1`, `check`), `governance/chart/`
- `governance/validation_job/Dockerfile` (usuario con que corre la imagen)
- `platform/policies/kyverno/`, `platform/namespaces/` (etiquetas de PodSecurity), `platform/Makefile` (`check-tools`), `platform/tests/kind_serving_kyverno.py` (el patrón de U01-T13 para evaluar con Kyverno fuera de pytest)
- `governance/docs/paso-20-kind.md` §5.2

---

## Criterios de aceptación

- [ ] **CA-1** — El manifiesto del Job cumple PodSecurity `restricted`.
  ```bash
  cd vectra-risk && uv run pytest governance/tests/unit -q -p no:cacheprovider -k "validation_job_template or pod_security"
  ```
  Esperado: pasa, con una prueba nueva que falla contra `main` con el mismo motivo que el clúster (`seccompProfile`). Comprueba con `--collect-only` que el filtro selecciona tu prueba. Mutaciones: quitar `seccompProfile`, `runAsNonRoot`, `allowPrivilegeEscalation: false` o `capabilities.drop` hacen fallar la prueba.

- [ ] **CA-2** — El manifiesto del Job cumple las políticas de Kyverno de la plataforma, evaluadas con el binario en un objetivo de `make` de `governance` que `check` incluye.
  ```bash
  cd vectra-risk && make -C governance policy-chart-u1
  ```
  Esperado: rc 0 y, en la salida, la evaluación del Job con `fail: 0`. Ajusta el objetivo al que corresponda y dilo. Si una política rechaza el Job, arréglalo o, si no se puede sin relajar la política, para y pregunta.

- [ ] **CA-3** — El pytest de `governance` y el de `platform` pasan **como los corre la CI**: sin `platform/.tools` en el árbol ni en el PATH.
  ```bash
  cd vectra-risk && uv run pytest governance/tests/unit -q -p no:cacheprovider && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: pasan. (Mueve `platform/.tools` FUERA del árbol para esta corrida y devuélvelo.)

- [ ] **CA-4** — El procedimiento para un Job que no arranca está en la guía, y el barrido, en la bitácora.
  ```bash
  cd vectra-risk && grep -n -i 'Si el Job no arranca' governance/docs/paso-20-kind.md && uv run python platform/tests/test_links.py
  ```
  Esperado: la sección existe; enlaces en rc 0.

- [ ] **CA-5** — `governance` sigue en verde.
  ```bash
  cd vectra-risk && make -C governance check
  ```
  Esperado: rc 0. Una sola vez, al final (levanta contenedores; si `test_service_build_app.py` falla con `XMinioServerNotInitialized` por la carga de la máquina, es el fallo conocido de `CANDIDATAS.md`: corre aparte lo que no llegó a correr y dilo).

---

## Plan de pruebas

Las de CA-1 y CA-2. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni contra `vectra.localtest.me`. En el clúster hay ahora mismo un Job atascado (`validation-65243983-65ad`) y el modelo `mv-2026-01-01-8a98ab02` en `en_validacion`: no lo toques; tu punto 4 dice qué hará el orquestador con él.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`, cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- No descargues imágenes. La máquina tiene poca memoria y un clúster de kind completo corriendo.
- En cada criterio, comprueba que el comando ejecuta de verdad tus pruebas nuevas.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u04t11-`.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
