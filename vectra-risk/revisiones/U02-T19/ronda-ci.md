# Arreglo del CI (KSV-0109) — U02-T19, PR 85

**VEREDICTO: VERDE.** Corrí yo mismo las cinco comprobaciones y todas pasan. No hay ningún ROJO ni NARANJA, solo dos AMARILLOS que no bloquean. Revisé `git diff 4e711e6 8d2cabd` en el worktree del codificador, en el sha 8d2cabd. Al terminar, el worktree sigue limpio (`git status --short` sin salida).

Contexto: decisión del usuario del 2026-11-09. El ConfigMap `keycloak-config-cli-realm` se separa en `rendered/kind/config-cli-realm.yaml` y solo ese archivo entra en `skip-files`, como en la decisión T1.

## Comprobaciones
| # | Comprobación | Lo que corrí | Resultado |
|---|---|---|---|
| 1a | `config-cli-realm.yaml` contiene solo el ConfigMap | `grep '^kind:'` | pasa: 1 documento, `ConfigMap keycloak-config-cli-realm` |
| 1b | `keycloak.yaml` ya no contiene el ConfigMap | `grep -c '^kind: ConfigMap'` | pasa: 0. Solo queda la referencia del volumen del Job (línea 517) |
| 1c | Trivy sobre `rendered/kind/keycloak.yaml` | `trivy config --severity HIGH,CRITICAL --ignorefile vectra-risk/.trivyignore --exit-code 1 …/kind/keycloak.yaml` | pasa: 0 hallazgos, código 0 |
| 1d | `skip-files` hace falta y basta | `trivy config` sobre `keycloak/rendered`, con y sin el skip | con el skip: los tres `keycloak.yaml` en 0, código 0. Sin él: solo `kind/config-cli-realm.yaml` da KSV-0109 (HIGH), código 1 |
| 1e | `skip-files` suma solo el archivo nuevo | diff de `.github/workflows/supply-chain.yml` | pasa: una sola entrada añadida al final |
| 2 | Staging y prod sin cambios | `git diff --quiet 4e711e6 8d2cabd -- …/rendered/staging …/rendered/prod` | pasa: código 0 |
| 3a | La división no pierde ni duplica documentos | comparé con PyYAML el `keycloak.yaml` de 4e711e6 contra `keycloak.yaml` + `config-cli-realm.yaml` | pasa: 19 documentos en ambos lados, idénticos uno a uno |
| 3b | Es determinista y el render coincide con Git | `git archive 8d2cabd` en una copia y `make -C identity-edge render-keycloak` dos veces | pasa: `git diff` vacío las dos veces |
| 3c | Falla si no hay exactamente un ConfigMap | el script con 0 ConfigMaps (con `keycloak.yaml` como entrada) y con 2 | pasa: código 1 en ambos casos, con el mensaje «hay 0» / «hay 2», y no escribe archivos |
| 4a | Las reglas de `identity-edge` | `make -C identity-edge check-keycloak-rendered policy-keycloak policy-keycloak-u1` | código 0: 4410 passed, `--combine` 11 de 11 por entorno, U1 `pass: 21` y `pass: 13` |
| 4b | Las pruebas unitarias | `uv run pytest identity-edge/tests/unit -k "keycloak or config_cli"` | **602 passed en 619 s**, código 0. El tiempo es real: no se saltaron |
| 4c | `generate.py` | `uv run python vectra-risk-gitops/generate.py --check` | código 0 |
| 4d | `platform` | `make -C platform check` | código 0: pytest 784 passed en 925 s, y el resto de suites (conftest, kyverno, promtool, chart lint) también pasa |
| 5 | La prueba de plataforma no se debilitó | lectura del diff de `test_platform.py` | pasa: sigue comparando con `==` la lista exacta, suma solo `…/keycloak/rendered/kind/config-cli-realm.yaml` y mantiene la prohibición de comodines |

Dos notas sobre cómo lo corrí:
- En la copia hecha con `git archive` me quedé sin cuota de disco al instalar el `.venv`. Por eso enlacé `.tools` y `.charts` del worktree y corrí con `UV_NO_SYNC=1 UV_PROJECT_ENVIRONMENT=<venv del worktree>`. El script de división solo usa la biblioteca estándar, así que esto no altera el resultado.
- Intenté también un `trivy config` sobre todo `vectra-risk` y se cortó por tiempo en mi máquina (`context deadline exceeded`). No es un fallo del diff. Lo sustituí por el escaneo de `keycloak/rendered`, con y sin el skip (fila 1d).

## Hallazgos
### F-01 · AMARILLO · `identity-edge/Makefile` (`render-keycloak`, rama kind) · la tubería no lleva `pipefail`
El código de salida de la tubería `helm template … | split_realm_configmap.py` es el del script, no el de `helm`. Si `helm` falla, el error solo se ve de forma indirecta: el script recibe una entrada vacía, cuenta 0 ConfigMaps y sale con 1. Hoy eso basta para que falle, pero el mensaje que se ve es engañoso.

### F-02 · AMARILLO · `identity-edge/tools/split_realm_configmap.py:19-24` · división frágil por texto
La división se hace por `"\n---\n"` y busca el documento por subcadena (`kind: ConfigMap` y `name: keycloak-config-cli-realm`). Si el ConfigMap llegara a ser el primer documento del render, saldría con `---` duplicado. Con la salida actual de `keycloakx` no ocurre: la fila 3b sale idéntica. Además, `test_trivy_skips_only_the_new_file…` en `test_config_cli.py` comprueba pertenencia y no la lista exacta, pero esa exactitud ya la cubre `test_platform.py`.

## Tareas candidatas
- Ninguna.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/Makefile render-keycloak|la tubería kind no lleva pipefail; un fallo de helm solo se ve como «hay 0» ConfigMaps
AMARILLO|identity-edge/tools/split_realm_configmap.py:19-24|división frágil por texto (subcadena y `---`)
INFORME: revisiones/U02-T19/ronda-ci.md
```
