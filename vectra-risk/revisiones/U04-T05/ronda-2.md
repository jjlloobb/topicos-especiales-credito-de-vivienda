# Ronda 2 — U04-T05 (solo Paso 13)

VEREDICTO: NO-VERDE (ningún ROJO; dos NARANJA que, por RL-1..RL-5, no bloquean la fusión)

Rama `tarea/U04-T05` @ `6a1aff3`, base `be3eec8`. El alcance lo fija `arbitraje-ronda-1.md`: F-03, F-01 (con lo necesario de F-02), F-04 y F-05. Al terminar, el worktree estaba limpio salvo este informe.

## Criterios de aceptación y puntos del arbitraje, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| F-03 | CA interna y `VECTRA_CA_BUNDLE`; `ServiceTokenProvider` real | `pytest test_validation_job_template.py -v` | pasa (6/6). La prueba lee el entorno **del manifiesto**, comprueba el ConfigMap `vectra-internal-ca` (`ca.crt`, montado de solo lectura) y pide el token con `token_provider()` sin `poster`, contra un https local |
| F-01 | `outcome` de BR-U7-04/05 y BR-U9-01; oráculo hecho a mano | `pytest test_validation_job.py -v`, más la mutación `outcome = p < cutoff` (plugin en el scratchpad) | pasa (47/47). La mutación hace fallar `test_the_job_gives_each_row_the_outcome_..._cutoff`. Leí `outcome.py` contra la tabla de BR-U7-04: coincide regla por regla (igual a la usura no es «sobre», `cutoff_efectivo` por canal) y es la misma lógica que `vectra_reference.proxy.outcome_of`. Los 14 casos son literales, no la fórmula |
| F-02 (parcial) | Política activa pasada por el lanzador | lectura de `api.py` y `k8s_jobs.py`; la prueba de integración de `VECTRA_POLICY` (dentro de `make -C governance check`) | pasa. El literal `cutoff` ya no está |
| F-04 | hadolint | `<principal>/platform/.tools/bin/hadolint` v2.15.1 | rc 0 |
| F-05 | NFR-U4-23 trazado | `test_traceability.py --all` en la rama y en `git archive be3eec8` | rc 1 en las dos. El diff de las salidas solo **quita** `INF-U4-01` y `NFR-U4-23`; no hay ningún fallo nuevo |
| CA-2/3 | Pruebas del Job y de la plantilla | (las de arriba) | 53 passed en 125 s, 0 omitidas (helm presente) |
| CA-4 | Imagen | `make -C governance image-validation`; `docker image inspect`; `dpkg-query`; import; `--read-only` | build rc 0; `65532:65532`; `libgomp1 14.2.0-19`; `OK`; `missing_env:VECTRA_JOB_MODE` rc 1 |
| CA-5 | `check` de U4 y U1 | `make -C governance check`; `make -C platform check`, y el respaldo `test_ci.py` | U4: rc 0 (ruff, mypy --strict 27, import-linter 2 kept, **312 passed en 756 s**, con Postgres de testcontainers; promtool omitido). U1: 789 passed, falla en `check-tools` (no hay `.tools` en el worktree); el respaldo da **274 passed** |
| Conf. | `confidence` del Job = la de U5 | `test_confidence_is_the_one_u5_publishes` y un diff a ojo con `vectra_reference/envelope/confidence.py` | pasa. El algoritmo es idéntico; solo cambia la clase de error |

## Pregunta 2: 409 sin política `activa`
- **Contrato U0:** lo permite. `conflict_state` → 409 está en `ProblemCode`; `reason` es anulable, y el catálogo no tiene un motivo para «sin política». Se responde con `reason: null`. El `default: Problem` de la ruta lo admite.
- **Diseño U4:** BR-U4-05..07 no exigen una política activa para validar. Es una precondición nueva y no documentada, pero es la consecuencia directa de la decisión del arbitraje («el lanzador pasa la política activa»). Ver F-03 abajo (AMARILLO).
- **Pruebas:** las suites de integración se ajustaron con `with_active_policy`. Corren las 312 y está la prueba nueva del 409: sin corrida, sin Job y el estado sigue `registrado`.
- **Demo:** no la rompe. §1.0 de `demo-recorte-funcional.md` y `U04-T07` (líneas 37-38) activan la política antes de registrar y validar el modelo.

## Hallazgos

