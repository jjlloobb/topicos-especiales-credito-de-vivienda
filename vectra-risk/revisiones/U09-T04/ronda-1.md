# Ronda 1 — U09-T04

VEREDICTO: NO-VERDE

Revisé la rama `tarea/U09-T04` en 641450890451cf9252276b9e1fa2621e29c86d81, contra la base fe0c9f3. El blob de la tarea coincide (f467c7e…).

**Procesos del worktree `u09-t04`:** no había ninguno vivo cuando empecé, así que no paré nada. La carga de ≈ 62 venía de otros worktrees: `u03-t06`, `u04-t09` y `u00-t03`. El worktree sigue limpio al entregar.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (carga) | Resultado |
|---|---|---|---|
| 1 | Imagen | `hadolint`, `make image`, `inspect`, los dos `docker run`, `grep FROM` (62,7) | pasa: rc 0, `65532:65532`, `OK`, `OK-entradas`, 2 de 2 `FROM` por digest. La reconstrucción salió entera de caché, así que la imagen corresponde a las fuentes actuales |
| 2 | Render, esquema y `conftest` | `integration.py` ×3, `kubeconform -strict` ×3, `conftest` ×3 y `--combine chart_set` ×3 (53) | pasa: `Valid: 10` ×3, `660 passed` ×3, `14 passed` ×3. `test_chart.py` corre dentro del `check`, todavía sin resultado |
| 3 | Bóveda y realm | el `python -c vault_paths` y el `grep` del realm | pasa: `OK-boveda` y líneas 1182 y 1203 |
| 4 | Contenedor real | `test_image.py`, dentro del `make check` de U9 | **sin resultado mío todavía**. Lo revisé leyendo el código (ver abajo) |
| 5 | Admisión de U1 | `make -C platform check-chart …` (68,6) | rc 2 por el pánico de Kyverno, que confirmé: `panic: poddisruptionbudgets.policy "bias-monitoring-service" already exists`. `policy-chart-u1` corre dentro del `check` |
| 6 | Cuota y flujos | `render.py --check`, `generate.py --check` de red, `platform/network/tests`, los 7 F y los dos `grep` (54,6) | pasa: `211 passed`, ninguna línea «falta», F27 en la línea 179 y la negación U9 en la línea 18 |
| 7 | Application y trazabilidad | los comandos tal cual (55) | pasa: `pass: 1, fail: 0` ×3, wave `'5'` ×3, `valueFiles` ×3, sin `automated`, `35 identificadores`, rc 0. Solo salen «BR-U9-21/22 sin prueba», que son del Paso 13 y están en la lista con su cita, como permite CA-7 |
| 8 | Presupuesto de kind | `requested_gib()` con los pico declarados (63,9) | pasa: 9,265625 GiB con U9 y 8,9765625 sin U9; U9 aporta 0,2890625. Queda bajo `BUDGET_GIB` 9,3 y bajo el umbral de detención 9,49. El diff solo toca `BUDGET_GIB` y su comentario |
| 9 | N/A | `test ! -d …` | pasa |
| 10 | Cierre | `make -C bias-monitoring check` y `make -C platform check` | **en curso**: U9 empezó a las 11:28:53 con carga 64,5 y a las 12:17 iba en `coverage-bias` al 31 %. Las tres secciones del cierre y `imagenes.md` sí están |
| 11 | RL-4, todas las unidades | runner en serie: bias-monitoring, platform, governance, reference-model, model-serving, scoring-explainability, identity-edge, decision-registry, contracts | **no verificado**. `keycloakx` 7.4.0 ya estaba en el worktree y es idéntico al del árbol principal (`diff -r` sin diferencias), así que no copié nada |
| 12 | Plan | `git diff … \| grep Paso 1[1-8]` | pasa: los 8 pasos con el texto exigido, sin otros cambios |

## Hallazgos

