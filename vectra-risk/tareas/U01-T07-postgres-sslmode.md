# U01-T07 — TLS exigido en PostgreSQL (`sslmode=verify-full`)

**Unidad:** U1 `platform-foundation`
**Historias que implementa:** US-605
**Depende de:** ninguna

Corrige el hallazgo N1 de `aidlc-docs/construction/platform-foundation/evidence/conformidad-2026-11-02.md`. El Paso 7 del plan de U1 está marcado, pero su aceptación incluye «`sslmode` exigido», y ni el manifiesto ni las pruebas lo imponen.

## Alcance

**Dentro:**
- **NFR-U1-22:** TLS cliente-servidor de PostgreSQL con la CA interna de cert-manager, `sslmode=verify-full` y TLS ≥ 1.2.
  - Que los `Cluster` de CloudNativePG (`platform/data/chart/`) **rechacen** conexiones sin TLS: reglas `pg_hba` con `hostssl` y sin `host` en texto plano.
  - Que los clientes que gestiona U1 se conecten con `verify-full`. Hoy el único es `restore-drill` (`drill.py`), que usa `sslmode=require`.
- La aceptación del Paso 7: `helm template` más una prueba que compruebe el `sslmode` exigido en el render.

**Fuera:**
- Clientes de otras unidades (U2 a U12).
- Cambiar la CA, los certificados o la malla de Linkerd.
- Ejecutar `psql` contra kind: el Paso 19 lo hace un operador después del PR.
- Las demás filas de la aceptación del Paso 7, que ya pasan.

## Archivos de contexto

- `aidlc-docs/construction/platform-foundation/nfr-requirements/nfr-requirements.md` (NFR-U1-22)
- `aidlc-docs/construction/plans/platform-foundation-code-generation-plan.md` (Paso 7)
- `aidlc-docs/construction/platform-foundation/infrastructure-design/` (INF-U1-02)
- `platform/data/chart/templates/clusters.yaml`, `platform/tests/test_platform.py` (`test_postgres_clusters`)
- `platform/restore-drill/drill.py` y `platform/restore-drill/tests/test_drill.py`
- `platform/mesh/certificates.yaml` (la CA interna)
- `aidlc-docs/construction/platform-foundation/evidence/conformidad-2026-11-02.md` (N1)

## Criterios de aceptación

- [ ] **CA-1** — En el render de los tres entornos, cada `Cluster` tiene reglas `pg_hba` que solo admiten `hostssl` para las conexiones TCP. Lectura de vuelta: la prueba lee el YAML renderizado, no los values.
  ```bash
  uv run pytest platform/tests/test_platform.py -q -k postgres_requires_tls
  ```
  Esperado: pasa en kind, staging y prod.
- [ ] **CA-2** — `restore-drill` se conecta con `sslmode=verify-full` y con la CA interna montada.
  ```bash
  uv run pytest platform/restore-drill/tests -q
  ```
  Esperado: todo pasa, y la aserción de `sslmode` exige `verify-full`.
- [ ] **CA-3** — El render está al día y U1 sigue cumpliendo sus verificaciones estáticas.
  ```bash
  make -C platform render && git status --porcelain platform/rendered && make -C platform check-local
  ```
  Esperado: `git status` sin salida y `check-local` en 0.

## Plan de pruebas

**Rojo primero:** escribe la prueba de CA-1 y cambia la aserción de CA-2 a `verify-full`. Registra que las dos fallan antes de tocar el chart y `drill.py`.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Implementa lo que dice el diseño. Si CloudNativePG no permite expresarlo como pide NFR-U1-22, o si el diseño y el plan no coinciden, detente y empuja de vuelta con la evidencia.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
