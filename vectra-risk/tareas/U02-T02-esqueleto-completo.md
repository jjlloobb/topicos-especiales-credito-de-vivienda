# U02-T02 — Completar el esqueleto de `identity-edge/` según §1

**Unidad:** U2 `identity-edge`
**Historias que implementa:** ninguna todavía; prepara US-601 y US-611
**Depende de:** U02-T01

Cierra el Paso 1 del plan de U2. `U02-T01` dejó fuera `tests/e2e/` y `tests/load/`, que la estructura de destino (§1) incluye.

## Alcance

**Dentro:**
- Que `identity-edge/` tenga **todos** los directorios de la estructura de destino de §1 del plan, incluidos `tests/e2e/` (Playwright) y `tests/load/` (k6).
- Una prueba que compare el árbol real con §1, para que el esqueleto no vuelva a quedar incompleto.

**Fuera:**
- Contenido de las pruebas de extremo a extremo y de carga (Pasos 13 y 14).
- Archivos que §1 nombra pero que crean otros pasos (`keycloak/Dockerfile`, `gateway/routes.yaml`, `tools/*.py`).
- Cambios en `.github/workflows/`, `platform/` y `contracts/`.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (§1 «Estructura de destino» y Paso 1)
- `identity-edge/` y `bitacoras/U02-T01.md`

## Criterios de aceptación

- [ ] **CA-1** — Existen todos los directorios de §1.
  ```bash
  for d in keycloak/themes/vectra keycloak/realm keycloak/values gateway/generated gateway/values ratelimit charts/valkey jobs observability runbooks tools tests/unit tests/property tests/e2e tests/load; do test -d identity-edge/$d || echo "FALTA $d"; done
  ```
  Esperado: sin salida.
- [ ] **CA-2** — Una prueba lee la lista de directorios de §1 **desde el plan** y la compara con el árbol de `identity-edge/`. Lectura de vuelta: falla si se borra cualquiera de ellos.
  ```bash
  uv run pytest identity-edge/tests -q -k skeleton_matches_plan
  ```
  Esperado: `1 passed`.
- [ ] **CA-3** — El Paso 1 sigue cumpliendo su aceptación del plan.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: termina en 0.

## Plan de pruebas

**Rojo primero:** escribe la prueba de CA-2 antes de crear `tests/e2e/` y `tests/load/`, y registra su fallo.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
