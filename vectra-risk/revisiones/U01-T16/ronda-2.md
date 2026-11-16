# Ronda 2 — U01-T16

VEREDICTO: VERDE

No queda ningún ROJO ni NARANJA. Los cinco hallazgos de la ronda 1 están cerrados, y cada mutación de la ronda 1 que antes sobrevivía ahora la detecta una prueba. Quedan tres AMARILLO que no bloquean. Los criterios CA-1 a CA-7 pasan con mis propias corridas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Recuperar antes de generar | `-k "recover or recupera"`; con `--collect-only` selecciona 27, todas de `test_vault_from_cluster.py` | pasa, 27 |
| 2 | Informe sin secretos | `-k "report or informe"` (selecciona 7) | pasa, 7 |
| 3 | Namespaces de `identity/` | `-k namespaces` (selecciona 4) | pasa, 4 |
| 4 | Solo lectura | `shellcheck` 0.11.0 sobre los dos guiones: rc 0; el `! grep`: rc 0 | pasa |
| 5 | Runbook | El grep encuentra las líneas 64, 67 y 205; los guiones como los corre `make`: 56 alertas, 4 runbooks operativos, 650 archivos sin enlaces rotos | pasa |
| 6 | pytest de `platform` como la CI | Con `.tools` fuera del árbol y del PATH, y `.charts` presente: 1015 passed en 256,6 s, 0 omitidas. La guía de U12 (`test_kind_guide.py`, `test_kind_inventory.py`): 95 passed. `.tools` devuelto | pasa |
| 7 | `make -C platform check` | Una sola vez: rc 0 | pasa |
| — | `test_traceability.py --all` | rc 0 | sin fallos nuevos |

## Estado de los hallazgos de la ronda 1

**F-01 · cerrado.**
- `declared_clients()` lee los `clientId:` y `vaultKey: identity/clients/…` de los `values.yaml` de los charts reales. Al ejecutarla devuelve 9 clientes: bias-monitoring-job, bias-monitoring-service, case-service, case-worker, explainability-service, governance-service, model-validation-job, product-metrics y scoring-service.
- Al restarlos de los clientes con cuenta de servicio, y quitar keycloak-config-cli y keycloak-reader de identity-edge, quedan `channel`, `channel-simulator` y `verification-reader`.
- Una prueba fija esas 6 rutas generadas y otra el cierre «Se generaron valores nuevos en 5 ruta(s) que algo lee». Break-glass queda aparte.
- `install.md` (pasos 3 y 8) y la bitácora («Ronda 2», «Qué debe ver: seis rutas») dicen lo mismo que el código.

**F-02 · cerrado.**
- Ahora solo cuenta como literal un `fullmatch` de `{{ .clave }}`.
- Seis variantes con algo alrededor se informan como plantilla, y la exacta se recupera.
- Mutación: con la expresión vieja fallan 3 pruebas.

**F-03 · cerrado.**
- `gateway-address.sh`: si `kubectl` falla sale con 5, sin proponer línea de hosts, y las pruebas fijan 0, 1, 3, 4 y 5. Las tres mutaciones se detectan:
  - intercambiar 3↔4: 2 fallan;
  - mismatch a 5: 1 falla;
  - kubectl a 1: 1 falla.
- `seed-vault.sh identity`: se arregló la captura del listado de namespaces. Con la sustitución de proceso de antes, la prueba nueva falla (1 fallo). `local` va declarado antes, así que se conserva el código de salida.

