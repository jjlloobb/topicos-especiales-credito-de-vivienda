# U01-T12 — El presupuesto de kind cuenta todo, serving no escala fuera de lo contado y el simulacro de failover tiene un procedimiento que funciona

**Unidad:** U1 — `platform-foundation` (con los values de kind de U6)
**Historias que implementa:** ninguna nueva; cierra los NARANJA de la revisión de U01-T11 (`revisiones/U01-T11/ronda-1.md`), cuyo PR se fusionó antes de terminar la revisión.
**Depende de:** U01-T11 (en `main`). U02-T23 (Keycloak con una réplica en kind) corre en paralelo y aún no está en `main`.

---

## Alcance

**Dentro:**

> 1. **Las cuentas ven los sidecars nativos (F-01).** `pod_cpu` y `pod_memory` de `platform/tests/test_kind_profile.py` solo suman `containers`. `linkerd-destination` y `linkerd-proxy-injector` llevan su proxy como `initContainer` con `restartPolicy: Always`, y el namespace `linkerd` no está en `MESHED`. La cuenta sigue la regla de Kubernetes (sidecars nativos sumados; para el resto de init containers, el máximo entre init y contenedores). El revisor recalculó: CPU 10,515 (tope 10,5) y memoria 13,8984 GiB (tope 13,9).
> 2. **Serving no escala fuera de lo contado en kind (F-03).** Con el request en 100m y el HPA al 60 %, el umbral es ≈ 72m por pod: con casi cualquier tráfico de D2 los dos InferenceService de prod escalarían a `maxReplicas` (predictor 2→4, explicador 2→6): +3,23 GiB y +1,44 CPU que nadie cuenta y que no caben. En kind, y solo en kind, serving deja de poder crecer más allá de lo que el presupuesto cuenta. Elige la forma que las políticas admitan y dilo, por este orden de preferencia: (a) `maxReplicas` igual a `minReplicas` en los perfiles de kind; (b) si `require-hpa-bounds` u otra política exige `max > min`, el `maxReplicas` más bajo admitido y `cpuUtilization` en 100; en cualquier caso **la prueba del presupuesto cuenta `maxReplicas`**, no `minReplicas`, para serving. Los limits y las 2 réplicas mínimas no cambian.
> 3. **El presupuesto dice lo que de verdad se pide en el pico de D2.** Además de lo anterior: el Job de validación (1 GiB más proxy, se crea en tiempo de ejecución) y lo de `kube-system` que tenga cifra conocida (`calico-node`, CoreDNS; F-06: `UNCOUNTED_CPU` nombra kindnet, que no se instala) entran en la cuenta o en una constante declarada y atada a su origen. El texto de la prueba y de los comentarios deja de hablar de «16 núcleos programables de la máquina» como si fueran capacidad real (F-05): son 8 núcleos físicos compartidos por tres nodos; el tope evita pods en `Pending`, nada más.
> 4. **El simulacro de failover tiene un procedimiento que funciona (F-02).** `platform/kind/postgres-failover.yaml:3` dice «Argo CD lo agrega solo», y es falso: hay que regenerar con `generate.py` y llevar el cambio a `main`, y deshacerlo al terminar. `install.md`, `values-kind.yaml` y el propio archivo lo dicen bien, y una prueba ejecuta el procedimiento escrito (copiar, regenerar, `--check`, render con los `valueFiles` de la Application) y comprueba las 3 instancias.
> 5. **Las pruebas de referencias colgantes cubren reglas, monitores y el `uid` de fuente de datos de los dashboards (F-07).**

**Keycloak.** U02-T23 dejará el HPA de Keycloak de kind en mínimo 1 (ahorra ≈ 1,02 GiB y 0,6 CPU). Tu prueba lee el render de `identity-edge`, así que la cifra bajará sola cuando esa tarea entre. Fija `BUDGET_GIB` y `CPU_BUDGET` con lo que hay hoy en `main`, y da en la bitácora las dos cifras: con Keycloak en 2 y en 1.

