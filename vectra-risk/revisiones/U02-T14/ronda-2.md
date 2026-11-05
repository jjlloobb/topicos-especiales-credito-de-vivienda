# Ronda 2 — U02-T14

VEREDICTO: NO-VERDE

Corrí los siete criterios y todos pasan. F-01a/b/c a F-09 quedan cerrados en lo que pide el arbitraje: lo comprobé contra el código de los tags y con mutaciones.

El veredicto es NO-VERDE por una sola regresión. El diff cambia en silencio el orden de los flujos de autenticación de los tres realms, algo que no pidió nadie ni registra la bitácora. Es desborde de alcance, ROJO.

Al terminar el worktree está limpio (`git status --short` vacío, HEAD 85138d8). Las mutaciones las hice en una copia de `git archive` dentro del scratchpad.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`)
| # | Comando | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run ruff check identity-edge/tests/e2e` | pasa, exit 0 |
| 2 | `env -u VECTRA_E2E_BASE_URL uv run pytest identity-edge/tests/e2e --collect-only -q`, sin `VECTRA_E2E_*` ni `SYNTH_*` en el entorno | pasa: 26 casos, 0 errores |
| 3 | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa, 6 |
| 4 | `uv run pytest identity-edge/tests/unit/test_e2e_echo.py -q` | pasa, 45 |
| 5 | `make -C identity-edge collect-e2e && make -C identity-edge check` | pasa, exit 0: 2505 casos en 900 s. Los únicos «Skipped» son el `Skipped: 0` de kubeconform. Después de la orden de `test`, que lleva `--ignore=identity-edge/tests/e2e`, no aparece ningún archivo de `tests/e2e` |
| 6 | `make -C platform check-local && uv run pytest contracts/tests -q`, en serie después de CA-5 | pasa: platform 745, contratos 502, exit 0 |
| 7 | `realm_lint.py` sobre los 3 realms `&& pytest test_realm_lint test_realm_diff test_bruteforce_model -q` | pasa, 813 |

El exit 1 que reporta la tarea en segundo plano viene de un `tail -2` que puse al final de mi comando; las dos órdenes terminaron en 0.

## Comprobaciones contra los tags
- **F-01a (26.8.1).**
  - El modelo coincide con `DefaultBruteForceProtector.java`:
    - 121-127: rápido solo si `waitSeconds <= 0 && last > 0 && delta < quickLoginCheckMilliSeconds`.
    - 130-132: tope `maxFailureWaitSeconds`.
    - 133-134: un bloqueo rápido no suma `numTemporaryLockouts`.
    - 136: un bloqueo rápido siempre fija `notBefore`.
    - 161: permanente con `numTemporaryLockouts > max`.
  - El fallo rápido sí cuenta, porque `incrementFailures` (línea 106) va antes.
  - Un acierto llama a `clearFailures` (`LoginFailureEntity.java` 126-132), que pone a cero fallos, bloqueos y `lastFailure`.
  - Valores por defecto: `RealmManager.java` 278 (60 s) y 280 (1000 ms). Correctos.
  - Mutaciones que hacen fallar la prueba unitaria, como deben: rápido que suma bloqueo, sin tope, acierto que no olvida el último fallo, regla rápida desactivada, acierto que no reinicia los bloqueos, intento que cuenta durante el bloqueo.
- **H11.**
  - `KcEnvConfigSource.java` 88 transforma `_` en `-`, así que `KC_SPI_EVENTS_LISTENER__JBOSS_LOGGING__SUCCESS_LEVEL` da `kc.spi-events-listener--jboss-logging--success-level`.
  - `MicroProfileConfigProvider.MicroProfileScope` (76-80) busca `spi-` + `events-listener--` + `jboss-logging--` + `success-level`. El SPI se llama `eventsListener` (`EventListenerSpi.java` 36) y la fábrica lee `success-level` (línea 56).
  - El realm tiene `eventsListeners: [jboss-logging]` y los values no suben el nivel de log, así que con `info` el evento se escribe.
  - Mutaciones: sin la variable o con `debug`, fallan `test_h11_*` y `env-whitelist`.
- **H12.**
  - En v6.5.1, `application.properties` 52 fija `import.managed.required-action=full`. `RequiredActionsImportService.doImport` (68-73) borra las acciones que no están en el import y crea o actualiza las declaradas, así que `UPDATE_PASSWORD` declarada se conserva.
  - Los valores coinciden con `DefaultRequiredActions.addUpdatePasswordAction`.
  - `realm_lint` sale con exit 1 si se quita la acción y también si `enabled: false`.
- **F-03.**
  - `generated/kind/backendtrafficpolicies.yaml` 314-317 define el contador `console` como `Global`, con `clientSelectors.headers x-vectra-sub type: Distinct`.
  - Si el gateway tomara la cabecera del cliente, 60 valores distintos tendrían cada uno su contador, no habría 429 y la prueba fallaría. Detecta lo que debe.
