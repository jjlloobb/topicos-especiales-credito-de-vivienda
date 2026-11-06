# U02-T16 — El inventario e2e lee el Paso 13 con cualquier estado del checkbox

**Unidad:** U2 `identity-edge`
**Historias que implementa:** ninguna nueva. Corrige la prueba de CA-3 de U02-T14.
**Depende de:** U02-T14 (PR 70) en `main`, en 08e29d2.

`main` está en rojo desde el PR 70. Después de la revisión VERDE de U02-T14, el orquestador marcó el Paso 13 del plan como `- [x] … (U02-T14)` (commit b952c17). `identity-edge/tests/unit/test_e2e_inventory.py` busca el texto literal `- [ ] **Paso 13 — …**` y `- [ ] **Paso 14`, así que `text.index(STEP)` lanza `ValueError`. Con eso fallan 5 casos y `make -C identity-edge check` sale con error. El CI no lo detectó porque solo corre las pruebas de `platform`.

## Alcance

**Dentro:**

> `test_e2e_inventory.py` ubica el bloque del Paso 13 y el inicio del Paso 14 sin depender del estado del checkbox (`[ ]` o `[x]`) ni del sufijo entre paréntesis que se agrega al cerrar un paso (`(U02-T14)`). Lo demás de la prueba no cambia.

**Fuera:**

- El plan (`aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`): el Paso 13 queda `[x]`. No se desmarca.
- El contenido de `INVENTORY` y las pruebas e2e.
- Hacer que el CI corra las pruebas de `identity-edge`: va a `CANDIDATAS.md`.
- Otras pruebas que lean el plan. Si encuentras alguna con el mismo defecto, anótala como candidata.

## Archivos de contexto

- `identity-edge/tests/unit/test_e2e_inventory.py`
- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 13 y 14)
- `tareas/U02-T14-especificacion-e2e.md` (CA-3)
- `.github/workflows/tests.yml` y `.github/workflows/platform.yml`, solo para entender por qué el CI no lo detectó

## Criterios de aceptación

Todos los comandos se corren desde `vectra-risk/`.

- [ ] **CA-1** — La prueba pasa con el plan de `main` (Paso 13 en `[x]`).
  ```bash
  uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q
  ```
  Esperado: 6 passed (o más, si se agregan casos), 0 failed.

- [ ] **CA-2** — La prueba no depende del checkbox. Hay un caso que ejecuta la misma localización del bloque sobre el texto del plan con el Paso 13 en `[ ]` y en `[x]`, con y sin sufijo, y sobre el Paso 14 en los dos estados. En los cuatro casos el bloque que obtiene es el mismo.
  ```bash
  uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q -k "checkbox or state"
  ```
  Esperado: pasa. La bitácora muestra la corrida en rojo de ese caso contra la versión de 08e29d2.

- [ ] **CA-3** — La prueba sigue atada al texto del Paso 13. Si se borra del plan, en una copia, una viñeta del Paso 13 que esté en `INVENTORY`, la prueba falla.
  ```bash
  # mutación en una copia o con git stash; la bitácora muestra la salida
  ```
  Esperado: falla con la mutación y pasa sin ella.

- [ ] **CA-4** — U2 vuelve a verde.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: exit 0, sin fallos.

- [ ] **CA-5** — U1 sigue cumpliendo. Va en serie, después de CA-4.
  ```bash
  make -C platform check-local
  ```
  Esperado: exit 0.

## Plan de pruebas

- Rojo primero: correr CA-1 en 08e29d2 y registrar los 5 fallos.
- Un caso parametrizado sobre los estados del checkbox (CA-2).
- La mutación de CA-3.

## Notas

- Archivo que se modifica en su sitio: `identity-edge/tests/unit/test_e2e_inventory.py`. Nada más, salvo la bitácora `bitacoras/U02-T16.md` y, si las hay, candidatas en ella.
- La localización puede ser una expresión regular anclada al inicio de línea (`^- \[[ x]\] \*\*Paso 13 — …\*\*`). La forma la decides tú, siempre que se cumplan CA-2 y CA-3.
- U02-T15 (Paso 14) se está implementando en paralelo y cerrará el Paso 14. Por eso `NEXT_STEP` también tiene que aceptar los dos estados.
