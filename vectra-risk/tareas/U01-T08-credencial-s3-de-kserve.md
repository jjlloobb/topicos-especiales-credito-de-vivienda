# U01-T08 — Credencial S3 de KServe para el storage initializer (`minio-kserve`)

**Unidad:** U1 `platform-foundation`
**Historias:** ninguna nueva. Desbloquea US-111 y US-204 en kind (U06-T03).
**Depende de:** U06-T02 (PR #104, en `main`): el chart de U6 monta `minio-kserve` en la `ServiceAccount` `kserve-model`.
**Rama:** `tarea/U01-T08`, desde `origin/main`.

**Por qué.** El revisor de U06-T02 (`revisiones/U06-T02/ronda-1.md`, punto 3) leyó el código de KServe v0.21.0 (`service_account_credentials.go:282-294`). KServe solo reconoce un Secret S3 que tenga la clave `AWS_SECRET_ACCESS_KEY` (o la que configure `credentials.s3`), y el endpoint de MinIO tiene que venir de anotaciones `serving.kserve.io/s3-*` en el Secret o de esa misma configuración. Hoy:
- `platform/data/chart/values.yaml` (`extraSecrets.minio-kserve`) entrega solo `accessKey` y `secretKey`, sin anotaciones;
- `platform/operators/kserve.yaml` no configura `credentials.s3`.

Con eso el storage initializer no consigue credenciales y ningún predictor llega a Ready en kind: se rompe el flujo base de las cuatro demos. Está en `CANDIDATAS.md` como BLOQUEANTE para U06-T03.

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:**

1. **Claves AWS en `minio-kserve`.** Agrega a `extraSecrets.minio-kserve` las claves `AWS_ACCESS_KEY_ID` (de `accessKey`) y `AWS_SECRET_ACCESS_KEY` (de `secretKey`), igual que ya hacen `loki-s3` y `tempo-s3`. **Conserva** `accessKey` y `secretKey`: el aprovisionamiento de usuarios de MinIO (`platform/data/minio/values*.yaml`, `existingSecretKey: secretKey`) las usa en `vectra-data`.
2. **Endpoint y TLS de MinIO.** Elige **una** de estas dos vías y justifícala en la bitácora con el código o la documentación de KServe v0.21.0 y con cómo se expone MinIO en cada entorno (servicio, puerto 9000 de F46, TLS propio o solo mTLS de Linkerd):
   - **(a)** `credentials.s3` en `platform/operators/kserve.yaml` (`s3Endpoint`, `s3UseHttps`, `s3VerifySSL` y, si hace falta, `s3CABundle`), con overrides por entorno si el endpoint difiere;
   - **(b)** anotaciones `serving.kserve.io/s3-endpoint`, `s3-usehttps`, `s3-verifyssl` (y la CA si aplica) en el Secret `minio-kserve` de `vectra-serving` y `vectra-staging`, lo que exige que la plantilla de `extraSecrets` admita anotaciones.

   Recomendación del orquestador: **(a)**, porque es configuración del operador que U1 ya posee y no cambia la plantilla de los Secrets. Si el código de KServe dice que (a) no basta, usa (b) y explica por qué.
3. **Prueba.** Una prueba en `platform/tests/` que lea el render de kind (y de staging/prod) y compruebe: el `ExternalSecret` de `minio-kserve` en `vectra-serving` y `vectra-staging` produce `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`; el de `vectra-data` sigue produciendo `accessKey` y `secretKey`; y la configuración elegida en el punto 2 está presente con el endpoint de F46. Rojo primero sobre `origin/main`.
4. **Regenerar** `platform/rendered/` con su generador y dejar `--check` en verde.

**Fuera:**

- El chart de U6 (`model-serving/`), salvo que la vía (b) obligue a cambiar cómo se referencia el Secret; si es así, **detente y repórtalo**.
- Otros Secrets de MinIO, la bóveda (`platform/kind/seed-vault.sh`) y cualquier cambio de diseño de seguridad.
- Cualquier `kubectl`, `argocd` o sync (AUTONOMIA-01). La comprobación real en kind es de U06-T03.

---

## Archivos de contexto

- `revisiones/U06-T02/ronda-1.md` (punto 3) y `CANDIDATAS.md` (entrada de `minio-kserve`).
- `platform/data/chart/values.yaml` (`extraSecrets`), `platform/data/chart/templates/` (plantilla de los `ExternalSecret`), `platform/data/minio/values.yaml` y `values-kind.yaml`.
- `platform/operators/kserve.yaml` y `vectra-risk-gitops/components.yaml` (KServe v0.21.0).
- `platform/network/flows.yaml` (F46) y `model-serving/chart/` (cómo se monta `minio-kserve`).

---

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — La prueba nueva pasa y su rojo primero está en la bitácora.
- [ ] **CA-2** — Render regenerado: el generador de `platform/rendered/` con `--check` termina en 0.
- [ ] **CA-3** — `make -C platform check` termina en 0 (si faltan herramientas, `platform/install-tools.sh`).
- [ ] **CA-4** — `make -C model-serving check` sigue en 0.
- [ ] **CA-5** — `--all` según `DECISIONES-LOOP.md` §6, sin fallos nuevos.
- [ ] **CA-6** — `CANDIDATAS.md`: la entrada de `minio-kserve` queda marcada «Resuelta (U01-T08)», con la vía elegida.

---

## Notas

- **Bitácora:** `bitacoras/U01-T08.md`, con la vía elegida, su fuente en KServe y el endpoint por entorno.
