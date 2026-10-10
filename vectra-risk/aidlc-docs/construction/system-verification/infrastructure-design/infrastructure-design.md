# Infrastructure Design — U12 `system-verification`

Decisiones del plan (`system-verification-infrastructure-design-plan.md`, Q1–Q5 = A, con las
notas del usuario). Los IDs `INF-U12-xx` se referencian en el plan de tareas. Resuelve los
pendientes de nfr-requirements §8.

U12 no tiene datos ni componentes en el clúster: corre fuera, en la imagen `system-verification`,
y solo lee.

---

## 1. Ejecución fuera del clúster (Q5; hallazgo del plan)

### INF-U12-01 — Imagen y entornos
- Imagen `system-verification` construida, escaneada, con SBOM y firmada por `supply-chain.yml` de U1, publicada en el registro del banco; el operador la ejecuta por digest.
- **Secciones por entorno**:

  | Entorno | Secciones permitidas |
  |---|---|
  | kind | Todas |
  | staging | Solo humo (nota 1 de Q5): `decisions` reducida a 100 casos, la lectura del dashboard en `u11` y `report` |
  | producción | Ninguna (barrera de NFR-U12-03; el cliente y los usuarios no existen) |

- **`channel-simulator` sale del clúster** (nota 2 de Q5): ya no es un `Deployment` de `vectra-mock`. Es una sección de la imagen de U12, que envía por el gateway como un canal real. Cambia U1 y el inventario (§6):
  - `vectra-mock` queda solo con `core-banking-mock`;
  - F07 tiene como origen la estación del operador (fuera del clúster) → gateway;
  - la suite de conectividad prueba F07 desde fuera.
- **Verificación**: prueba de la barrera por sección (staging con `rt2` → se niega; `decisions` > 100 en staging → se niega); la imagen no contiene manifiestos de Kubernetes.
- **Satisface**: NFR-U12-01, 03; AUTONOMIA-01.

## 2. X04 y X06 (Q1)

### INF-U12-02 — Jobs de prueba de las unidades dueñas
- **U9** agrega a su chart el Job `x04-probe-<runId>`, con la identidad `bias-monitoring-job`. Llama a `POST /v1/models/{id}/approval` de governance, una ruta distinta de `freeze`, y termina con éxito solo si recibe el 403 de Linkerd.
- **U3** agrega a su chart de reconstrucción (`chart-rebuild/`) el Job `x06-probe-<runId>`, con la credencial de `registry_app` del `ExternalSecret` existente (no crea un Secret nuevo). Intenta `UPDATE registry_entries …` y termina con éxito solo si recibe `permission denied`.
- **Los dos Jobs** (nota 1 de Q1):
  - se renderizan **solo con los values de kind**; un `conftest` de U9 y de U3 comprueba que no aparecen con los values de staging ni de producción;
  - llevan `backoffLimit: 0` y el sidecar nativo de Linkerd, y **no** llevan `ttlSecondsAfterFinished` (revisión del Infrastructure Design de U12, 2026-10-10): como los Jobs de reconstrucción de U3, un Job completado queda como está y se **poda** cuando el `runId` cambia (sync con prune). Con un TTL, Kubernetes lo borraría a las 24 h, la Application quedaría `OutOfSync` y el siguiente sync volvería a correr la prueba;
  - se lanzan con un PR que fija `probes.runId` en los values de kind y un sync manual con prune;
  - **`probes.runId` es independiente de `monitoringRebuild.runId`** en `chart-rebuild/`: el chart renderiza los Jobs de reconstrucción solo con `monitoringRebuild.runId` y `x06-probe` solo con `probes.runId`. La regla «sin `runId` no hay recursos» pasa a ser «sin **ninguno** de los dos `runId` no hay recursos», y fijar uno no renderiza los recursos del otro.
