# Ronda 1 — U00-T01

VEREDICTO: VERDE

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U00-T01`, rama `tarea/U00-T01`, sha `8229c7a3e883d4234540cd3814868078a9436d83`, base `d95782a`. El hash de la tarea coincide con `fe459e96bebc6e58d75083612c138e2726f02b0e`. El diff tiene un commit y 10 archivos: el modelo, dos pruebas, tres specs, tres `.d.ts` generados y la bitácora. No hay desborde de alcance.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `from_wire` rechaza `outcome` y `reasons` fuera del catálogo | `uv run --offline pytest contracts/tests/unit/test_outcome.py -q -k "outcome_outside_catalog or reasons_outside_catalog"` (en el worktree) | pasa: `2 passed, 16 deselected` |
| 2 | La spec de scoring trae los `enum` | `uv run --offline pytest contracts/tests -q -k recommendation_spec_has_enums` (en el worktree) | pasa: `1 passed, 457 deselected` |
| 3 | U0 cumple su plan completo | `UV_OFFLINE=1 uv sync --frozen && make -C contracts check`, en un clon del sha con `node_modules` enlazados del árbol principal | pasa: exit 0, `458 passed`, sin `skipped`, cobertura 97,78 %, puertas de cobertura, trazabilidad y bench en verde, `git diff --exit-code` sobre openapi, ts/generated y enums.generated sin diff, y tsc, eslint y vitest (8 passed) en verde |

## Comprobaciones adicionales que pidió el orquestador
- **§3.3 completo.** Comparé campo por campo `outcome/__init__.py:59-72` con domain-entities §3.3. `kind` es `Literal["recommendation"]`, `case_id` es UUID y `score` y `confidence` son `UnitDecimal4`. Ahora `outcome` es `Outcome` y `reasons` es `list[ReasonCode]` (§3.6). `model_version_id` y `policy_version_id` son `str`, y `explanation` es obligatoria. `registry_entry_id` es `str` con `min_length=1`, `evaluated_at` es `Timestamp` y `feature_vector_hash` es `Sha256Hex`. Los doce campos cumplen.
- **Guarda del token, con mutación.** En la copia reemplacé la condición de `_Guarded._require_token` por `if False:` y la prueba `test_br_u0_01_direct_construction_forbidden` falla (`DID NOT RAISE ContractViolation`, `1 failed`). El cambio a `Outcome.FAVORABLE` era necesario: con `outcome="favorable"` (str) y la guarda intacta, la validación estricta del campo lanza `ValidationError` antes de llegar a la guarda. Sin ese cambio, la prueba ya no ejercía la guarda. No la debilita.
- **Mutaciones de los tipos.** Revertir `outcome: Outcome` a `str` deja `2 failed, 1 passed` en los CA. Revertir `reasons: list[ReasonCode]` a `list[str]` deja también `2 failed, 1 passed`. Las pruebas de los CA detectan las dos regresiones.
- **`from_wire` con casos de borde** (`probe.py`). Rechaza con `ValidationError` estas variantes de `outcome`: `FAVORABLE`, `Favorable`, `" favorable"`, `"favorable "`, `""`, `null`, `1` y `sigue` (de `Decision`). Rechaza estas de `reasons`: `SCORE_BAJO_CORTE`, `Vis`, `" vis"`, `"vis "`, `favorable`, `model_frozen`, `timeout`, `decision_already_recorded` (de otros catálogos), la cadena suelta `"vis"`, `[null]` y `[1]`. Acepta los valores válidos.
- **Camino positivo con `reasons` no vacío** (`probe2.py`). `build_outcome` con `[VIS, PARAMETRO_NORMATIVO_NO_VIGENTE]` y `revision_requerida` produce una `Recommendation`. En el cable salen los valores en minúscula y el viaje de ida y vuelta por `from_wire` da `==` `True`.
- **Spec y cliente TS.** `scoring-service.yaml` gana los schemas `Outcome` y `ReasonCode`, y `case-service.yaml` gana `ReasonCode`; los demás ya los tenían. En los tres specs, `Recommendation.outcome` pasa a `$ref Outcome` y `reasons.items` a `$ref ReasonCode`. Los `.d.ts` tipan `outcome: components["schemas"]["Outcome"]` y `reasons: components["schemas"]["ReasonCode"][]`. Filtré las líneas cambiadas en openapi y ts y no queda ninguna ajena a `Outcome`, `ReasonCode`, `outcome` o `reasons`: no hay cambios no relacionados. `enums.generated.ts` no cambia y ya exportaba `OUTCOMES` y `REASON_CODES`.
- **Consumidores que pasen `str`.** Hice grep de `Recommendation`, `RecommendResult`, `build_outcome` y `from_wire` en todo `vectra-risk/` (identity-edge, platform, loop, contracts). Los únicos usos de producción son `models/api.py:106` (`CaseDetail.recommendation`, que recibe el tipo) y `routes/__init__.py:107`. Los fixtures de `PolicyResult` en tests, bench, property y examples ya usaban `Outcome.FAVORABLE`. Nadie pasa `str`. `build_outcome` pasó de `.value` a los miembros del enum, que es correcto con `StrictModel` en modo python.
- **Worktree.** `git status --short` sale vacío al final, HEAD está en `8229c7a`, la rama es `tarea/U00-T01` y el merge-base es `d95782a`. Todas las mutaciones las hice en el clon del scratchpad, y ese clon quedó revertido.

## Hallazgos
### F-01 · AMARILLO · vectra-risk/contracts/tests/unit/test_codegen.py:42 · La prueba de CA-2 solo comprueba que el enum de `ReasonCode` no esté vacío
`assert spec[...]["ReasonCode"]["enum"]` pasaría con un catálogo truncado o distinto. Bastaría con compararlo con `[r.value for r in ReasonCode]`, igual que se hace con los tres valores de `outcome`.

### F-02 · AMARILLO · vectra-risk/contracts/tests/unit/test_outcome.py:89-102 · Las pruebas de CA-1 no fijan la causa del error, y ninguna prueba cubre `reasons` no vacío
`pytest.raises(ValidationError)` no comprueba que el `loc` sea `outcome` o `reasons`, así que un `ValidationError` de otro campo también las haría pasar. Las mutaciones confirman que hoy sí detectan la regresión. Además, todos los fixtures usan `reasons=[]`, de modo que ninguna prueba de la suite recorre el nuevo `list(ready.policy_result.reasons)` de `build_outcome` con elementos. Yo lo verifiqué a mano en `probe2.py` y funciona, pero queda sin prueba.

### F-03 · AMARILLO · vectra-risk/bitacoras/U00-T01.md:132 · El verde de CA-3 en la bitácora no trae transcripción
La bitácora solo transcribe la corrida de `make check` que falló (líneas 95-126). La final, con exit 0, aparece como afirmación sin salida. Mi corrida la confirma, así que no bloquea, pero la evidencia del codificador está incompleta. La sección «Verde» (líneas 63-70) también muestra una corrida en rojo, y la explicación llega después, en la línea 81.

### F-04 · AMARILLO · vectra-risk/contracts/CHANGELOG.md · El cambio del contrato público no consta en «Sin publicar»
La spec de `Recommendation` pasa de `string` a enumerados cerrados, y el CHANGELOG lleva un registro de los cambios del contrato previos a la etiqueta. La tarea no lo exige, así que lo dejo al criterio del orquestador.

## Tareas candidatas (defectos reales fuera de alcance)
- `contracts/ts/src/wire.ts:2-8`: `RecommendationWire`, escrito a mano, no declara `outcome` ni `reasons` (usa `[key: string]: unknown`), y `parseRecommendResult` solo valida `kind`. El lado TS no ofrece una lectura tipada ni validada de los enumerados equivalente a `from_wire`. Valdría derivar el tipo de `components["schemas"]["Recommendation"]` o validar contra `OUTCOMES` y `REASON_CODES`.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t01-r1/ca3.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t01-r1/probe.py
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t01-r1/probe2.py
- Clon con las mutaciones ya revertidas: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t01-r1/repo

AMARILLO|vectra-risk/contracts/tests/unit/test_codegen.py:42|La prueba de CA-2 solo comprueba que el enum de ReasonCode no esté vacío
AMARILLO|vectra-risk/contracts/tests/unit/test_outcome.py:89|Las pruebas de CA-1 no fijan el loc del error y ninguna prueba cubre reasons no vacío
AMARILLO|vectra-risk/bitacoras/U00-T01.md:132|El verde de CA-3 se afirma sin transcripción
AMARILLO|vectra-risk/contracts/CHANGELOG.md:8|El cambio del contrato no consta en «Sin publicar»
INFORME: revisiones/U00-T01/ronda-1.md
VEREDICTO: VERDE
