# U02-T01 — Esqueleto de `identity-edge/`

**Unidad:** U2 `identity-edge`
**Historias que implementa:** ninguna todavía; prepara US-601 y US-611
**Depende de:** ninguna (U0 y U1 ya están en `main`)

Paso 1 del plan de U2.

## Alcance

**Dentro:**
- El directorio `identity-edge/` con la estructura de destino del plan (§1).
- Su `pyproject.toml`, que entra como miembro del workspace `uv`.
- Un `Makefile` con el objetivo `check`.
- Pruebas que usan los perfiles de Hypothesis de `contracts/tests/conftest.py`.

**Fuera:**
- Contenido de Keycloak, del realm, del gateway, del rate limit o de Valkey (Pasos 2 a 9).
- Applications de GitOps y entradas en `vectra-risk-gitops/components.yaml` (Paso 12).
- Cambios en `.github/workflows/` y en `platform/`.
- Dependencias nuevas que requieran red. Si `uv lock` necesita red, empuja de vuelta.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (§1 y Paso 1)
- `pyproject.toml` y `uv.lock` (workspace)
- `contracts/Makefile` y `contracts/tests/conftest.py` (patrón de `check` y perfiles de Hypothesis)

## Criterios de aceptación

- [ ] **CA-1** — El esqueleto pasa su `check` con el lock congelado.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: termina en 0.
- [ ] **CA-2** — Están los directorios de §1. Los vacíos llevan `.gitkeep`.
  ```bash
  for d in keycloak/themes/vectra keycloak/realm keycloak/values gateway/generated gateway/values ratelimit charts/valkey jobs observability runbooks tools tests/unit tests/property; do test -d identity-edge/$d || echo "FALTA $d"; done
  ```
  Esperado: sin salida.
- [ ] **CA-3** — Las pruebas de `identity-edge` cargan el perfil de Hypothesis del workspace. Lectura de vuelta: una prueba afirma que el perfil activo es el que fija `HYPOTHESIS_PROFILE`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q -k hypothesis_profile
  ```
  Esperado: `1 passed`.
- [ ] **CA-4** — U0 y U1 no se rompen.
  ```bash
  uv sync --frozen && uv run pytest contracts/tests -q -x -p no:cacheprovider && uv run ruff check identity-edge platform contracts
  ```
  Esperado: todo pasa.

## Plan de pruebas

**Rojo primero:** escribe la prueba de CA-3 antes que el `conftest.py` de `identity-edge` y registra su fallo.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster ni contra Docker** (`kubectl`, `helm install`, `argocd`, `docker start`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