- **Red** (revisión del Infrastructure Design de U12, 2026-10-10):
  - **X06**: U1 aplica deny-all, así que `x06-probe` necesita su propio flujo hacia `registry-db-rw`; sin él, la prueba daría timeout en lugar de `permission denied`. Se agrega **F111** (`x06-probe-<runId>` → `registry-db-rw`, 5432, **solo kind**) al inventario y a `flows.yaml`;
  - **X04**: la `NetworkPolicy` de F27 selecciona por la etiqueta de pod `vectra.io/workload: bias-monitoring-job`, y la `AuthorizationPolicy` de Linkerd, por la identidad `bias-monitoring-job`. Los pods de `x04-probe` llevan la misma etiqueta y la misma `ServiceAccount`, así que la conexión llega a governance y es Linkerd quien la rechaza en la ruta (403), que es lo que X04 prueba. Sin la etiqueta, la prueba daría timeout por la `NetworkPolicy` y no probaría X04;
  - una prueba de `generate.py` comprueba que F111 solo aparece en kind y que el selector de F27 admite los pods de `x04-probe`.
- U12 lee su estado y su log con `kubectl get job` y `kubectl logs`, y los guarda como evidencia de X04 y X06. BR-U12-05 cambia (§6).
- **Evidencia vieja** (segunda revisión del Infrastructure Design de U12, 2026-10-10): sin TTL, un Job completado de una verificación anterior sigue en el clúster. El oráculo de X04 y X06 solo acepta el Job si se cumplen las dos condiciones:
  - el sufijo `<runId>` de su nombre es igual al `runId` registrado en el manifiesto de la verificación en curso;
  - su `status.completionTime` es posterior al inicio de la verificación (el `started_at` del manifiesto).

  Si no se cumplen, el elemento sale `no ejecutado`, nunca `pasa`.
- **Comandos de `kubectl` permitidos** (nota 3 de Q1): NFR-U12-43 permite `get`, `auth can-i`, `logs` y `port-forward`. La prueba estática sigue rechazando `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` y `rollout`.
- **Verificación**: `conftest` de los dos charts con los tres values; en kind, cada Job termina con éxito y su log contiene el error esperado.
- **Satisface**: AUTONOMIA-01, 02, 03.

## 3. Acceso a lo interno (Q2)

### INF-U12-03 — `port-forward`, cliente de lectura y RBAC del operador
- **Camino**: `kubectl port-forward` a `decision-registry-service`, Prometheus y Loki desde la estación del operador.
  - No crea ni modifica recursos y no abre rutas en el gateway: X09 (único ingress) no cambia.
  - El `port-forward` llega al pod sin pasar por el gateway ni por las `NetworkPolicy`, así que solo lo pueden usar operadores con acceso al clúster.
- **RBAC del operador** (nota 1 de Q2; completado en la revisión del Infrastructure Design de U12, 2026-10-10): `port-forward` exige `create` sobre `pods/portforward`, y INF-U12-05 y NFR-U12-10 leen nodos, `InferenceService` y los digests de las imágenes. El binding **K16** (§6), solo en kind y staging, queda así:

  | Recurso | Verbos | Alcance |
  |---|---|---|
  | `nodes` | `get`, `list` | `ClusterRole` `vectra-verification-nodes` (los nodos no tienen namespace), para la capacidad de INF-U12-05 |
  | `pods` | `get`, `list`, `watch` | `vectra-app`, `vectra-edge`, `vectra-serving`, `vectra-identity`, `vectra-data`, `vectra-observability`: estado y digests de las imágenes (NFR-U12-10) |
  | `jobs` | `get`, `list`, `watch` | `vectra-app` (Jobs de prueba de U3, U9 y RT-5 de U8) |
  | `pods/log` | `get` | `vectra-app` |
  | `horizontalpodautoscalers` | `get`, `list`, `watch` | `vectra-app`, `vectra-edge` y `vectra-serving` (los HPA de KServe en `RawDeployment`, para BR-U12-08 y la suma de máximos de INF-U12-05; segunda revisión del Infrastructure Design de U12, 2026-10-10) |
  | `inferenceservices.serving.kserve.io` | `get`, `list`, `watch` | `vectra-serving` |
  | `pods/portforward` | `create` | `vectra-app` (registro) y `vectra-observability` (Prometheus y Loki) |
  | `selfsubjectaccessreviews` | `create` | Para `kubectl auth can-i` (el permiso estándar de todo usuario autenticado) |

  Un `Role` por namespace más el `ClusterRole` de nodos, sin comodines (`disallow-rbac-wildcards` de U1).

  `disallow-rbac-wildcards` de U1 lo cubre, y un `kyverno test` comprueba que el binding no existe en producción.
