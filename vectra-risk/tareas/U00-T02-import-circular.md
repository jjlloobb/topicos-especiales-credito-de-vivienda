# U00-T02 — Romper el import circular de `vectra_contracts.outcome`

**Unidad:** U0 `contracts`
**Historias que implementa:** US-111
**Depende de:** ninguna. Si `U00-T01` se fusiona antes, partir de ella.

Corrige el hallazgo N1 de `aidlc-docs/construction/contracts/conformidad-2026-11-02.md`. El Paso 4 del plan de U0 y el README dicen que los servicios usan `check_preconditions` y `build_outcome` de `vectra_contracts.outcome`. Hoy, si ese es el primer import del proceso, falla.

## Alcance

**Dentro:**
- Que `import vectra_contracts.outcome` y `import vectra_contracts.dictionary` funcionen como primer import, en un intérprete limpio.
- La cadena circular es `outcome` → `dictionary` → `models/__init__` → `models/api.py` → `outcome`. Se rompe sin cambiar la API pública ni el comportamiento.
- Una prueba que importe **cada** módulo público de `vectra_contracts` y `vectra_common` en un proceso aparte, para que no vuelva a pasar.

**Fuera:**
- Los tipos de `Recommendation` (U00-T01).
- Mover módulos de paquete o renombrar símbolos públicos.
- Cambios en `.importlinter` que relajen sus contratos.

## Archivos de contexto

- `contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py`, `dictionary.py`, `models/__init__.py`, `models/api.py`
- `contracts/.importlinter`
- `aidlc-docs/construction/plans/contracts-code-generation-plan.md` (Paso 4) y `contracts/README.md`
- `aidlc-docs/construction/contracts/conformidad-2026-11-02.md` (N1, con la evidencia)

## Criterios de aceptación

- [ ] **CA-1** — Los dos módulos se importan como primer import.
  ```bash
  uv run python -I -c "import vectra_contracts.outcome" && uv run python -I -c "import vectra_contracts.dictionary"
  ```
  Esperado: termina en 0, sin salida.
- [ ] **CA-2** — Una prueba importa cada módulo público en un subproceso limpio. La lista de módulos se deriva de los paquetes, no se escribe a mano.
  ```bash
  uv run pytest contracts/tests -q -k each_module_imports_in_isolation
  ```
  Esperado: pasa, con al menos un caso por módulo.
- [ ] **CA-3** — U0 sigue cumpliendo su plan, con import-linter intacto.
  ```bash
  uv sync --frozen && make -C contracts check
  ```
  Esperado: termina en 0.

- [ ] **CA-4** — La API pública de `vectra_contracts.models` no cambia frente a `c656de2`. Se comprueba en un proceso `python -I` limpio, sin nada precargado. El conjunto esperado se deriva de los submódulos de `models`, no se escribe a mano. La prueba compara:
  - los nombres de `from vectra_contracts.models import *`;
  - que `dir(models)` contenga esos nombres y `api`;
  - que `models.api` sea el submódulo;
  - que un nombre inexistente dé `AttributeError`.

  Lectura de vuelta: la prueba debe fallar si `__dir__` devuelve solo `globals()`, si `__dir__` omite `api` o si `__getattr__` no resuelve `api`.
  ```bash
  uv run pytest contracts/tests -q -k models_public_api_in_clean_interpreter
  ```
  Esperado: pasa. La bitácora registra las tres mutaciones fallando.

> **Enmienda del 2026-11-02 (orquestador, con aprobación del usuario):** se agrega CA-4. «Sin cambiar la API pública» no tenía un criterio con comando que lo comprobara, y eso llevó la tarea a 3 rondas (`revisiones/U00-T02/ronda-3.md`).

## Plan de pruebas

**Rojo primero:** escribe la prueba de CA-2 y registra que falla en `vectra_contracts.outcome` y `vectra_contracts.dictionary`.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Implementa lo que dice el diseño. Si el diseño y el plan no coinciden, detente y repórtalo.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