- **F-04.** `envoyproxy/ratelimit` `src/limiter/cache_key.go` 101-102 usa `(now/divider)*divider`: ventana fija alineada al tiempo Unix. `wait_for_next_window` se alinea con eso. El ritmo de 21/s queda por debajo de los 200/s globales y la ráfaga dura unos 30 s, menos de la ventana de 60.
- **F-05.** `linkerd2-proxy-init` `pkg/iptables/iptables.go` 197-198 (`ignore-loopback`) deja el tráfico de `lo` fuera de la redirección, y la sonda `exec` no pasa por el kubelet ni por la red. El servidor escucha en 0.0.0.0. Mutaciones: un puerto 9090 o una IP que no es el loopback hacen fallar CA-4.
- **F-02, F-06, F-07, F-08, F-09.** Comprobados en el diff:
  - F-02: candidatas retiradas y línea de la bitácora marcada `[FALSO…]`.
  - F-06: `MFA_MAX_AGE`, `window_seconds` y `totp.interval`.
  - F-07: mutaciones nuevas, que pasan en CA-4.
  - F-08: `numTemporaryLockouts` en la invariante y en `settle`.
  - F-09: `kc-totp-settings-form` y `name="totp"`.

## Hallazgos

### F-10 · ROJO · `keycloak/realm/realm.{kind,staging,prod}.yaml` (7 ejecuciones cada uno) y `jobs/rendered/*/realm-configmap.yaml` · Desborde: se cambiaron prioridades de los flujos de autenticación
`git diff 8514930..85138d8 -- …/realm.kind.yaml` cambia `priority: 30` por `priority: 57` en siete ejecuciones de `authenticationFlows`, y lo mismo pasa en staging, prod y los tres ConfigMaps.

En `vectra-browser forms` el orden de los subflujos condicionales queda 10, 20, **57** (`vectra-mfa-cro`), 40, 50, 60, 70. Es decir, `vectra-mfa-cro` pasa del 3.er puesto a ir después de `vectra-mfa-operacion` y antes de `break-glass`. Los otros seis cambios son el subflujo `… factor` de cada `vectra-mfa-<rol>`.

Ni H12 ni el arbitraje autorizan tocar los flujos. La tarea dice: «Todo lo demás de los realms sigue fuera». La bitácora solo declara «acción `UPDATE_PASSWORD` (prioridad 57)», y ningún criterio lo detecta: CA-7 pasa con 30 y con 57. Parece un reemplazo global de `priority: 30` hecho al insertar la acción.

Hay que devolver las 21 prioridades a 30 en los realms y regenerar `jobs/rendered`.

### F-11 · AMARILLO · `tests/unit/test_bruteforce_model.py` · La guarda `wait <= 0` de la regla rápida no está cubierta
Si en el modelo se cambia `if wait <= 0 and previous …` por `if previous …`, los 45 casos siguen pasando. Falta un caso: el fallo número `failureFactor` llega rápido y debe dar la espera de la serie, con `temporary_lockouts == 1`, no un bloqueo rápido.

### F-12 · AMARILLO · `tests/e2e/test_e2e_bruteforce.py:128-134` · El instante del fallo se toma antes del intento
`self.model.wrong(at)` usa un `at` medido antes del `attempt()` HTTP, mientras que Keycloak fecha el fallo al procesar el POST. Si la latencia de un intento supera `QUICK_MARGIN_SECONDS` (0,5 s), el siguiente fallo puede ser rápido en Keycloak y no en el modelo. Conviene medir `at` después del intento, o ampliar el margen.

### F-13 · AMARILLO · `test_bruteforce_model.py`, docstring de la prueba del acierto · Referencia de línea
Cita la línea 122 para `last > 0`, pero está en la 123.

## Tareas candidatas
- Ninguna nueva.

## Transcripciones
Están todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/rev-t14-r2/`:
- `ca1.txt` a `ca7.txt`, uno por criterio.
- `dbfp.java`, `lfe.java`, `kcenv.java`, `mpcp.java`, `jlf.java` y `rais.java`: fuentes de los tags.

No tengo Write, así que no escribí `revisiones/U02-T14/ronda-2.md`: este mensaje es el informe completo.

```
VEREDICTO: NO-VERDE
ROJO|identity-edge/keycloak/realm/realm.{kind,staging,prod}.yaml (authenticationFlows) y jobs/rendered/*/realm-configmap.yaml|Desborde: 7 prioridades de flujos de autenticación cambiadas de 30 a 57 por realm (reordena vectra-browser forms), sin declarar
INFORME: revisiones/U02-T14/ronda-2.md
```
