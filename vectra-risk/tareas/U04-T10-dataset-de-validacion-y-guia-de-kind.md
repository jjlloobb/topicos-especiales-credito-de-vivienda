# U04-T10 — El dataset de validación es un objeto que el Job puede leer, y la guía de kind no pisa los values

**Unidad:** U4 — `governance` (y un documento de U5, `reference-model/docs/release.md`)
**Historias que implementa:** ninguna nueva; cierra dos defectos de integración que impiden validar un modelo en kind (auditoría entre unidades del 2026-11-14).
**Depende de:** ninguna (U01-T10 arregla en paralelo el permiso de MinIO; no la esperes)

---

## Alcance

**Dentro:**

> 1. **`datasetRef` apunta a un objeto, y U5 lo sube ahí.** `governance/chart/values.yaml:54` trae `datasetRef: s3://validation-datasets`, que es solo el bucket. `api.py:354` lo pasa tal cual al Job de validación y el lector lo rechaza: `S3Reader.read("s3://validation-datasets")` → `ValidationJobError object_uri_invalid` (`governance/validation_job/vectra_validation/s3.py:65-66`; ejecutado por el revisor). Mientras tanto, `reference-model/docs/release.md:70` sube el dataset a `validation-datasets/${MV}/validation.parquet`. Los dos lados quedan de acuerdo en **una** ruta de objeto, la que el diseño de U4 y U5 respalde. Si el diseño pide un dataset por versión de modelo (la ruta con `${MV}`) y eso exige cambiar el contrato entre el servicio y el Job, **para y pregunta** antes de tocarlo.
> 2. **Un `datasetRef` sin objeto no se despliega.** El chart o el servicio lo rechaza pronto y con un mensaje claro, en vez de fallar dentro del Job en plena validación.
> 3. **La guía de kind no pisa los values.** `governance/docs/paso-20-kind.md:52-58` dice «crea `vectra-risk-gitops/values/kind/governance.yaml` (nuevo)»; ese archivo ya existe con `keycloak.issuer` (U02-T21). Seguida al pie de la letra devuelve el emisor interno y todo token da 401. La guía pasa a decir que se **añaden** claves al archivo existente, como las de U7 y U8, y el «Esperado» del diff se corrige.
> 4. **La prueba usa el permiso real.** `governance/tests/unit/validation_support.py:185` usa `validation-readonly` con un almacén falso que deja leer cualquier bucket, y por eso nadie vio que ese usuario no puede leer `model-store` (lo arregla U01-T10 en U1). El doble respeta qué buckets puede leer cada usuario, o una prueba ata la lista de buckets que el Job lee a una constante que U1 pueda comprobar.

**Fuera** (recházalo aunque lo veas roto):

- La política de MinIO (`platform/data/minio/`): es U01-T10.
- Quién puede escribir en `validation-datasets` (`CANDIDATAS.md:271`): sigue como está; `release.md` conserva su aviso de subir con la raíz.
- Construir imágenes, digests, o cualquier otra sección de `paso-20-kind.md`.
- El código de `reference-model/` (solo su `docs/release.md`).

---

## Archivos de contexto

- `governance/chart/values.yaml`, `governance/chart/templates/service.yaml:70`, `vectra-risk-gitops/values/kind/governance.yaml`
- `governance/src/vectra_governance/api.py:354`, `config.py`, `k8s_jobs.py`
- `governance/validation_job/vectra_validation/run.py`, `s3.py`
- `governance/tests/unit/validation_support.py`
- `governance/docs/paso-20-kind.md`, `reference-model/docs/release.md`
- `aidlc-docs/construction/governance/` y `aidlc-docs/construction/reference-model/` (el diseño: de dónde sale el dataset y si es uno o uno por versión)
- `DECISIONES-LOOP.md`, `CANDIDATAS.md`

---

## Criterios de aceptación

- [ ] **CA-1** — El `datasetRef` que renderiza kind es una URI de objeto que el lector del Job acepta.
  ```bash
  cd vectra-risk && uv run pytest governance/tests -q -p no:cacheprovider -k "dataset"
  ```
  Esperado: pasa, con una prueba nueva que toma el valor **renderizado** del chart con los values de kind (los `valueFiles` de `vectra-risk-gitops/apps/kind/governance.yaml`) y lo pasa por el analizador de URI real de `s3.py`. Contra `main`, esa prueba falla con `object_uri_invalid`.

- [ ] **CA-2** — La ruta a la que `release.md` sube el dataset es la misma que lee U4.
  ```bash
  cd vectra-risk && uv run pytest governance/tests -q -p no:cacheprovider -k "release_doc or dataset"
  ```
  Esperado: pasa, con una prueba que extrae la ruta de la orden `mc cp` de `reference-model/docs/release.md` y la compara con el `datasetRef` renderizado; cambiar uno sin el otro la hace fallar.

- [ ] **CA-3** — Un `datasetRef` que es solo un bucket no se despliega.
  ```bash
  cd vectra-risk && helm template governance governance/chart --set validation.datasetRef=s3://validation-datasets $(sed -n 's/^ *- \$values\/vectra-risk\//-f /p' vectra-risk-gitops/apps/kind/governance.yaml | tr '\n' ' ') ; echo "rc=$?"
  ```
  Esperado: rc distinto de 0 con un mensaje que nombra `validation.datasetRef`; o, si lo rechaza el servicio al arrancar, la prueba unitaria que lo demuestra (dilo en la bitácora y ajusta el comando).

- [ ] **CA-4** — La guía de kind añade claves al archivo existente y no dice crearlo.
  ```bash
  cd vectra-risk && ! grep -n -E 'crea `vectra-risk-gitops/values/kind/governance.yaml`|governance.yaml` \(nuevo\)' governance/docs/paso-20-kind.md && grep -n 'keycloak.issuer' governance/docs/paso-20-kind.md
  ```
  Esperado: el primer `grep` no encuentra nada; el segundo encuentra el aviso de conservar `keycloak.issuer`.

- [ ] **CA-5** — El doble de la validación no deja leer a un usuario un bucket que su política no cubre.
  ```bash
  cd vectra-risk && uv run pytest governance/tests/unit -q -p no:cacheprovider -k "validation"
  ```
  Esperado: pasa, con una prueba negativa nueva. La bitácora dice qué buckets necesita leer el Job y con qué usuario, para que U01-T10 lo ate del lado de U1.

- [ ] **CA-6** — `governance` sigue en verde, y los enlaces también.
  ```bash
  cd vectra-risk && make -C governance check && uv run python platform/tests/test_links.py
  ```
  Esperado: rc 0. Si `make -C governance check` levanta contenedores y la máquina está cargada, córrelo una sola vez al final.

---

## Plan de pruebas

- Prueba del `datasetRef` renderizado contra el analizador real (CA-1).
- Prueba que ata `release.md` y el chart (CA-2).
- Prueba negativa del `datasetRef` sin objeto (CA-3).
- Prueba negativa del doble con permisos por bucket (CA-5).

**Rojo primero:** cada prueba nueva se ve fallar contra `main` antes del cambio; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** La máquina tiene poca memoria libre (≈ 5 GiB): no corras suites pesadas más de una vez.
- Se modifican en su sitio los archivos citados.
- El paquete del modelo de referencia aún no se ha subido a ningún MinIO: cambiar la ruta del dataset no rompe nada desplegado.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
