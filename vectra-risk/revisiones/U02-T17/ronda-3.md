# Ronda 3 — U02-T17

VEREDICTO: VERDE

Revisé el sha `37ea5a7` en el mismo worktree. El usuario acotó la ronda a C-01 y C-05 de la revisión del PR 78. Corrí yo mismo CA-1 a CA-6 y los seis pasan. C-01 y C-05 cumplen lo que pide el arbitraje. Los rojos se reproducen en una copia. Las candidatas están en `CANDIDATAS.md` y el AMARILLO de la ronda 2 quedó resuelto. No queda ningún ROJO ni NARANJA, no hay desborde y, al terminar, `git status --short` del worktree sale vacío.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Las Applications coinciden con `components.yaml` | `uv run python vectra-risk-gitops/generate.py --check` | pasa, rc=0 |
| 2 | Las 7 Applications de U2 existen en los 3 entornos | `uv run python -I scratchpad/ca2r3.py`, con PyYAML: revisa la wave, el namespace, que la ruta lleve el entorno y exista, y que no haya `automated` | pasa, `bad=0`, 21/21. Waves por entorno: valkey 2, keycloak 3, gateway 3, ratelimit 3, identity-jobs 4, identity-rules 4, identity-monitors 4 |
| 3 | El orden respeta P-U1-12 | `uv run python platform/tests/test_waves.py` | pasa, rc=0 (kind 48, prod 45, staging 47) |
| 4 | Ninguna sincroniza sola | `platform/.tools/bin/kyverno test platform/policies/kyverno` | pasa: 81 passed, 0 failed. `u2-keycloak-auto` es el negativo esperado |
| 5 | U1 y U2 siguen en verde | `make -C platform check`, luego `make -C identity-edge check` | rc=0 los dos. Platform: 745 passed en 5 min 02 s, kyverno apply 45/0 y 309/0. identity-edge: **2690 passed** en 25 min 32 s. Los tiempos son reales, así que no hubo pruebas saltadas |
| 6 | V1-a | `test ! -e vectra-risk-gitops/values && grep -c "decisión V1-a" …plan.md` | pasa, rc=0, conteo 1 |

## C-01: cada par STRICT nuevo, contrastado con los renders (kind, staging y prod)
- **`secret-store` → `valkey`:** `charts/valkey/rendered/<env>` tiene 1 `ExternalSecret` en cada entorno, con `secretStoreRef: { name: vectra-store, kind: ClusterSecretStore }` (`valkey.yaml:758`). **Correcto.**
- **`secret-store` → `keycloak`:** hay 3 `ExternalSecret` en cada entorno, con targets `identity-ca`, `keycloak-config-cli-client` y `keycloak-reader-client` (`keycloak.yaml:464/485/506`). **Correcto.**
- **`secret-store` → `identity-jobs`, no agregado. Lo confirmo:**
  - `grep -rlE "ExternalSecret|ClusterSecretStore|secretStoreRef" jobs/rendered/<env>` da 0 archivos en los tres entornos.
  - `identity-ca` aparece 6 veces en `identity-jobs.yaml` como Secret montado.
  - El `ExternalSecret` con `target: { name: identity-ca }` vive en el render de keycloak (`keycloak.yaml:453-465`).
  - Los Secrets de cliente que usan los Jobs también salen de keycloak.
  - La dependencia transitiva la cubre `keycloak` → `identity-jobs`, y `keycloak` ya depende de `secret-store`.
- **`mesh-certificates` → `keycloak` y `gateway`:**
  - `platform/mesh/certificates.yaml:21` crea el `ClusterIssuer` `vectra-internal-ca`. Es el único archivo del componente: `include: certificates.yaml`, `components.yaml:28`.
  - En kind usan ese emisor el `Certificate` de keycloak y el de `gateway/generated/kind/certificates.yaml`.
  - En staging y prod el gateway no lo usa (allí va `banco-ca`), pero el par es inocuo porque STRICT no distingue entornos. **Correcto.**