### F-01 · NARANJA · `bias-monitoring/policies/conftest/cronjob.rego:204,211` (y `policy-ranges`) · la regla de la política admite valores que el CronJob rechaza

Es la misma clase de defecto que el codificador corrigió en `set.rego`. Lo comprobé con un render real del chart (`-f` con la política alterada) y las dos pasadas de `conftest`:
- `stale_after: "1h30m"`, `"90"` y `"abc"`: **ningún FAIL**, y `config.parse_policy` los rechaza con `stale_after_not_a_duration`.
- La causa: `not duration_seconds(...) >= 1800` con una función indefinida deja indefinido el cuerpo de la regla, y la regla no dispara.
- `n_min: "abc"` tampoco da ningún FAIL, y `parse_policy` lo rechaza con `n_min_not_an_integer`. Aquí pesa el orden entre tipos de Rego: `"abc" >= 30` vale verdadero.

La compuerta de cambio de INF-U9-03 y BR-U9-13 deja pasar una política con la que el CronJob falla en cada corrida.
- Lo que falta: booleanos aparte (`stale_ok`), comprobar que el valor es un número (`is_number`) y casos de fallo para los dos.
- Scripts: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/realrender.py` y `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/stale.py`.

### F-02 · NARANJA · CA-10 / CA-11 · el cierre sigue sin evidencia
- `cierre-demo.md`, fila 18, dice «No cerrado al entregar», y la bitácora dice «No declaro CA-10 ni CA-11 verificados».
- Mi corrida sigue en curso, así que esos criterios todavía no están verificados.
- Si mi corrida termina con todo en verde, el codificador tiene que actualizar la fila 18 y la bitácora con las cifras.

### F-03 · AMARILLO · `bias-monitoring/Makefile:99` · `check` no construye la imagen
- `test_image.py` corre contra la etiqueta `:dev` que ya exista, de modo que el `check` puede pasar con una imagen vieja.
- En esta ronda no pasó: mi `make image` salió entero de caché.
- Arreglo: poner `image` antes de `test` en `check`.

### F-04 · AMARILLO · `platform/tests/test_platform.py:285` · desborde mínimo en U1
- Agrega `"bias-monitoring"` a `EXPECTED_WAVES[5]`.
- Es la consecuencia mecánica de la entrada en `components.yaml`, y sin ella `make -C platform check` falla.
- Tiene precedente en U03-T05 (F-03, AMARILLO) y U04-T06 (aafe8e2), y ya está en `CANDIDATAS.md:303` («las tareas que agregan una Application deben nombrar este archivo»).
- Dictamen: es el mínimo necesario, **no es ROJO**. Es un hueco de la especificación de la tarea.

### Lo que preguntaste en los puntos 2, 4 y 5 (sin hallazgo)
- **`policy-chart-u1` (punto 4):** sí verifica lo que pide CA-5. Es el mismo `check-chart` de U1 (mismas `STATIC_POLICIES`, mismo `KYVERNO_OK`, `rego` y `--namespace hpa`), solo que con un entorno por directorio, igual que `decision-registry/Makefile`.
  - `require-hpa-bounds` no es Kyverno ni en `check-chart`. La exención la comprueba el `rego` `hpa`, como muestra el rojo R-02.
  - Es AMARILLO, sin bloquear: la lista `STATIC_POLICIES` está copiada en el Makefile de U9 y puede quedarse atrás si U1 la cambia.
- **Regla `identity` de `set.rego` (punto 5):** reconstruí la regla anterior (`not env_of(...) == mounted_secret_path(...)`) en una copia en el scratchpad y le apliqué la mutación `wrong_key_mount`.
  - Con la regla anterior: `14 passed`, rc 0. El rojo que reporta el codificador es real.
  - Con la regla actual: `FAIL identity: VECTRA_CLIENT_KEY_PATH de bias-monitoring-job…`, rc 1. La corrección funciona.
- **Service y F25 (punto 2):** el Service se llama `bias-monitoring-service`, expone 8080 y 8081, y está en `vectra-app`. Coincide con `peers.biasUrl` de `governance/chart/values.yaml:42`, que es lo que llega a `GOVERNANCE_BIAS_URL` (`governance/chart/templates/service.yaml:79`). Ningún values de entorno lo sobreescribe.
  - La prueba de imagen toma las variables del render y solo cambia las URLs y el issuer, con raíz de solo lectura y la llave montada en el path del chart.
  - Es AMARILLO: la CA (`VECTRA_CA_BUNDLE`) no la ejercita nadie, porque los dobles son http. Lo verá U12.

### F-05 · AMARILLO · `code/services.md` · P-2 (a) pedía quitar la sección
- P-2 (a) decía «quitar esa sección de `services.md`», y el codificador la reescribió con las cifras.
- Además, el texto («≈ 1 min 10 s más en `coverage-bias`») contradice los 13 min 20 s que el propio codificador midió.

## Tareas candidatas
- U1: `make -C platform check-chart` entra en pánico con los tres entornos en un mismo directorio. Confirmado otra vez; ya está registrada.
- U9: llevar `STATIC_POLICIES` a un solo origen en lugar de copiarlo en cada Makefile.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/checks/summary.txt`: rc, segundos y carga de cada unidad. El runner `run_checks.sh` sigue escribiendo ahí, si sobrevive a que yo termine.
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/checks/<unidad>.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/checkchart.log`: el pánico de Kyverno.

RL-4/RL-5 dicen que solo un ROJO bloquea. No hay ningún ROJO: F-01 y F-02 son NARANJA. Si este NO-VERDE bloquea la fusión lo decide el orquestador, no yo.

```
VEREDICTO: NO-VERDE
NARANJA|bias-monitoring/policies/conftest/cronjob.rego:204|policy-stale y policy-ranges admiten stale_after y n_min que el CronJob rechaza
NARANJA|CA-10/CA-11|cierre sin evidencia del check de todas las unidades
AMARILLO|bias-monitoring/Makefile:99|check no construye la imagen que prueba test_image.py
AMARILLO|platform/tests/test_platform.py:285|EXPECTED_WAVES fuera de alcance, minimo necesario
AMARILLO|code/services.md|seccion reescrita en vez de quitada (P-2 a), cifra de costo incoherente
INFORME: revisiones/U09-T04/ronda-1.md
```


## Anexo del orquestador: corrida de los `check` (CA-10 y CA-11)

El revisor entregó su informe mientras su runner `run_checks.sh` seguía corriendo. El runner terminó después. Copio sus resultados de `scratchpad/checks/summary.txt`, con la causa de cada rc ≠ 0 tomada de los logs. Corrió en serie sobre `6414508`.

| Unidad | rc | Segundos | Causa del fallo |
|---|---|---|---|
| bias-monitoring | 0 | 4304 | — |
| platform | 0 | 795 | — |
| governance | 0 | 793 | — |
| reference-model | 0 | 855 | — |
| model-serving | 0 | 452 | — |
| scoring-explainability | 0 | 631 | — |
| identity-edge | 2 | 3217 | Una sola prueba falla, `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` (2771 pasan). Es el fallo previo de `8d2cabd` y lo corrige U02-T20. |
| decision-registry | 2 | 1327 | Una sola prueba falla, `test_f04_300_mil…` (668 pasan). Es el límite de 2 s bajo carga, una candidata conocida que corrige U03-T07. |
| contracts | 2 | 324 | Solo falla `bench_gate`: `test_bench_pipeline p95 = 5.266 ms (limite 5.0)` con load de 10 a 14. Es la candidata de bench bajo carga (ver U04-T09). |

Ninguno de los tres fallos depende del diff de U09-T04: el diff no toca identity-edge, decision-registry ni contracts. Para F-02, el codificador cita estas cifras en la fila 18 y en la bitácora.
