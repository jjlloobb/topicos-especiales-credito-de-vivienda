# Ronda 2 — U02-T17

VEREDICTO: VERDE

Revisé la rama `tarea/U02-T17` en el sha `5575027`. Los seis criterios de aceptación pasan en mi propia ejecución. F-01 y F-02 quedaron resueltos tal como pidió el arbitraje. Las 6 candidatas están en `CANDIDATAS.md`. No hay regresiones, no hay desborde de alcance y no queda ningún ROJO ni NARANJA en pie. Al terminar, el worktree sigue limpio (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Las Applications coinciden con `components.yaml` | `uv run python vectra-risk-gitops/generate.py --check` | pasa, rc=0 |
| 2 | Las 7 Applications de U2 están en los 3 entornos | Script PyYAML con `uv run python -I scratchpad/ca2.py`. Revisa la wave, el namespace, la presencia del entorno en `source.path`, que la ruta exista y que no haya `automated` | pasa: 21/21 OK, `bad=0`. Waves 2,3,3,3,3,4,4 en cada entorno |
| 3 | El orden de waves respeta P-U1-12 | `uv run python platform/tests/test_waves.py` | pasa, rc=0 (kind 48, prod 45, staging 47). Rojo reproducido en una copia, ver F-01 |
| 4 | Ninguna Application nueva sincroniza sola | `platform/.tools/bin/kyverno test platform/policies/kyverno` | pasa: 81 passed, 0 failed. `u2-keycloak-auto` sigue con `result: fail` como caso negativo |
| 5 | U1 y U2 siguen en verde | `make -C platform check` y luego `make -C identity-edge check` | pasan, rc=0 los dos. Platform: 745 passed en 2 min 13 s, 4 min 05 s en total, `kyverno apply` 45/0 y 309/0. identity-edge: 2643 passed en 13 min 12 s. Los tiempos son reales, así que no hay saltos silenciosos |
| 6 | V1-a | `test ! -e vectra-risk-gitops/values && grep -c "decisión V1-a" …plan.md` | pasa, rc=0, conteo 1 |

## Comprobación de lo que pedía el arbitraje

**F-01 (resuelto).** `FIXED_WAVES` en `platform/tests/test_waves.py:20-27` queda así:
- conserva `valkey: 2` y `keycloak: 3`;
- renombra las entradas a `gateway: 3` y `ratelimit: 3`;
- suma `identity-jobs: 3`, `identity-rules: 4` e `identity-monitors: 4`.

Reproduje los rojos en una copia sacada con `git archive HEAD` en `scratchpad/r2`, nunca en el worktree. En cada caso cambié `components.yaml`, corrí `generate.py` y después `test_waves.py`:
- **keycloak e identity-jobs en wave 4:** rc=1, con «keycloak: wave 4, se esperaba 3» e «identity-jobs: wave 4, se esperaba 3» en kind, prod y staging. Coincide con la bitácora.
- **valkey en 1, ratelimit en 4, identity-rules en 5:** rc=1, y cada una se nombra con su wave esperada.
- **keycloak en 2 (rojo original del CA-3):** rc=1, con «se esperaba 3» y «keycloak (wave 2) necesita postgres antes».
- **valkey en 3 (rojo original del CA-3):** rc=1, con «se esperaba 2» y «gateway (wave 3) necesita valkey antes».

La bitácora (sección «Ronda 2») corrige de forma explícita la afirmación falsa de la ronda 1 y también la que decía que `CANDIDATAS.md` no existía.

**F-02 (resuelto).** En `platform/tests/test_kind_profile.py:10-12`, `BUDGET_GIB = 5.5` lleva el comentario literal del arbitraje: «Provisional (decisión del usuario, 2026-11-08, U02-T17): U1 + U2 piden 5,47 GiB. Se revisa con la medición del Paso 16 de U2 (DD-3 y T6 de `aidlc-docs/construction/plans/demo-kind-alcance.md`).» Ocupa dos líneas de comentario y el texto coincide. El archivo citado existe y contiene DD-3 (línea 266) y T6 (línea 45). Se quitó el comentario anterior («U1 solo pedia 5.0…»).

**Las 6 candidatas (resuelto).** Están en `vectra-risk/CANDIDATAS.md:149-154`, con el formato de las entradas que ya había:
1. presupuesto de kind, con DD-3/T6 y el margen de 0,027 GiB;
2. `banco-ca`, enlazada con la entrada de U02-T07 (línea 63), con el literal duplicado y el aviso de que vale en cualquier entorno;
3. `charts.sh` no baja `keycloakx`;
4. la ruta fija a los CRDs de Gateway API (F-04);
5. el fixture `u2-keycloak` copiado a mano (F-05);
6. `EXPECTED_WAVES` y `FIXED_WAVES` se solapan.

**Alcance.** El diff de la ronda 2 (`803fabe..5575027`) solo toca `CANDIDATAS.md`, `bitacoras/U02-T17.md`, `test_kind_profile.py` y `test_waves.py`. No hay desborde.

## Hallazgos

### F-01 · AMARILLO · bitacoras/U02-T17.md (Ronda 2, «Verde») · Remite a una evidencia que no está
La bitácora dice «CA-2 a CA-6 y `make check`: ver abajo», pero debajo solo viene «Respuesta a los hallazgos». No hay comando ni salida de CA-2, CA-4, CA-5 ni CA-6 de la ronda 2, así que esa parte está sin verificar. No bloquea porque yo corrí los seis criterios y pasan (ver la tabla). Conviene añadir la evidencia o quitar la referencia.

## Tareas candidatas (defectos reales fuera de alcance)
No hay nuevas. Las 6 del arbitraje ya están en `CANDIDATAS.md`.

```
VEREDICTO: VERDE
AMARILLO|bitacoras/U02-T17.md (Ronda 2, «Verde»)|«ver abajo» remite a la evidencia de CA-2 a CA-6 y make check, que no está en la bitácora
INFORME: revisiones/U02-T17/ronda-2.md
```
