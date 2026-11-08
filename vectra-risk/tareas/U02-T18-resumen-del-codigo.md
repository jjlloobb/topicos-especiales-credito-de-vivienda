# U02-T18 — Resumen del código de U2 y correcciones de la revisión del PR 79

**Unidad:** U2 `identity-edge`
**Historias que implementa:** ninguna nueva (documentación y trazabilidad de US-601 y US-611).
**Depende de:** el PR 79, ya fusionado en `main`.

Paso 15 del plan de U2, que entra **completo** en la demo (E). Además lleva las correcciones de documentación que dejó la revisión de código del PR 79 (decisión del usuario, 2026-11-08: sin ronda 4, y lo pendiente va aquí o a candidatas). Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6.

## Alcance

**Dentro:**

1. **Paso 15 del plan, sin recortes:**
   - [ ] **Paso 15 — Resumen del código de U2**
     - `aidlc-docs/construction/identity-edge/code/README.md`: componente → archivos → verificación → BR/NFR/P/INF.
     - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit identity-edge` (cada BR-U2, NFR-U2, P-U2 e INF-U2 aparece en algún archivo de `identity-edge/`).

   Hoy faltan 7: NFR-U2-04, 05, 21, 25, 40, 41 y 42. Para cada uno:
   - si hay un archivo de `identity-edge/` que lo implementa o lo prueba, el id va en ese archivo, en un comentario o docstring junto al código que lo cumple;
   - si se cumple fuera de `identity-edge/` (por ejemplo, en U1 o en un workflow), va a la tabla «Trazabilidad a código de los identificadores sin referencia en él» del README, con el archivo, como en `aidlc-docs/construction/contracts/code/README.md`. Si `test_traceability.py` no acepta esa tabla para U2, **detente y repórtalo**: no cambies la prueba;
   - si se verifica en el Paso 16 (kind) o en una prueba diferida por la demo, se nombra el archivo de la especificación que lo cubre (por ejemplo, `identity-edge/tests/e2e/` o `identity-edge/tests/load/`).

   No se agrega un id a un archivo que no lo implementa ni lo prueba, solo para pasar la prueba.
   El README sigue el formato de `aidlc-docs/construction/contracts/code/README.md`, con una sección por componente: Keycloak y realm, `realm-lint`, Jobs (`realm-drift` y `signing-key-age`), gateway y `route-gen`, rate limit y Valkey, flujos y RBAC, observabilidad, e2e y carga, y GitOps.

2. **Correcciones de la revisión de código del PR 79** (`revisiones/U02-T17/`; los hallazgos los resume la Nota):
   - **Nota del Paso 12 del plan** (`aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`, nota C-05 del 2026-11-08): dice que `identity-jobs` incluye `keycloak-config-cli`, y es falso. Corrígela así: «`identity-jobs` (los CronJobs `realm-drift` y `signing-key-age`) va en la wave 4 para que no corran antes de que Keycloak esté sano. `keycloak-config-cli` no está en esta Application: es un hook `PostSync` de `keycloak` (INF-U2-05) y sigue bloqueado.» Conserva la fecha y la referencia a C-05.
   - **Tarea U02-T17** (`tareas/U02-T17-applications-gitops.md`):
     - en la tabla, la fila de `identity-jobs` deja de decir `keycloak-config-cli`;
     - la sección «Orden» deja de decir «misma wave» para `keycloak` → `identity-jobs`;
     - la frase del alcance de la demo vuelve a quedar fuera del bloque de la enmienda.
   - **Tablas de waves de los diseños.** En `aidlc-docs/construction/identity-edge/infrastructure-design/deployment-architecture.md` §2 va una fila de wave 4 con `identity-jobs` (`realm-drift` y `signing-key-age`), `identity-rules` e `identity-monitors`. En la fila de wave 3 de la misma tabla, `keycloak-config-cli` queda como hook `PostSync` de Keycloak, bloqueado. En `aidlc-docs/construction/platform-foundation/infrastructure-design/deployment-architecture.md` §3, la wave 4 suma «CronJobs, reglas y monitores de U2». Cada cambio lleva la nota «(revisión de código del PR 79, 2026-11-08)».
   - **Candidatas** en `CANDIDATAS.md`, con el formato de las entradas que ya tiene:
     - faltan en `STRICT` las dependencias de `namespaces` y `priority-classes` antes de los componentes de U2;
     - `SAME_WAVE_OK` tiene la misma carrera en otros pares, por ejemplo `mesh-certificates` y `priority-classes` → `linkerd-control-plane`;
     - el par `mesh-certificates` → `gateway` se exige en staging y prod, donde no aplica;
     - `keycloak` → `identity-monitors` es una dependencia de ejecución, no de instalación;
     - `EXPECTED_WAVES` y `FIXED_WAVES` se solapan, si no está ya.

   Revisa que no haya duplicados con las candidatas de U02-T17.
3. **Plan.** Marca `[x]` el Paso 15, con `(U02-T18)`.

**Fuera:**
- Cambios a `platform/tests/test_waves.py`, `components.yaml` o las Applications. Las dependencias que faltan van como candidatas.
- Pasos 16 a 18 de U2.
- Cambiar `test_traceability.py` para que acepte algo.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 12 y 15)
- `aidlc-docs/construction/identity-edge/` (FD, NFR, NFR Design, Infra)
- `aidlc-docs/construction/contracts/code/README.md` (formato del resumen)
- `platform/tests/test_traceability.py`
- `revisiones/U02-T17/` (rondas y revisiones de código)
- `tareas/U02-T17-applications-gitops.md`
- `CANDIDATAS.md`

## Criterios de aceptación

- [ ] **CA-1** — Trazabilidad completa de U2.
  ```bash
  uv run python platform/tests/test_traceability.py --unit identity-edge
  ```
  Esperado: código 0, sin ninguna línea «sin trazabilidad». **Rojo primero:** la salida de hoy, con los 7 que faltan, en la bitácora.

- [ ] **CA-2** — El resumen existe, enlaza bien y nombra cada componente.
  ```bash
  test -f aidlc-docs/construction/identity-edge/code/README.md && uv run python platform/tests/test_links.py
  ```
  Esperado: código 0, sin enlaces rotos.

- [ ] **CA-3** — Las correcciones están hechas.
  ```bash
  grep -n "keycloak-config-cli" aidlc-docs/construction/plans/identity-edge-code-generation-plan.md tareas/U02-T17-applications-gitops.md
  grep -n "identity-jobs" aidlc-docs/construction/identity-edge/infrastructure-design/deployment-architecture.md
  ```
  Esperado: ninguna línea dice que `identity-jobs` contiene `keycloak-config-cli`, y la tabla de U2 tiene `identity-jobs` en la wave 4.

- [ ] **CA-4** — `check` de U2 y de U1.
  ```bash
  make -C identity-edge check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

No hay código nuevo. El rojo es el de CA-1. Cada id que agregues a un archivo de `identity-edge/` se justifica en la bitácora (`bitacoras/U02-T18.md`) con la línea de código o la prueba que lo cumple.

## Notas

- Archivos que se modifican en su sitio: el plan de U2, la tarea U02-T17, los dos `deployment-architecture.md`, `CANDIDATAS.md` y los archivos de `identity-edge/` que reciben un id.
- Hallazgos de la revisión del PR 79 que esta tarea atiende:
  - (1) la nota de `keycloak-config-cli`;
  - (2), (3), (4), (7) y (8) como candidatas;
  - (5) las tablas de waves de los diseños;
  - (6) el texto de U02-T17.