**Lo importante de esta tarea es la cifra honesta.** Si con todo contado el pico de D2 no cabe en una máquina de 15 GiB (hoy la plataforma sola usa ≈ 7,6 GiB reales y el revisor estima ≈ 15,15 GiB pedidos), **no lo disimules**: fija el presupuesto en lo medido, di cuánto sobra o falta frente a 15 GiB, y propón en la bitácora qué más se podría recortar en kind (con su ahorro), sin aplicarlo: esa decisión es del usuario.

**Fuera:**

- `identity-edge/` (U02-T23) y `system-verification/` (U12-T07 corrige la guía de U12 por F-04).
- Bajar réplicas mínimas de U3 a U11 o de los InferenceService activos; Argo CD sin dex; cualquier recorte nuevo.
- Staging y prod: su render no cambia.

---

## Archivos de contexto

- `revisiones/U01-T11/ronda-1.md`, `bitacoras/U01-T11.md`, `tareas/U01-T11-…`
- `platform/tests/test_kind_profile.py`, `platform/mesh/linkerd-kind.yaml`, `platform/kind/postgres-failover.yaml`, `platform/kind/cluster.yaml`, `platform/data/chart/values-kind.yaml`, `platform/runbooks/install.md`, `platform/policies/kyverno/require-hpa-bounds.yaml`
- `vectra-risk-gitops/` (`generate.py`, `apps/kind/postgres.yaml`, `values/kind/model-serving.yaml`), `model-serving/chart/` (`values.yaml`, `values.schema.json`, plantillas del HPA/InferenceService) y sus pruebas de chart
- `governance/src/vectra_governance/k8s_jobs.py` (recursos del Job de validación; solo lectura)
- `DECISIONES-LOOP.md` §7, `CANDIDATAS.md`

---

## Criterios de aceptación

- [ ] **CA-1** — Las cuentas incluyen los sidecars nativos y el Job de validación; los topes son los medidos.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "budget or cpu"
  ```
  Esperado: pasa. Contra `main`, la prueba nueva de sidecars nativos falla. La bitácora trae el desglose completo del pico de D2 (memoria y CPU), con Keycloak en 2 y en 1, y la comparación con 15 GiB.

- [ ] **CA-2** — En kind, serving no puede escalar más allá de lo contado.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "serving" && uv run pytest model-serving/tests -q -p no:cacheprovider -k "chart or values or schema"
  ```
  Esperado: pasa, con una prueba que rinde un InferenceService de prod con los values de kind y comprueba que réplicas máximas × request es lo que el presupuesto suma; el render cumple las políticas de Kyverno (resultado en la bitácora). Ajusta el segundo comando al nombre real de las pruebas de chart de U6 y dilo.

- [ ] **CA-3** — El procedimiento del simulacro de failover, ejecutado tal como está escrito, da 3 instancias en los cuatro clusters.
  ```bash
  cd vectra-risk && uv run pytest platform/tests -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "failover"
  ```
  Esperado: pasa; contra `main`, falla (o no existe y el procedimiento escrito da `generate.py --check` rc 1: muéstralo).

- [ ] **CA-4** — Las referencias colgantes cubren reglas, monitores y dashboards.
  ```bash
  cd vectra-risk && uv run pytest platform/tests -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "dangling or colgante or references"
  ```
  Esperado: pasa; una mutación (una regla o un panel que nombra Loki) la hace fallar. Ajusta el filtro al nombre real y dilo.

- [ ] **CA-5** — Staging y prod no cambian, y todo sigue en verde.
  ```bash
  cd vectra-risk && make -C platform check-local && git diff --stat origin/main -- platform/rendered/staging platform/rendered/prod vectra-risk-gitops/apps/staging vectra-risk-gitops/apps/prod
  ```
  Esperado: rc 0 y diff vacío.

---

## Plan de pruebas

Las de CA-1 a CA-4. **Rojo primero** en cada una; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** No levantes contenedores que una prueba existente no levante. La máquina tiene poca memoria y hay otros dos codificadores trabajando.
- `platform/.charts` y `platform/.tools` no están versionados: cópialos del árbol principal. No descargues imágenes de contenedor.
- Scratchpad compartido: prefijo `u01t12-`. `CANDIDATAS.md`: solo añadir al final.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
