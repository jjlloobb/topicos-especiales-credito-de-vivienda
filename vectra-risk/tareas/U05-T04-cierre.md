# U05-T04 — Cierre de `reference-model`: procedimiento de entrega, cobertura, trazabilidad y cierre acotado a la demo

**Unidad:** U5 `reference-model`
**Historias que implementa:** US-201 y US-202, en su parte de entrega.
**Depende de:** U05-T03 (PR 86). Si todavía no está fusionado, **la rama parte de `origin/tarea/U05-T03`**, y el orquestador la integra con `main` cuando se fusione.

Bloques E y F del plan de U5 (Pasos 9 a 12), con el alcance de la demo (`aidlc-docs/construction/plans/demo-kind-alcance.md` §3, U5):
- **Paso 8 D:** diferido (T1, T4). No se hace aquí.
- **Paso 9 E\*:** sin descargar la release ni `cosign verify`. Se usa `make release` local, se verifica cada SHA-256 del manifiesto y se sube al MinIO de kind (T1).
- **Paso 10 E:** completo.
- **Paso 11 N/A.**
- **Paso 12 E\*:** cierre acotado.

Rige el ritmo RL-1 a RL-5 (§6).

## Alcance

**Dentro:**

- **Paso 9, acotado a la demo.** `reference-model/docs/release.md` es el procedimiento del operador, con un comando en cada paso:
  1. `make -C reference-model release` en local;
  2. verificar cada SHA-256 del `manifest.json` con un comando o un script incluido (por ejemplo, un target `verify-release`);
  3. subir el paquete al bucket `model-store` y el dataset de validación al bucket `validation-datasets` del **MinIO de kind**, con las credenciales del ingeniero (NFR-U5-03; AUTONOMIA-01: lo ejecuta una persona). Usa `mc` (la imagen y el alias que ya documenta `platform/runbooks/install.md`) y no inventes rutas: toma los nombres de bucket del diseño de U1 y U4;
  4. registrar la versión en U4 (US-201). U4 todavía no existe: el documento nombra el endpoint del diseño de U4, con `[PENDIENTE U4]`;
  5. los 5 paquetes de la variante proxy (`rt2-demo`) se suben igual, pero solo en kind y en staging (BR-U5-15).
  - Una sección «Diferido por la demo (T1)» dice qué agrega la release firmada del Paso 8: descarga, `cosign verify` y `verify-attestation`.
  - Aceptación: `uv run python platform/tests/test_runbooks.py --operational --root reference-model/docs`. Además, una prueba que corre el script de verificación de SHA sobre un paquete bueno (pasa) y sobre uno alterado (falla).
- **Paso 10 completo:**
  - cobertura de ramas ≥ 90 % y 100 % en `envelope/confidence.py`;
  - trazabilidad de cada BR-U5 a una prueba;
  - `aidlc-docs/construction/reference-model/code/README.md`, con el formato de `aidlc-docs/construction/contracts/code/README.md`.
  - Aceptación: `uv run pytest reference-model/tests --cov --cov-branch --cov-fail-under=90` y `uv run python platform/tests/test_traceability.py --unit reference-model --all`.
  - Si la prueba de trazabilidad no reconoce los BR-U5 porque están en párrafos y no en tablas (le pasó a U3), **no la cambies**. Demuestra con `grep` en la bitácora que cada BR-U5 aparece en una prueba y deja la candidata.
- **Paso 11 (N/A):** `test ! -d reference-model/chart && test ! -d reference-model/migrations`.
- **Paso 12, cierre acotado:**
  - `make -C reference-model check` corre en orden las verificaciones de los Pasos 1 a 10 y termina en 0;
  - `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`, con el formato del cierre acotado de U1 (`aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`): qué quedó comprobado, qué se difirió (Paso 8 y la parte de release del Paso 9) y su destino, y las candidatas abiertas de U5 más relevantes (margen de 0,39 pp de la base, doble de U9, `derive` de U0).

**Plan:** marca `[x]` los Pasos 9, 10, 11 y 12. El 9 y el 12 llevan «(U05-T04, acotado a la demo)». El Paso 8 queda `[ ]`, con la nota «diferido por la demo».

**Fuera:**
- El workflow de CI, la release OCI firmada, `cosign` y SBOM (Paso 8, diferido).
- Subir algo de verdad a MinIO o registrar en U4: lo hace el operador después.
- Cambiar el generador, el modelo o la calibración.

## Archivos de contexto

- `aidlc-docs/construction/plans/reference-model-code-generation-plan.md` (Pasos 8 a 12)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§3, U5, y §6)
- `aidlc-docs/construction/reference-model/` (NFR-U5-03, 33; todos los BR-U5)
- `aidlc-docs/construction/platform-foundation/` (buckets de MinIO) y `aidlc-docs/construction/governance/` (registro de versiones)
- `platform/runbooks/install.md` y `platform/runbooks/_template.md` (formato operativo)
- `aidlc-docs/construction/contracts/code/README.md` y `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md` (formatos)
- `reference-model/`, `revisiones/U05-T0*/` y `CANDIDATAS.md`

## Criterios de aceptación

- [ ] **CA-1** — Procedimiento de entrega.
  ```bash
  uv run python platform/tests/test_runbooks.py --operational --root reference-model/docs && uv run pytest reference-model/tests -k "verify_release" -v
  ```
  Esperado: código 0. El paquete alterado hace fallar la verificación.

- [ ] **CA-2** — Cobertura y trazabilidad.
  ```bash
  uv run pytest reference-model/tests --cov --cov-branch --cov-fail-under=90 && uv run python platform/tests/test_traceability.py --unit reference-model --all
  ```
  Esperado: código 0, con cobertura ≥ 90 % y 100 % en `confidence.py`.

- [ ] **CA-3** — N/A y cierre.
  ```bash
  test ! -d reference-model/chart && test ! -d reference-model/migrations && make -C reference-model check && make -C platform check && uv run python platform/tests/test_links.py
  ```
  Esperado: código 0 en todos.

## Plan de pruebas

Haz el rojo primero en el script de verificación de SHA, con un paquete alterado. Si la cobertura no llega al 90 %, agrega las pruebas que falten antes de marcar el Paso 10. Registra todo en `bitacoras/U05-T04.md`.

## Notas

- Hay otro codificador en paralelo en `decision-registry/` (U03-T04). No toques ese directorio.
