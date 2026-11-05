# Ronda 2 — U02-T11

VEREDICTO: NO-VERDE

Revisé 4ec7946 contra 54d76a3 (lo de esta ronda) y contra 1cd6bfd (`main`, el diff completo). El hash de la tarea es 123403e214dee2cacb418d62838283790c0adfc3, el esperado. Corrí CA-1 a CA-5 desde `vectra-risk/` uno detrás de otro, CA-4 antes que CA-5. Los cinco terminan en 0 y no se omite ninguna prueba. Al final el worktree está limpio (`git status --short` sin salida) y sigue en 4ec7946.

Las reglas de R6, R7 y R8 sí detectan los cambios: conftest y pytest fallan en todas mis mutaciones. Quedan dos hallazgos NARANJA: al oráculo le falta comprobar algo y la enmienda prohíbe literales que siguen en las pruebas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Descriptores | `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py -q` | pasa: 34 pruebas en 41,0 s |
| 2 | `envoy-ratelimit` | `make -C identity-edge render-envoy-gateway policy-ratelimit && uv run pytest …test_envoy_gateway_values.py …test_ratelimit_deployment.py -q` | pasa: conftest 1763/1763 y 1/1; pytest 140 pruebas en 65,3 s |
| 3 | Chart de Valkey | `make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && uv run pytest …test_valkey_chart.py -q` | pasa: conftest 112/112 y 3/3 por entorno; kyverno `pass: 40, fail: 0` en los tres; pytest 132 pruebas en 33,9 s |
| 4 | K11 | `make -C platform check-local` | pasa: 622 pruebas en 172 s; «222 archivos Markdown sin enlaces rotos» |
| 5 | Regresión | `uv sync --frozen && make -C identity-edge check` | pasa: 2325 pruebas en 767 s, sin omitidas ni deseleccionadas |

## Mutaciones mías (copia `git archive 4ec7946`, volviendo a renderizar cuando toca)
| Mutación | `make` de CA-2/CA-3 | pytest |
|---|---|---|
| M0, ninguna | 0 | 132 passed |
| M1, `values/prod.yaml` con `banco-z1`/`banco-z2` | 2 (`zones:` ×4) | 3 failed |
| M2, `values/staging.yaml` con `banco-z1`/`banco-z2` | 2 (`zones:` ×4) | 3 failed |
| M3, staging con A y B intercambiadas | 2 (`debe ir a la zona … (R6)` ×4) | 3 failed |
| M4, prod con solo `sentinel-b` en `zone-a` | 2 | 2 failed; **el oráculo no lo ve** (F-01) |
| M5, M6, `downAfterMilliseconds` 3000 y `failoverTimeout` 30000 en `values.yaml` | 2 (`sentinel-timing` ×6) | 7 failed |
| M7, `parallelSyncs: 2` solo en prod | 2 | 4 failed |
| M8 y M9, el diseño cambia las zonas a `zone-x`/`zone-y` o down-after a 4000 | 0 | 7 y 5 failed (también la prueba del literal, F-02) |
| M10, M11, M13, `TRACING_EXPORTER_PROTOCOL` quitado, `http` o `GRPC` | 2 (`telemetry … (R8)` en kind y en el banco) | 8 failed |
| M12, el diseño de R8 pasa a `http` | 0 | 9 failed |

## Hallazgos

### F-01 · NARANJA · `identity-edge/tests/unit/test_valkey_chart.py:118-145` · el oráculo no compara la zona de `sentinel-a` ni la de `sentinel-b`, y la bitácora dice que sí
- **El fallo.** El dict `zones` incluye `sentinel-a` y `sentinel-b`, pero la comprobación de zona está dentro de `for name, priority in priorities.items()`. Ese bucle solo recorre `valkey-a` y `valkey-b`. El bucle de `design.sentinel_layout()` no mira la zona, así que las entradas de Sentinel en `zones` no se usan nunca.
- **Lo demuestra M4.** Con `sentinel-b` en `zone-a` en prod, `test_the_render_of_each_environment_follows_the_design[prod]` pasa. Solo fallan `test_the_render_meets_the_policies[prod]` y `test_the_zones_of_every_environment_are_the_ones_of_the_design[prod]`.
- **Hoy R6 queda cubierto** por esa prueba aparte y por conftest. Pero CA-3 pide que el oráculo lea del diseño cada valor que el diseño fija, y INF-U2-04 fija «`sentinel-a` … a `zone-a` … `sentinel-b` a `zone-b`».
- **La afirmación falsa.** La bitácora (Ronda 2, «Cambio») dice: «el oráculo compara la zona de los 4 StatefulSet en los tres entornos». No es así.
- **Prueba sin cobertura.** `test_another_zone_in_the_values_fails_the_oracle_and_conftest` solo pasa porque cambia también las zonas de Valkey. Si solo cambiara las de Sentinel, el oráculo no fallaría.