**F-04 · cerrado (solo runbook).** El paso 9 «Valkey y `envoy-ratelimit`» va aparte y marcado como no medido. Comprobé los nombres en el repositorio:
- `valkey-a`, `valkey-b`, `sentinel-a` y `sentinel-b` son **StatefulSet** en `vectra-edge` (`identity-edge/charts/valkey/rendered/kind/valkey.yaml`, líneas 261, 370, 479 y 614). La orden del runbook es correcta.
- El Deployment del ratelimit en `envoy-gateway-system` se llama **`envoy-ratelimit`**: `deployment="envoy-ratelimit"` en `identity-edge/observability/rules/tests/identity-edge-rules-test.yaml:53`, y la etiqueta `app.kubernetes.io/name: envoy-ratelimit` en `identity-edge/ratelimit/policy/ratelimit.rego:21` y `observability/monitors/monitors.yaml:32`. Se puede poner en el runbook `kubectl rollout restart deployment/envoy-ratelimit -n envoy-gateway-system` en lugar de «nombre no verificado».
- `system-verification/docs/kind/identidad.sh` existe, y `humo login` es la función de la guía de U12.

**F-05 · cerrado.**
- Break-glass sale marcada «nadie la lee» y no cuenta en el cierre. Mutación: 1 falla.
- Un `Secret` que no es UTF-8 da un error propio que nombra `namespace/Secret` y la clave, sin bytes y sin causa encadenada. Mutación: 1 falla.
- Volvió al paso 3 la frase medida el 2026-11-14.

## Regresiones (punto 3): ninguna
Repetí las mutaciones de la ronda 1 sobre el código nuevo y todas se detectan:
- sin recuperación: 16 fallan;
- sin conflicto: 1 falla;
- sin comprobar que el `jwks` casa con la privada: 1 falla;
- toda plantilla tomada como literal: 10 fallan.

`fixed_value` y `TOKEN_PENDING` no cambiaron y sus pruebas pasan. El nuevo error de UTF-8 no incluye el valor.

## Hallazgos nuevos
### G-01 · AMARILLO · `platform/runbooks/install.md` líneas 173 y 207 · Siguen diciendo «pasos 4 a 8»
Ahora existe el paso 9. El paso 5 de «Tras reiniciar la máquina» manda a «los pasos 4 a 8 … para lo generado». Lo mitiga que el paso 3 enumere las 6 rutas y diga «Paso 9, enseguida» para Valkey. Se arregla con «4 a 9» en esas dos frases (la de «lo medido … 4 a 8» de la línea 173 sí es correcta).

### G-02 · AMARILLO · `vault_paths.py`, `line.unread = path in IDENTITY_EXTRA` · «Nadie la lee» sale de una constante, no de lo que el clúster lee
La respuesta dice que «depende de lo que algún `ExternalSecret` lee», pero la marca viene de la lista fija `IDENTITY_EXTRA`. Si un `ExternalSecret` vivo llegara a leer `identity/break-glass`, el cierre diría «nada que realinear» de todos modos. Hoy no pasa en kind. Se arregla comprobando la ruta contra el índice de `ExternalSecret` vivos que ya tiene `Recoverer`.

### G-03 · AMARILLO · `test_vault_from_cluster.py`, `CHART_VALUES` · Los charts se nombran a mano en la prueba
`declared_clients()` lee los charts de verdad, pero la lista de carpetas está escrita a mano: un chart nuevo con un `*-client` no entraría. Se podría recorrer `*/chart/values.yaml`.

## Respuesta al punto 4
- Los cuatro de Valkey y Sentinel son StatefulSet con esos nombres exactos.
- El ratelimit es `deployment/envoy-ratelimit` en `envoy-gateway-system`.

Higiene: no hice nada contra el clúster. Borré las copias `rev-u01t16-*` del scratchpad, el worktree quedó limpio (`git status --short` vacío) y `platform/.tools` volvió a su enlace.

```
VEREDICTO: VERDE
AMARILLO|platform/runbooks/install.md:173,207|Siguen diciendo «pasos 4 a 8» y el paso 9 de Valkey queda fuera del rango citado
AMARILLO|platform/kind/vault_paths.py (unread = path in IDENTITY_EXTRA)|«Nadie la lee» sale de una constante, no de los ExternalSecret vivos
AMARILLO|platform/kind/tests/test_vault_from_cluster.py CHART_VALUES|Charts nombrados a mano en declared_clients()
INFORME: revisiones/U01-T16/ronda-2.md
```