- **Cliente de lectura**: `verification-reader` de U2 (`private_key_jwt`), solo en `realm.kind.yaml` y `realm.staging.yaml`, con `registry:read:metrics` (entradas `recommendation` y `human_decision`) y `registry:read:monitoring` (entradas `freeze`). `realm-lint` lo rechaza en producción y comprueba que no tenga ningún otro scope.
- **RT-1 sin el registro** (nota 2 de Q2): el registro **nunca** guarda `free_text` (BR-U0-95 lo rechaza en todo payload), así que el oráculo de RT-1 de BR-U12-04 no puede leerlo de ahí. El texto vive en `case-db` y el analista lo ve en el detalle del caso (`CaseDetail.application`). RT-1 se verifica **por el BFF con `analista-1`**: el `free_text` del detalle es igual byte a byte al enviado, y la recomendación y la narrativa del detalle son idénticas a las del caso par. No hace falta ningún scope sensible. BR-U12-04 cambia (§6).
- **Latencia de RT-2** (nota 3 de Q2): una sola definición, la **más conservadora que se puede calcular**:
  - **inicio** = el **menor** `recorded_at` de las `recommendation` del lote `stratified` (leídas por `verification-reader` y filtradas por los `case_id` del `RunReport`). El cruce real del umbral ocurre entre la primera y la última entrada del lote, así que medir desde la primera nunca subestima;
  - **fin** = el `recorded_at` de la entrada `freeze`;
  - el lote tarda unos 3 min en ingresar, así que la cota puede sobrestimar hasta ≈ 3 min. Con ≈ 27 min típicos, el margen frente a 30 min queda en ≈ 0 a 3 min, y el informe lo dice.

  BR-U12-07, `Rt2Measurement` y PBT-U12-04 cambian (§6).
- **Prometheus y Loki**: sus APIs de lectura por el `port-forward`, sin credencial dentro del clúster.
- **Verificación**: `realm-lint` con `verification-reader` en producción → falla; con otro scope → falla; `kyverno test` del binding K16; prueba de RT-1 con un par cuyo `free_text` cambia en `case-db` → `falla`.
- **Satisface**: SECURITY-06, 08; AUTONOMIA-03.

## 4. Evidencias y capacidad (Q3, Q4)

### INF-U12-04 — Evidencias en el monorepo
- Cada verificación abre la rama `verification/<fecha>-<commit>` con `system-verification/evidence/<fecha>-<commit>/` (evidencias, `manifest.json` y `verification-report.md`).
- **`CODEOWNERS`** del directorio: los equipos `calidad` y `cumplimiento`, que el plan de tareas crea en el `CODEOWNERS` del monorepo si no existen (nota de Q3). `branch-protection-check` de U4 exige la aprobación de *code owners* en todo el monorepo, así que cubre esta ruta; una prueba lo confirma con un PR de fixture que toca solo `system-verification/evidence/`.
- Tope de 50 MB por verificación; los archivos grandes (reportes de k6, volcados de logs) se comprimen, y si aun así se supera, la evidencia guarda un resumen y el hash del original.
- **Satisface**: NFR-U12-20, 21.