### F-01 · NARANJA · `validation_job/vectra_validation/features.py:73-76` · `proposed_rate_ea` llega al modelo como -1 (el defecto latente es real, y es del Job)
- **Raíz en U0:** `derive` → `_field_feature` devuelve `CategoryFeature("0.1500")` para `proposed_rate_ea`. El campo es `Decimal4 = str` (`labels.py:107-111`, `models/base.py:39`).
- **U5 y U6 lo esquivan:** U5 entrena esa columna como numérica (`BASE_SPEC`, `train.encode`). U6 (`origin/tarea/U06-T01`, `vectra_serving_common/model.py:56-63`) decide **por nombre**: si la feature está en `categorical_encoding`, codifica; si no, `float(raw)`.
- **El Job decide por el tipo del `FeatureValue`:** con `isinstance(item, CategoryFeature)` y sin vocabulario para esa columna, pone -1 en todas las filas.

Lo medí con `latent.py` en el scratchpad: modelo estilo U5 (codificación de `train.encode`), 6 000 filas de entrenamiento y 2 000 de validación.
- La columna del Job vale siempre `[-1.]`; las demás columnas son idénticas.
- `max |Δp| = 0,78` y `mean |Δp| = 0,023`.
- **AUC: 0,8630 con la codificación de U5 y 0,8482 con la del Job.** Cruza el `auc_target` de 0,85.
- `favorable@0,08`: 1 841 frente a 1 929. Esto desplaza también la `initial_disparity` que F-01 acaba de corregir.

Las pruebas lo esconden porque el fixture (`validation_support.xgboost_bytes`) entrena con la matriz del propio Job.

- **Pertenece a U4:** el código está en el diff de esta tarea, Paso 13. U0 es la causa de fondo: el tipo de la feature es ambiguo (ya es candidata, `CANDIDATAS.md:214` y `:343`).
- **Demos:** no rompe ninguna.
  - Scoring del flujo base: U6 codifica por nombre, así que no le afecta.
  - D1: `sync_check` compara el modelo consigo mismo y pasa igual.
  - D2: AUC y disparidad son informativas (BR-U4-07); el oráculo pide `initial_disparity` no vacía, y el freeze lo decide U9 con los outcomes reales.
- **Arreglo sugerido (no lo hago):** codificar por pertenencia a `categorical_encoding`, como U5 y U6.

### F-02 · NARANJA · `validation_job/vectra_validation/run.py:73-76` · El cableado de `confidence` y `channel` en `validate` no tiene prueba
Con `confidence` sustituida por `"1.0000"` en `run` (mutación por monkeypatch, `mut_conf.py`), **pasan las 47**. La regla 3 (baja confianza) y el `cutoff_efectivo` por canal solo se prueban en `outcome_of` aislado. La prueba de punta a punta cubre únicamente las reglas 1 y 2. Una regresión que deje de pasar la confianza o el canal real no se detectaría.

### F-03 · AMARILLO · `api.py:333-338` · Precondición nueva sin trazar en el FD de U4
El 409 por falta de política `activa` no figura en BR-U4-05 y sale con `reason` nulo. Conviene anotarlo en el FD o en el runbook (P-7/P-9) para que el operador no lo lea como un error de estado de la versión.

### F-04 · AMARILLO · `test_validation_job_template.py` (prueba de F-03) · La ruta de la CA del manifiesto se sustituye por `monkeypatch.setenv`
Es aceptable, porque el arbitraje permitía una CA de prueba y la prueba sí afirma la ruta y el montaje. Pero `_verify_context` lee `os.environ`, no la configuración, así que el valor del manifiesto no es el que se ejerce. Solo kind (U04-T07) lo confirma de punta a punta.

## Tareas candidatas (defectos reales fuera de alcance)
- U0: declarar el tipo de cada feature (en `derive` o en `FeatureSpecItem`) para que un `Decimal4` no salga como categoría. Ya está en `CANDIDATAS.md:214`.
- U4: el fixture del Job debería entrenar con la codificación de U5 (`vectra_reference.train.encode`), no con la matriz del Job. Si no, F-01 seguirá invisible.
- U4/U0: un `reason` de catálogo para «sin política activa», si se quiere distinguirlo de un 409 de estado.

## Rutas de transcripciones largas (scratchpad)
`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/`:
- `r2-unit-job.txt`, `r2-gov-check.txt`, `r2-plat-check.txt`, `r2-build.txt`;
- `r2-trace-branch.txt` y `r2-trace-base.txt`;
- `latent.py`, `mut/mut_plugin.py` y `mut/mut_conf.py`.