- **`keycloak` → `identity-monitors`:** `observability/monitors/monitors.yaml:15` monta `identity-ca`, que crea el render de keycloak. **Correcto.**
- **Barrido de clase sobre los 7 renders de U2:** no aparece ninguna otra dependencia de instalación sin cubrir.
  - `ratelimit` ya tenía `secret-store`.
  - `identity-rules` e `identity-monitors` ya tenían `prometheus-operator-crds`.
  - El render de jobs no tiene `issuerRef` ni `ExternalSecret`.

## C-05: identity-jobs en la wave 4
Está en wave 4 en los cuatro sitios:
- `components.yaml:45`;
- `apps/{kind,staging,prod}/identity-jobs.yaml:7`, con `sync-wave: '4'`;
- `FIXED_WAVES` en `test_waves.py:23`;
- `EXPECTED_WAVES` en `test_platform.py:284`.

El par `("keycloak", "identity-jobs")` está en STRICT (línea 61) y ya no está en `SAME_WAVE_OK`. La nota del plan, en `identity-edge-code-generation-plan.md:222`, coincide palabra por palabra con el arbitraje.

## Rojos, reproducidos en una copia
La copia es `git archive 37ea5a7` en `scratchpad/r3`, no el worktree. En cada caso corrí `generate.py` y luego `test_waves.py`:
- **Base:** rc=0.
- **identity-jobs en 3** (en `components` y en `FIXED`): rc=1, «identity-jobs (wave 3) necesita keycloak antes (wave 3)».
- **valkey en 1:** rc=1, «valkey (wave 1) necesita secret-store antes».
- **keycloak en 1:** rc=1. Nombra `mesh-certificates`, `secret-store` y `postgres`.
- **mesh-certificates en 3:** rc=1, «gateway…» y «keycloak (wave 3) necesita mesh-certificates antes».
- **identity-monitors en 3:** rc=1, «necesita keycloak antes».
- **Control:** con valkey en 1 y **sin** el par `("secret-store", "valkey")`, rc=0. El par nuevo es justo lo que detecta el fallo.

## Candidatas y bitácora
- `CANDIDATAS.md:171-172` trae C-06 (`value_files()` y el README frente a V1-a) y el comentario inexacto de `SAME_WAVE_OK` en U1.
- La bitácora, en la sección «Ronda 3», trae el comando y la salida de CA-1 a CA-6. El AMARILLO de la ronda 2 quedó resuelto. Sus cifras coinciden con las mías: 2690 passed.

## Alcance
El diff `febe093..37ea5a7` solo toca:
- `test_waves.py`, `test_platform.py`, `components.yaml` y las 3 apps `identity-jobs`;
- la nota del plan, `CANDIDATAS.md` y la bitácora.

No hay desborde.

## Hallazgos

### F-01 · AMARILLO · tareas/U02-T17-applications-gitops.md (CA-2 y «Orden») · Texto de la tarea desfasado tras C-05
El CA-2 de la tarea todavía espera las waves «2, 3, 3, 3, 3, 4, 4». La sección «Orden» describe `keycloak` → `identity-jobs` como «misma wave». El arbitraje de la ronda 3 ya fija 2,3,3,3,4,4,4, así que esto no bloquea. Además, ese archivo es del orquestador, no del codificador. Lo mismo pasa con la línea base del Paso 12 del plan (`plan.md:219`, «Keycloak + `keycloak-config-cli` … (3)»): la corrige la nota de la línea 222, que es el estilo de enmienda del repositorio.

## Tareas candidatas (defectos reales fuera de alcance)
No hay nuevas.

```
VEREDICTO: VERDE
AMARILLO|tareas/U02-T17-applications-gitops.md (CA-2 y «Orden»)|el texto de la tarea aún espera identity-jobs en wave 3 y «misma wave»; el arbitraje ya fija la wave 4
INFORME: revisiones/U02-T17/ronda-3.md
```
