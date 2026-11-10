# Ronda 1 — U01-T08

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `baaa3a9`, base `0288602`. El revisor no escribe en el worktree; el orquestador transcribió este informe de su entrega.

## Criterios de aceptación (corridos por el revisor, tras `make -C platform charts`)

| # | Comando | Resultado |
|---|---|---|
| CA-1 | `uv run pytest platform/tests/test_kserve_credentials.py -v`, en la rama y en `git archive 0288602` | 11 passed; rojo reproducido en la base: 7 failed, 4 passed |
| CA-2 | `make -C platform check-rendered` | rc 0 |
| CA-3 | `make -C platform check` | rc 0: pytest 800 passed, chainsaw 81/81, kyverno 335/0 y 47/0, conftest 707/336/3 sin fallos |
| CA-4 | `make -C model-serving check` | rc 0, 24 identificadores trazados |
| CA-5 | `test_traceability.py --all`, rama y base | rc 1 en las dos; los 39 fallos de la rama (U4 y U9, sin `cierre-demo.md`) ya estaban en la base: sin fallos nuevos |
| CA-6 | `grep -c "Resuelta (U01-T08)" CANDIDATAS.md` | 1, con la vía (a) |

## Dictamen

1. **Clave de values correcta.** En `kserve-resources` v0.21.0 (`files/common/configmap-patch.yaml`, `data.credentials`) el bloque `s3` se arma desde `.Values.kserve.storage.s3.*`, y los nombres por omisión de las claves son `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. El render de `inferenceservice-config.credentials.s3` sale con `s3Endpoint: minio.vectra-data.svc:9000`, `s3UseHttps: "0"`, `s3VerifySSL: "false"`.
2. **La SA `kserve-model` basta.** KServe v0.21.0: `storage_initializer_injector.go:598-603` → `CreateSecretVolumeAndEnv` con la SA del pod; `service_account_credentials.go` reconoce el Secret por `AWS_SECRET_ACCESS_KEY`; `s3/s3_secret.go` inyecta las `AWS_*` como `secretKeyRef`; `s3/utils.go` toma endpoint, HTTPS y verificación del ConfigMap si el Secret no trae anotaciones. El chart de U6 usa `serviceAccountName: kserve-model` y la SA lista `minio-kserve`.
3. **El riesgo de Linkerd no es real.** `proxy.nativeSidecar: true` y `proxy.await: true` (`platform/mesh/linkerd-values.yaml`), y `vectra-serving`/`vectra-staging` anotados con el sidecar nativo. El inyector (linkerd2 edge-26.10.2, `patch.json`) pone `network-validator` y el proxy delante de cualquier init container, con `restartPolicy: Always` y `startupProbe`; el storage initializer sale por el proxy con mTLS. `Server minio-9000` autoriza `kserve-model` de `vectra-serving` y `vectra-staging` (F46, `MeshTLSAuthentication`).
4. **MinIO y el render.** `existingSecretKey: secretKey` sigue sirviendo en `vectra-data`; el diff de `platform/rendered/` es +2 líneas (`AWS_*`) en cada `ExternalSecret` `minio-kserve` de kind, staging y prod.

## Hallazgos

- **F-01 · AMARILLO** · `bitacoras/U01-T08.md` y `CANDIDATAS.md`: premisa falsa sobre el orden del proxy y un remedio (`skip-outbound-ports` con 9000) que rompería F46. **Corregido por el orquestador** en los dos archivos.
- **F-02 · AMARILLO** · `platform/tests/test_kserve_credentials.py:47`: no comprueba `s3VerifySSL`; la prueba del puerto compara una constante propia con F46. Candidata.
- **F-03 · AMARILLO** · `platform/data/chart/values.yaml:108`: las `AWS_*` también llegan a `vectra-data`. Inofensivo. Candidata.

Sin tareas candidatas nuevas. La comprobación en kind (orden de los init containers y descarga de `s3://model-store`) es de U06-T03.
