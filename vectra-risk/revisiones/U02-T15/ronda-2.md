# Ronda 2 — U02-T15

VEREDICTO: VERDE

Revisé el diff completo de la tarea, de 08e29d2 a 69c408f, y el retrabajo de esta ronda, de 36d98b9 a 69c408f.
- **Tarea:** el hash de `tareas/U02-T15-especificacion-carga.md` en HEAD es 654f3fef47692416657883d03b4c8d6735ce57b6, el esperado.
- **Comandos:** corrí CA-1 a CA-6 desde `vectra-risk/`, con CA-6 en serie después de CA-5.
- **Mutaciones:** las hice en una copia sacada con `git archive 69c408f`. Están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/r2/copy/`.
- **Estado final:** el worktree queda limpio (`git status --short` no imprime nada) y en 69c408f.

Los seis hallazgos F-01 a F-06 están cerrados: cada mutación de la ronda 1 que antes sobrevivía ahora muere. No queda ningún ROJO ni NARANJA.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | k6 pinneado | `bash platform/install-tools.sh && platform/.tools/bin/k6 version` | pasa: `k6-v2.3.0-linux-amd64.tar.gz: OK` y `k6 v2.3.0 (commit/e088784614, go1.26.8)`. En la copia con `K6_SHA256=49c3…` sale `FAILED`, exit 1, y no queda `k6` en `bin` (`ca1-mut.log`) |
| 2 | `k6 inspect` sin entorno | `env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js` | pasa: exit 0. Trae los umbrales `{flow:login}` `p(95)<500`, `{flow:token}` `p(95)<200`, `{flow:jwks}` `p(95)<50`, `http_req_failed` `rate<0.01` y `checks` `rate>0.99` (`ca2.json`) |
| 3 | Script según el diseño | `uv run pytest identity-edge/tests/unit/test_load_spec.py -q` | pasa: 28 pruebas en 66,7 s. El tiempo se explica por dos corridas reales de k6 de 30 s contra gateways falsos |
| 4 | Usuarios de carga | `uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q` | pasa: 12 pruebas en 20,0 s |
| 5 | U2 y `load-inspect` en `check` | `uv sync --frozen && make -C identity-edge check` | pasa salvo lo conocido: `ruff` limpio, `load-inspect` corre (línea 211 del log) y pasa. Resultado: `5 failed, 2552 passed in 901.87s`, sin omitidas. Los 5 fallos son de `test_e2e_inventory.py` (U02-T16), exit 2 solo por ellos (`ca5.log`) |
| 6 | U1 con la herramienta nueva | `make -C platform check-local`, después de CA-5 | pasa: `745 passed`, `ca6=0` (`ca6.log`) |

## Cierre de los hallazgos de la ronda 1 (mutaciones en la copia, `mutaciones.log`)
| Hallazgo | Mutación | Resultado |
|---|---|---|
| F-01 | M11: `ok: true` fijo en `handleSummary` | muere: `test_a_p95_difference_over_the_budget_fails_the_verdict_and_make_load` |
| F-01 | M12: `verdict_problems` ignora `overhead` | muere: la prueba anterior y `test_a_verdict_without_rate_limited_responses_fails` |
| F-01 | M13: `make load` con `\|\| true` en lugar de `\|\| code=1` | muere: `test_a_p95_difference_over_the_budget…` |
| F-01 | M20: el tramo `direct` apunta a `BASE_URL` | muere: `test_the_two_legs_of_the_overhead_go_to_different_targets` y `…over_the_budget…` |
| F-01 | M21 (nueva): la diferencia con el signo invertido | muere: `…over_the_budget…` |
| F-03 | M19: sin el umbral `checks` | muere: 3 fallos (`test_the_script_matches_the_design` y dos mutantes `umbral:checks`) |
| F-03 | M19b: `checks: ['rate>0.5']` | muere: `test_the_script_matches_the_design` |
| F-04 | M18: el POST de `login-actions` etiquetado `flow:'token'` | muere: `test_every_request_is_tagged_with_the_flow_of_its_path` |
| F-02 | login 500→400 en NFR y en el script a la vez | **pasa** (28 pasan): ya no hay literal propio |
| F-02 | NFR-U2-11 5→7 en NFR y en el script a la vez | **pasa** (28 pasan) |
| F-02 | J7 1 %→2 % en el plan y en el script a la vez (`http_req_failed` y `checks`) | **pasa** (28 pasan): `checks` se deriva de J7 |
| F-02 | control: login 500→400 solo en el NFR | muere: 3 fallos, como debe |
| F-05 | se quita del oráculo la comprobación del rol | muere: los 4 `test_a_copy_with_a_role_that_requires_mfa_fails_the_oracle[cro, cumplimiento, ingeniero_riesgo, operacion]` |
| F-05 | se quita del oráculo la comprobación de `requiredActions` | muere: `test_a_copy_that_enrols_otp_fails_the_oracle` |
| F-05 | M15: el seed con `CONFIGURE_TOTP` | muere: 2 fallos |

Lo que muestran estas mutaciones:
- **F-01, lectura de vuelta:** la prueba que excede el presupuesto lee `overhead-verdict.json` (`ok:false`, `diff_p95_ms > budget_ms`) y además exige `make load` distinto de 0, así que no se queda en el código de salida. La prueba dentro del presupuesto exige `ok:true` y exit 0.
- **F-05:** las dos pruebas de copia mutada ya no son tautológicas. Si el oráculo se debilita, fallan.
- **F-06:** el docstring de `load_checks.py:3-4` está corregido. La bitácora mantiene la línea 16 original, que todavía dice `options.thresholds`, pero la sección «Ronda 2» la corrige de forma explícita. Es coherente con una bitácora que solo crece; no lo cuento como hallazgo.
- **Sweep F-02:** busqué los valores del diseño (500, 200, 50, 300, 900, 120, 20, 0,01, 0,99, `analista`, `load-`) en `test_load_spec.py`, `test_load_seed_users.py`, `load_checks.py` y `fake_gateway_server.py`. Solo quedan constantes del perfil reducido (10 usuarios, 30 s), valores de reemplazo de los mutantes y códigos HTTP. Ninguno fija un valor del diseño.
- **Alcance:** el retrabajo toca 6 archivos, todos dentro de la tarea. No toca `CANDIDATAS.md`, `routes.yaml`, los realms ni `install-tools.sh`.
- **Estabilidad:** las 15 corridas de `test_load_spec.py` (CA-3 y 14 mutantes) se hicieron mientras corrían en paralelo dos `make check` completos, el mío y el de U02-T16. La comparación de p95 dentro del presupuesto (≤ 5 ms entre dos gateways falsos) nunca dio un falso fallo.
- **Bitácora:** las afirmaciones de la ronda 2 coinciden con mi ejecución: 28 y 12 pruebas, `5 failed, 2552 passed`, `745 passed`, y M11, M12, M13, M18, M19 y M20 mueren.

## Hallazgos
Ninguno en pie. F-07 lo resuelve el orquestador al abrir el PR, según el arbitraje.

### F-08 · AMARILLO · `identity-edge/tests/unit/test_load_spec.py:80` · el mutante `console-burst:tasa` supone un límite mayor que 5
`int(ld.console_limit_per_second()) - 5` daría una tasa nula o negativa si el límite de `routes.yaml` bajara a 5/s o menos. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Siguen las de la ronda 1:
  - los buckets de `ratelimit_service_response_time_seconds` no resuelven 2 ms;
  - el sesgo del port-forward en el tramo `direct`;
  - J5 dice «por debajo de 10/s», pero el techo real son 5 logins/s porque cada login cuenta 2 hits.
- Los 5 fallos de `test_e2e_inventory.py` son de U02-T16.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/r2/`:
- `ca1.log`, `ca1-mut.log`, `ca2.json`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`
- `mutaciones.log`
- `mut.py`, el banco de mutaciones

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_load_spec.py:80|el mutante console-burst:tasa supone un limite de consola mayor que 5/s
INFORME: revisiones/U02-T15/ronda-2.md
```
