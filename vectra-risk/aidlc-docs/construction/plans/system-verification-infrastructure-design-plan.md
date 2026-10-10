# Plan de Infrastructure Design — U12 `system-verification`

**Alcance:** cómo llegan las herramientas de U12, que corren fuera del clúster y solo leen
(NFR-U12-01, 43), a lo que necesitan verificar en kind y staging, y los pendientes de
nfr-requirements §8.

**Ya decidido** (no se pregunta):
- Imagen `system-verification` ejecutada por el operador fuera del clúster; k6 en un segundo contenedor en la red de kind si hace falta (NFR-U12-01).
- Credenciales leídas del Vault de kind (o la bóveda de staging) con la sesión del operador, solo en memoria (NFR-U12-04).
- Nada de U12 en producción; barrera de `issuer` y host (NFR-U12-03).
- El Job de RT-5 es de U8 (INF-U8-03) y la suite de conectividad, de U1.

**Hallazgo que este Infrastructure Design debe resolver:** el inventario
(`component-dependency.md` §1 y F07) y U1 (deployment-architecture §2) ubican `channel-simulator`
**dentro** del clúster, en `vectra-mock`. NFR-U12-01, ya aprobado, lo saca del clúster. Con Q1–Q5 en
A, se registra el cambio: `vectra-mock` queda solo con `core-banking-mock`, y F07 pasa a tener como
origen la imagen `system-verification` que el operador ejecuta fuera del clúster, contra el gateway
como un canal real.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Deployment Environment | Q5 |
| Compute Infrastructure | Q4 |
| Storage Infrastructure | Q3 (evidencias); U12 no tiene datos en el clúster |
| Messaging Infrastructure | Sin preguntas: U12 no usa colas |
| Networking Infrastructure | Q1, Q2 |
| Monitoring Infrastructure | Q2 (lectura de Prometheus y Loki) |
| Shared Infrastructure | Q1 (Jobs de prueba de otras unidades), Q2 (cliente de lectura de U2) |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — X04 y X06 (pendiente de nfr-requirements §8)
X04 exige llamar a governance con la identidad de `bias-monitoring-job`; X06, un `UPDATE` con
`registry_app` en `registry-db`. Desde fuera y con solo lectura no se puede.

A) **Jobs de prueba de las unidades dueñas, que U12 solo lee**:
   - **U9** agrega a su chart el Job `x04-probe-<runId>` (solo en kind, con la identidad `bias-monitoring-job`): llama a una ruta de governance distinta de `freeze` (por ejemplo, `POST /v1/models/{id}/approval`) y termina con éxito si recibe el 403 de Linkerd, y con error si recibe otra cosa;
   - **U3** agrega a su chart de reconstrucción el Job `x06-probe-<runId>` (solo en kind, con la credencial de `registry_app`): intenta un `UPDATE` sobre `registry_entries` y termina con éxito si recibe `permission denied`;
   - los dos se lanzan como los Jobs de reconstrucción de U3: un PR que fija un `runId` en los values de kind y un sync manual (sin `kubectl create`);
   - U12 lee su estado y su log con `kubectl get job` y `kubectl logs` (se agrega `logs` a los comandos de lectura de NFR-U12-43) y los guarda como evidencia.

   (Recomendado)

B) Permitir `kubectl exec` en un pod de bias y de registry, con justificación en NFR-U12-43

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) los dos Jobs se renderizan solo con los values de kind; un `conftest` de U9 y de U3 comprueba que no aparecen con los values de staging ni de producción, y llevan `ttlSecondsAfterFinished`. (2) El Job `x06-probe` recibe la credencial de `registry_app` por el `ExternalSecret` existente, sin crear un Secret nuevo. (3) NFR-U12-43 pasa a permitir `get`, `auth can-i`, `logs` y `port-forward` (Q2), y la prueba estática sigue rechazando `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` y `rollout`. (4) Cambios a registrar: planes de U9 y U3, y el FD/BR-U12-05 (X04 y X06 se leen de los Jobs).
## Question 2 — Llegar a lo interno: registro, Prometheus y Loki (pendiente de nfr-requirements §8)

A) **`kubectl port-forward` y un cliente de lectura solo en kind y staging**:
   - **camino**: `kubectl port-forward` a `decision-registry-service`, Prometheus y Loki desde la estación del operador. No es un cambio al clúster: no crea ni modifica recursos, y no abre ninguna ruta nueva en el gateway, así que X09 (único ingress) no cambia. `port-forward` se agrega a los comandos permitidos de NFR-U12-43;
   - **identidad del registro**: un cliente nuevo de U2, `verification-reader` (`private_key_jwt`), solo en `realm.kind.yaml` y `realm.staging.yaml`, con `registry:read:metrics` (entradas `recommendation` y `human_decision` para RT-1, RT-3 y la latencia de RT-2) y `registry:read:monitoring` (las entradas `freeze`); `realm-lint` lo rechaza en producción y comprueba que no tenga ningún otro scope;
   - **latencia de RT-2**: inicio = el mayor `recorded_at` de las `recommendation` del lote `stratified` (por sus `case_id`), que es la última entrada que pudo llevar la agregada sobre el umbral; fin = el `recorded_at` de la entrada `freeze`;
   - **Prometheus y Loki**: sus APIs de lectura por el `port-forward`, sin credencial dentro del clúster (como hoy los lee Grafana);
   - el `port-forward` va al pod y no pasa por el gateway ni por las `NetworkPolicy` de U1, así que solo se permite a operadores con acceso al clúster de kind o staging.

   (Recomendado)