### F-02 · NARANJA · `test_valkey_chart.py:226`, `test_valkey_chart.py:262-267`, `test_ratelimit_deployment.py:355` · pruebas que fijan R6–R8 con un literal propio
La enmienda de la tarea dice: «Ninguna prueba debe fijar estos valores con un literal propio». Encontré tres casos:
- `assert (zone_a, zone_b) == ("zone-a", "zone-b")`, dentro de `test_the_zones_of_every_environment_are_the_ones_of_the_design`;
- `test_the_sentinel_times_are_read_from_the_design`, que repite las tres directivas como literales;
- `assert design.ratelimit_tracing_protocol() == "grpc"`.

Lo demuestran M8 y M9: si cambian a la vez el diseño y el chart, estas pruebas fallan igual, así que el valor queda copiado en las pruebas. Que el oráculo siga al diseño ya lo garantizan `DESIGN_CHANGES` y las comprobaciones del modelo. No cuento los literales de `valkey.rego` y `ratelimit.rego` (`node_zone`, `sentinel_master_conf`, `"grpc"`): son la política misma, que es lo que se aceptó en la ronda 1. Si el orquestador interpreta la enmienda solo para el oráculo, F-02 baja a AMARILLO, pero eso lo arbitra él.

### F-03 · AMARILLO · `bitacoras/U02-T11.md:164` · la respuesta a F-05 no es exacta
Dice «Corregido en 3d66e5a (retiro)» y a la vez «No hay cambio de código». 3d66e5a no toca la bitácora. Además, la candidata sigue escrita en la línea 112 sin ninguna marca de retirada. No está en `CANDIDATAS.md`, así que no hace daño.

### Lo comprobado sin hallazgo
- **F-01 de la ronda 1, cerrado en el código.**
  - `valkey.rego` exige `zone-a`/`zone-b` y A→zone-a, B→zone-b (M1–M4).
  - La regla `sentinel-timing` tiene un caso por directiva (M5–M7).
  - `parallelSyncs` deja de ser un literal de la plantilla.
  - El render versionado no cambia.
- **F-03 y F-04 de la ronda 1.** Sin cambios: `templates/valkey.yaml` y `sentinel.yaml` no están en el diff de esta ronda.
- **R8 contra el código de origen (`gh api`).**
  - En `envoyproxy/ratelimit` `5ae0682e`, `src/settings/settings.go:316` declara `TRACING_EXPORTER_PROTOCOL`, con default `"http"`.
  - `src/trace/trace.go:72-84` acepta exactamente `"http"`, `""` o `"grpc"`. Con cualquier otro valor, `Fatalf`.
  - `grpc` en minúsculas es correcto, y M13 confirma que `GRPC` se rechaza.
  - En Envoy Gateway v1.9.3, `internal/infrastructure/kubernetes/ratelimit/resource.go` no fija esa variable, así que no choca con la env del usuario.
- **Valores leídos del diseño.**
  - `zones()` lee «Las zonas se llaman … en los tres entornos».
  - `sentinel_timings()` exige las tres directivas de INF-U2-04.
  - `ratelimit_tracing_protocol()` lee la enmienda de INF-U2-03.
  - M8, M9 y M12 hacen fallar el oráculo cuando cambia el diseño.
- **Alcance.** Los archivos de 3d66e5a están todos dentro del alcance enmendado.

## Tareas candidatas (defectos reales fuera de alcance)
- **Diseño, del orquestador.** `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md:116` todavía dice «`zone-a` y `zone-b` en kind; las zonas de cada entorno van en los values». La enmienda R6 (línea 150) lo contradice, y esa línea no está marcada como superada.

## Notas
- Mis mutaciones corrieron en la copia del scratchpad al mismo tiempo que CA-1 a CA-4. CA-4 y CA-5 corrieron en serie entre ellos.
- En mi scratchpad hay archivos que no son míos (`ronda2.md`, `r2-ca*.log`, `prod.bak`, `kind.bak`), con la misma marca de tiempo que la bitácora del codificador. No los uso como evidencia.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/r2/ca1.log` a `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/r2/ca5.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/r2/mutations.log`, con el detalle en `mut-m*.make.log` y `mut-m*.pytest.log` del mismo directorio
- Copia de las mutaciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/copy2/vectra-risk`

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/unit/test_valkey_chart.py:118-145|el oráculo no compara la zona de sentinel-a ni de sentinel-b, y la bitácora dice que sí
NARANJA|test_valkey_chart.py:226, :262-267; test_ratelimit_deployment.py:355|pruebas que fijan R6–R8 con un literal propio, contra la enmienda de la tarea
INFORME: revisiones/U02-T11/ronda-2.md
```
