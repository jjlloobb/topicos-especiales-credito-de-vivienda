# Ronda 1 — U02-T20

VEREDICTO: VERDE

Corrí yo los 6 criterios sobre HEAD `eaa81a8` (base `1bb39b5` = `origin/main`) y los 6 pasan. El blob del archivo de la tarea es `a173a3b2f084510936a4f1d10bae8712e0598d55` y coincide con el esperado. No queda ningún ROJO ni NARANJA. Hay dos AMARILLO, que no bloquean.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | La prueba pasa, y hay rojo previo | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -k "t1_supply_chain" -v` | pasa: 8 passed, 136 deselected, 1.88s. Rojo previo reproducido: corrí la función de `origin/main` (`test_t1_supply_chain_skips_exactly_the_three_realm_configmaps`) contra el workflow actual y lanza `AssertionError` |
| 2 | Rojo en los dos sentidos (a)(b)(c) | Las 7 pruebas con `pytest.raises`, más una sonda propia (`probe.py`) con 7 mutaciones y 6 trampas sobre el texto en memoria | pasa: las 7 fallan por el motivo correcto (detalle abajo) |
| 3 | Sin cambios en el workflow ni en `.trivyignore` | `git diff --exit-code origin/main -- ../.github/workflows/supply-chain.yml .trivyignore` | pasa: rc=0. El diff `1bb39b5..HEAD` solo toca `CANDIDATAS.md`, la bitácora y `test_identity_jobs.py` |
| 4 | El `check` de la unidad | `make -C identity-edge check`, una sola vez y en serie, con los charts y herramientas que ya había en el worktree | pasa: rc=0, 2779 passed in 2530.51s (0:42:10). Carga al empezar 13.58 12.52 12.33 (15:22) y al terminar 10.50 11.97 12.46 (16:06) |
| 5 | Las otras guardas siguen en verde | `uv run pytest platform/tests/test_platform.py identity-edge/tests/unit/test_config_cli.py -k trivy_skips -v` | pasa: exactamente 2 seleccionadas, 2 passed |
| 6 | Entrada en `CANDIDATAS.md` | `grep -n "U02-T20" CANDIDATAS.md`, más `git diff --numstat` | pasa: está en la línea 480, marcada «Resuelta (U02-T20)» y cita F-01 de `revisiones/U03-T06/ronda-1.md` y `8d2cabd`. El numstat da `1 0`: una línea añadida y ninguna quitada |

### CA-2 en detalle (lo corrí yo, sin tocar el archivo real)
- **Las 7 mutaciones del diff.** Probé quitar cada una de las 5 entradas (el YAML queda válido, con 4 entradas), añadir `kind/keycloak.yaml` y añadir el comodín `rendered/*/keycloak.yaml`. Las 7 lanzan `AssertionError` en la línea 446, `assert skipped == _expected_skip_files()`. Ninguna falla por un YAML roto ni por un `ValueError`.
- **Trampas que probé por mi cuenta.** Todas lanzan `AssertionError` en la línea 446:
  - la lista reordenada;
  - un comodín en lugar de una entrada (misma cantidad de entradas);
  - un archivo inexistente en lugar de una entrada;
  - una entrada duplicada;
  - `keycloak/rendered/staging/keycloak.yaml` añadido.
- **Lo demás se conserva.** Si se cambia `KSV-0109` falla en la línea 452, y si se cambia `trivyignores` falla en la 453. Si se añaden espacios tras las comas, la prueba pasa, como debe, porque la lista equivale a la original.
- **Las afirmaciones secundarias sí funcionan.** Para comprobarlo cambié a la vez la lista esperada y el workflow:
  - con un comodín, falla en la línea 447;
  - con un archivo inexistente, en la 449;
  - con `kind/keycloak.yaml`, en la 450;
  - con `prod/keycloak.yaml`, en la 451.
- **P-2.** La lista vigente es la mínima: `keycloak.yaml` queda fuera de `skip-files` y se escanea entero.

## Hallazgos

### F-01 · AMARILLO · `identity-edge/tests/unit/test_identity_jobs.py`, `test_t1_supply_chain_skip_list_fails_when_an_entry_or_wildcard_is_added` · La prueba de añadir podría pasar en vacío
En esta prueba, `_mutated(...)` se evalúa dentro del `with pytest.raises(AssertionError)`, y `_mutated` tiene su propio `assert old in line`. Lo comprobé: `_mutated("not-in-line", "x")` lanza `AssertionError`. Si mañana `skip-files` pasa a ocupar varias líneas, o cambia su última entrada, esta prueba seguiría en verde por el `assert` auxiliar y no por la guarda. Hoy no pasa: mi sonda confirma que el fallo sale de la línea 446. Además, la prueba principal fallaría en ese mismo escenario, así que no hay nada oculto en este momento. La prueba de quitar ya lo hace bien, porque llama a `_mutated` fuera del `with`.

### F-02 · AMARILLO · El mismo archivo · `range(5)` está fijo, y ninguna mutación ejercita las afirmaciones secundarias
- `@pytest.mark.parametrize("index", range(5))` no crece con `_expected_skip_files()`. Una sexta entrada se quedaría sin su prueba de quitar.
- Las 7 mutaciones mueren en la igualdad. Ninguna prueba del diff llega a las afirmaciones de comodín, existencia, `keycloak.yaml` y staging/prod. Yo comprobé que funcionan, pero no queda fijado en la suite.

CA-2 no pide más que esto, así que no bloquea.

## Comprobaciones adicionales
- La evidencia de la bitácora es coherente con el diff actual. El rojo previo cita `Left contains one more item: '…/config-cli-realm.yaml'` y yo lo reproduje.
- No hay desborde de alcance. Las pruebas de U1 y de `test_config_cli.py` siguen intactas (P-3 (a)), y la duplicación quedó registrada como candidata.
- Al terminar, el worktree está limpio (`git status --short` vacío) y HEAD sigue en `eaa81a8`.
- Ninguna prueba se salta. Que el `check` tarde 42 minutos se explica por la carga de la máquina.

## Tareas candidatas (defectos reales fuera de alcance)
- Ya la registró el codificador y la confirmo: `make -C identity-edge check` necesita `platform/.charts/envoy-gateway`, que no está en el árbol principal. Convendría anotarlo en la guía de despacho.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u02-t20-r1/u02t20-check.log` (CA-4, con la carga al empezar y al terminar)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u02-t20-r1/probe.py` (sonda de mutaciones y trampas)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u02-t20-r1/probe2.py` (afirmaciones secundarias)

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_identity_jobs.py:test_t1_supply_chain_skip_list_fails_when_an_entry_or_wildcard_is_added|La prueba de añadir podría pasar en vacío por el assert de _mutated dentro de pytest.raises
AMARILLO|identity-edge/tests/unit/test_identity_jobs.py:parametrize range(5)|range(5) fijo y ninguna mutación ejercita las afirmaciones secundarias
INFORME: revisiones/U02-T20/ronda-1.md
```