B) Publicar rutas en el gateway para el registro, Prometheus y Loki

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) `port-forward` exige el verbo `create` sobre `pods/portforward` en el RBAC del operador; no crea recursos, pero la política de roles del operador debe permitirlo solo en kind y, si se usa, en staging. (2) Qué scope expone la entrada que lleva el `free_text` para RT-1: la proyección `metrics` no lleva texto libre, así que el Infrastructure Design confirma contra el catálogo de U0 y U3 qué scope de lectura permite compararlo; si es uno sensible, se agrega a `verification-reader` con su caso en `realm-lint` y se registra el cambio a U2. (3) La definición de inicio de la latencia de RT-2 (último `recommendation` del lote) difiere de BR-U12-07 y de `Rt2Measurement` (entrada que lleva la agregada sobre el umbral): el lote tarda ≈ 3 min en ingresar, así que ese inicio subestima la latencia hasta ≈ 3 min y no es conservador, con un margen de ≈ 27 contra 30 min. El Infrastructure Design fija una sola definición (la más conservadora que se pueda calcular) y se actualizan BR-U12-07, `Rt2Measurement` y PBT-U12-04.
## Question 3 — Dónde quedan las evidencias (Storage)

A) **En el monorepo, por PR**:
   - cada verificación abre una rama `verification/<fecha>-<commit>` con `system-verification/evidence/<fecha>-<commit>/` (evidencias, `manifest.json` y `verification-report.md`);
   - `CODEOWNERS` del directorio: el equipo de calidad y el de cumplimiento, con la aprobación obligatoria de *code owners* que verifica `branch-protection-check` de U4;
   - los archivos grandes (reportes de k6, volcados de logs) se comprimen y tienen un tope de 50 MB por verificación; si se supera, la evidencia guarda un resumen y el hash del original.

   (Recomendado)

B) En un bucket aparte

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: confirmar que existen los equipos de calidad y cumplimiento en los `CODEOWNERS` del monorepo, y que `branch-protection-check` de U4 cubre la ruta `system-verification/evidence/`.
## Question 4 — Capacidad de kind para la carga (Compute; US-609)

A) **Medir y escalar con aviso**:
   - la prueba de carga necesita el clúster de kind de U1 (4 workers en 2 zonas simuladas, U1 deployment-architecture) con los HPA en sus máximos y KServe escalado;
   - antes de la carga, la herramienta lee la capacidad asignable de los nodos y la suma de los máximos de los HPA, y si no alcanza corre con `scale = 0,5` (10 req/s y 100 usuarios) y el informe lo dice;
   - k6 corre en su propio contenedor con 2 CPU y 2 GiB, fuera de los nodos del clúster, para no robarles capacidad.

   (Recomendado)

B) Agregar nodos a kind solo para la prueba

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: kind y k6 comparten el host; la comprobación de capacidad incluye la CPU y la memoria libres del host (no solo la asignable de los nodos), porque k6 con 2 CPU y 2 GiB compite con los nodos de kind por el mismo hardware.
## Question 5 — Imagen y entornos (Deployment Environment)

A)
   - imagen `system-verification` construida, escaneada, con SBOM y firmada por `supply-chain.yml` de U1, publicada en el registro del banco; el operador la ejecuta por digest;
   - **kind**: todas las secciones;
   - **staging**: solo humo (BR-U12-10), con el cliente `verification-reader` y los usuarios sintéticos de staging;
   - **producción**: nada (barrera de NFR-U12-03; el cliente y los usuarios no existen).

   (Recomendado)

B) Ejecutar desde el código fuente, sin imagen

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) en staging solo se permiten las secciones de humo: `decisions` reducida (hasta 100 casos), la lectura del dashboard de `u11` y `report` (cierra la nota pendiente de NFR-U12-03). (2) Como `channel-simulator` sale de `vectra-mock`, se registra el cambio en U1: `flows.yaml` (F07 con origen externo por el gateway), la suite de conectividad, el inventario de `component-dependency.md` §1 y `deployment-architecture.md` de U1; `vectra-mock` queda solo con `core-banking-mock`.
---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `infrastructure-design.md` (INF-U12-xx)
- [x] `deployment-architecture.md`
- [x] Cambios a otras unidades (U2 cliente de lectura; U3 y U9 Jobs de prueba; U1 si hace falta) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
