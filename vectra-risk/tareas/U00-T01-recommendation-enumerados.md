# U00-T01 — `Recommendation` con enumerados cerrados

**Unidad:** U0 `contracts`
**Historias que implementa:** US-111
**Depende de:** ninguna

Corrige el hallazgo R1 de `aidlc-docs/construction/contracts/conformidad-2026-11-02.md`. El Paso 3 del plan de U0 está marcado, pero `Recommendation` no cumple lo que define el diseño.

## Alcance

**Dentro:** que `Recommendation` tenga los tipos de domain-entities §3.3:
- `outcome: favorable | desfavorable | revision_requerida`, el enumerado `Outcome` que ya usa `PolicyResult`;
- `reasons: list[ReasonCode]`.

Con eso, `RecommendResult.from_wire()` rechaza valores fuera del catálogo (BR-U0-20, NFR-U0-14, P-U0-03 capa 1). También hay que regenerar las specs OpenAPI y el cliente TS, que derivan de los modelos (Paso 15).

**Fuera:**
- El import circular de `outcome` (U00-T02).
- Otros campos o tipos de §3.
- Cambiar `Outcome` o `ReasonCode`.

## Archivos de contexto

- `aidlc-docs/construction/contracts/functional-design/domain-entities.md` (§3.3, §3.6)
- `aidlc-docs/construction/contracts/functional-design/business-rules.md` (BR-U0-20)
- `aidlc-docs/construction/contracts/nfr-requirements/` (NFR-U0-14) y `nfr-design/` (P-U0-03)
- `aidlc-docs/construction/plans/contracts-code-generation-plan.md` (Pasos 3, 4 y 15)
- `aidlc-docs/construction/contracts/conformidad-2026-11-02.md` (R1, con la evidencia)

## Criterios de aceptación

- [ ] **CA-1** — `from_wire` rechaza `outcome` y `reasons` fuera del catálogo. Lectura de vuelta: una prueba toma una `Recommendation` válida en forma de cable, cambia `outcome` a `"aprobado_a_ciegas"` y, en otro caso, `reasons` a `["cualquier_cosa"]`. En los dos espera error de validación.
  ```bash
  uv run pytest contracts/tests/unit/test_outcome.py -q -k "outcome_outside_catalog or reasons_outside_catalog"
  ```
  Esperado: `2 passed`.
- [ ] **CA-2** — La spec generada de scoring trae los `enum`. La prueba lee el YAML generado: `Recommendation.outcome` debe tener exactamente los 3 valores, y `reasons.items` debe referirse al enumerado de `ReasonCode`.
  ```bash
  uv run pytest contracts/tests -q -k recommendation_spec_has_enums
  ```
  Esperado: `1 passed`.
- [ ] **CA-3** — U0 sigue cumpliendo su plan completo.
  ```bash
  uv sync --frozen && make -C contracts check
  ```
  Esperado: termina en 0, con el código generado al día (sin diff).

## Plan de pruebas

**Rojo primero:** escribe las pruebas de CA-1 y CA-2 y registra que fallan con el código actual. CA-1 debe fallar porque `from_wire` acepta los valores.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red: si `make check` necesita algo de red, empuja de vuelta.
- Implementa lo que dice el diseño. Si el diseño y el plan no coinciden, detente y repórtalo.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
