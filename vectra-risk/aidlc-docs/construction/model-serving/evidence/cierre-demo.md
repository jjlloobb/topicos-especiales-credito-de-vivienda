# Cierre de U6 con alcance acotado a la demo

**Estado: pendiente de revisión; Paso 11 pendiente del operador.** U6 queda cerrada **para kind** (`demo-kind-alcance.md` §3, U6), no para staging ni prod. U06-T01 y U06-T02 crearon las imágenes, el chart, las políticas y la sección «Diferido por la demo»; U06-T03 agrega la guía del operador (Paso 11), los scripts, el presupuesto de memoria de kind y este cierre. El codificador no corrió nada contra el clúster (AUTONOMIA-01).

## Comprobado

Lo del codificador, sin clúster:

| Punto | Resultado | Dónde |
|---|---|---|
| `make -C model-serving check` | Termina en 0: ruff, mypy `--strict`, import-linter, pruebas con cobertura de ramas (>= 90 %; 100 % en `package_loader`), conftest y kubeconform de los tres perfiles, políticas de U1 sobre el render de kind, staging y prod, y trazabilidad | bitácora `bitacoras/U06-T03.md` |
| Presupuesto de memoria de kind | `requested_gib()` cuenta los `InferenceService`; kind pide 256 MiB por pod de serving; staging y prod siguen en INF-U6-01; `BUDGET_GIB` = 8,5 (pico medido 8,4375 GiB, con 512 MiB serían ≈ 10,4) | `platform/tests/test_kind_profile.py`, `vectra-risk-gitops/values/kind/model-serving.yaml`, `DECISIONES-LOOP.md` §7 |
| Guía del operador | Escenarios 1, 2, 3 y memoria con comando, salida esperada y ruta de evidencia | [`model-serving/docs/paso-11-kind.md`](../../../../model-serving/docs/paso-11-kind.md) |
| Scripts de kind | `traffic.sh`, `sample-replicas.sh`, `memory.sh`, `check-pods.sh`: `shellcheck` en 0 y 13 pruebas con dobles (servidor HTTP local y `kubectl` falso, que solo lee) | `model-serving/docs/kind/`, `model-serving/tests/unit/test_kind_scripts.py` |
| Paso 12 (N/A) | `model-serving/migrations` y `model-serving/frontend` no existen | plan, Paso 12 |

Evidencia de kind (la adjunta el operador; hasta entonces **pendiente del operador**):

| Escenario | Archivo de evidencia | Estado |
|---|---|---|
| Imágenes y digests | `evidence/kind/imagenes.md` | pendiente del operador |
| Paquetes en el model-store (y la elección de M2) | `evidence/kind/paquetes.md` | pendiente del operador |
| 1. Promoción con 0 `version_mismatch` | `evidence/kind/escenario-1-promocion.md` | pendiente del operador |
| 2. Rollback, el activo nunca baja de 2 réplicas | `evidence/kind/escenario-2-rollback.md` | pendiente del operador |
| 3. RT3-a/d no listos, RT3-b listo; `MODEL_DIR`, storage initializer del explicador, orden de init containers y propagación de etiquetas | `evidence/kind/escenario-3-rt3.md` | pendiente del operador |
| Memoria (`kubectl top`, DD-3 b) | `evidence/kind/memoria.md` | pendiente del operador |

## Pendiente de otras unidades

| Punto | Depende de |
|---|---|
| Escenario 1 de punta a punta: 0 `version_mismatch` contra `scoring-service` (hoy el tráfico va directo a `:predict` de cada `InferenceService`) | U7, Paso 18 |
| El `rollback_pr`, `post_activation_pr`, `create_promotion_pr` y `mark_active` reales (la guía los usa por su interfaz) | U04-T05b (`promotion-tool`) en `main` y U04-T07 (política y modelo de referencia) |
| Revisión de las cifras de memoria con cada unidad nueva (U7, U9 a U12) | `BUDGET_GIB` de `test_kind_profile.py` |

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit model-serving --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los Pasos 6, 7, 8 y 10 no aparecen: son de U06-T02 y se trazan en el chart, las políticas, las pruebas y el `Makefile`. El Paso 9 (alertas, runbooks, `ServiceMonitor`) está diferido entero (T2), pero sus identificadores (P-U6-06, NFR-U6-03) ya los cita el código de U06-T01 y no necesitan fila.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| NFR-U6-10 | Paso 4 (benchmark local de p95 ≤ 30 ms) y Paso 11 (prueba de carga de U12 en kind) | Enmienda §3 U6; T3 | Benchmark de `:predict` (p95 ≤ 30 ms) y de `:explain` (p95 ≤ 150 ms); sin él, el valor no está medido |
| NFR-U6-12 | Paso 11 (escalado bajo 20 solicitudes/s) | Enmienda §3 U6; T3; T6 | Prueba de carga con `kubectl get hpa` en kind: los componentes escalan sin superar sus máximos. El HPA está declarado y probado sobre el render (P-U6-04, NFR-U6-11), no bajo carga |
| NFR-U6-30 | Paso 5 (firma Cosign, SBOM, Trivy) | Enmienda §3 U6, Paso 5; T1 | Firma de las imágenes, SBOM y escaneo con `supply-chain.yml` de U1; y el `kyverno test` de una imagen oficial sin firma. Las imágenes ya están pinneadas por digest, sin firmar |