### INF-U12-05 — Capacidad para la carga (US-609)
- Antes de la carga, la herramienta compara:
  - la capacidad asignable de los 4 workers de kind con la suma de los máximos de los HPA y de KServe;
  - la **CPU y la memoria libres del host** (nota de Q4), porque kind y el contenedor de k6 (2 CPU y 2 GiB) comparten el mismo hardware.
- Si alguna no alcanza, corre con `scale = 0,5` (10 solicitudes/s y 100 usuarios) y el informe lo dice.
- **Satisface**: NFR-U12-31; RESILIENCY-09.

## 5. Cumplimiento de extensiones (Infrastructure Design U12)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Sin recursos de U12 en el clúster; Jobs de prueba por PR y sync manual; `kubectl` sin escritura (INF-U12-01, 02) |
| AUTONOMIA-02 | Cumple | Oráculos y evidencias (INF-U12-02..04) |
| AUTONOMIA-03 | Cumple | X04, X06 y RT-5 por Jobs de las unidades dueñas; K16 acotado |
| SECURITY-06 / 08 | Cumple | `verification-reader` con dos scopes; K16 sin comodines y solo en kind y staging |
| SECURITY-12 | Cumple | Credenciales solo en memoria (NFR-U12-04) |
| RESILIENCY-09 | Cumple | INF-U12-05 |

## 6. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U12 FD BR-U12-04 (RT-1) | El oráculo de RT-1 se lee por el BFF con `analista-1` (`free_text`, recomendación y narrativa del detalle), porque el registro no guarda `free_text` (BR-U0-95) | Q2, nota 2 |
| U12 FD BR-U12-05 | X04 y X06 se leen de los Jobs `x04-probe` y `x06-probe` | Q1 |
| U12 FD BR-U12-07, domain-entities (`Rt2Measurement`) y PBT-U12-04 | Inicio de la latencia = el menor `recorded_at` de las `recommendation` del lote | Q2, nota 3 |
| U12 NFR-U12-43 | `kubectl` permitido: `get`, `auth can-i`, `logs`, `port-forward` | Q1, Q2 |
| U9 plan de tareas | Job `x04-probe-<runId>` solo en kind, con `conftest` | Q1 |
| U3 plan de tareas (chart de reconstrucción) | Job `x06-probe-<runId>` solo en kind, con `conftest` | Q1 |
| U2 (realm, `realm-lint`, plan) | Cliente `verification-reader` solo en kind y staging, con `registry:read:metrics` y `registry:read:monitoring` | Q2 |
| `component-dependency.md` §3 y U1 (RBAC, plan Paso 5) | Binding K16 `vectra-verification-operator` completo (nodos con `ClusterRole`, `inferenceservices`, pods por namespace), solo en kind y staging, creado en el Paso 5 de U1 y probado con `kyverno test` y `conftest`; NFR-U1-27 pasa a K01–K14 y K16 | Q2, nota 1; revisión del Infrastructure Design de U12, 2026-10-10 |
| `component-dependency.md` §2.4 y U1 (`flows.yaml`, plan Paso 3); U3 plan (Paso 13) | Flujo F111 `x06-probe` → `registry-db-rw`, solo kind; selector de F27 por `vectra.io/workload: bias-monitoring-job`, que llevan también los pods de `x04-probe` | revisión del Infrastructure Design de U12, 2026-10-10 |
| U3 BR-U3-17 y plan (Paso 12); U9 plan (Paso 12) | Jobs de prueba sin `ttlSecondsAfterFinished`, podados al cambiar `probes.runId`; en `chart-rebuild/`, los dos `runId` son independientes | revisión del Infrastructure Design de U12, 2026-10-10 |
| `component-dependency.md` §1 y F07; U1 deployment-architecture, `flows.yaml` y suite de conectividad | `channel-simulator` fuera del clúster: `vectra-mock` solo con `core-banking-mock`; F07 desde fuera por el gateway | Q5, nota 2 |
| `CODEOWNERS` del monorepo | Equipos `calidad` y `cumplimiento` para `system-verification/evidence/` | Q3 |
