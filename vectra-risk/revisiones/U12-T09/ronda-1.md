# Ronda 1 — U12-T09

VEREDICTO: NO-VERDE

No hay ningún ROJO. Los seis criterios pasan en mi propia corrida y no hay desborde de alcance. El veredicto es NO-VERDE por dos NARANJA. Según la regla RL del orquestador, solo un ROJO bloquea.

## Criterios de aceptación, verificados por mí (sha b8aa2c9, worktree u12-t09)
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `pytest system-verification/tests -k "transient or transitorio"` | pasa, 13 passed. `--collect-only` da 13, todas de U12-T09 (11 en `test_transient_reads.py` y 2 en `test_cli.py`) |
| 2 | `... -k "resend or reenvi"` | pasa, 17 passed. El filtro también recoge 3 pruebas viejas (`test_simulator` 429/503 y dos de rt2 sobre «resend the batch»); las demás son de `test_resend.py` |
| 3 | `... -k sincronizacion` | pasa, 6 passed. Recoge además una prueba vieja de `test_kind_guide` («la sincronizacion de MinIO») |
| 4 | `pytest test_kind_scripts.py test_prepared_prs.py && make -C system-verification shellcheck` | pasa, 93 passed en 121 s. Shellcheck rc 0 (con `uvx`, no se denegó). Los casos nuevos están: 2 de `estado_final` y 4 de `entry_retirar` |
| 5 | `pytest test_kind_guide.py test_kind_inventory.py test_demos_closed_world.py && grep RT3-c ... && ! grep ...` | pasa, 184 passed. RT3-c aparece en las líneas 50, 55 y 58 y las frases falsas no aparecen. **Rojo contra main comprobado por mí:** cambiando con un plugin `GUIDE_TEXT` y `README` por los de `6cf06e1`, 9 de las 10 pruebas `t09_*` que no son de mutación fallan (puntos 7, 8, 9, 14 y los demás) |
| 6 | `make -C system-verification check-fast && test_links.py && make -C model-serving lint` | pasa, rc 0. Lo corrí **entero, una sola vez, con Docker**: `test_kind_smoke`, `test_oidc_headless` y `test_rt5_promql` pasaron, no se saltaron. Etapa 1: 1306 passed en 1135 s, cobertura 95,84 %. Etapa 2: 1033 passed, 100 %. ruff, mypy, 11 contratos, 647 Markdown sin enlaces rotos, 22 identificadores. Esto completa lo que el codificador no pudo correr |
| — | `platform/tests/test_traceability.py --all` | rc 0: no hay fallos nuevos |

**Mutaciones propias del bloque A.** Las hice con un plugin de pytest en el scratchpad que parchea módulos al arrancar; no copié ni toqué fuentes.
- `READ_MAX_PAUSE = READ_BASE` (sin espera creciente): 6 failed.
- `driver.retry_read` sin reintento: 2 failed.
- `sim_normal.retry_read` sin reintento: 11 failed.
- `RESEND_STATUSES` de main: 7 failed.
- `WAITING_STATES` de main: 5 failed.
- Tope ×50: 1 failed.
- `INFRA_ERRORS` de main: 2 failed.
- Lista de lectura con 4xx y 500 añadidos: 1 failed (solo la prueba del 500).
- **Sobreviven:** la lista de lectura con 400/401/403/409/422 añadidos (92 passed), y `set_decisions(sent, accepted)` anticipado suprimido (92 passed).

## Comprobaciones pedidas
- **1a, idempotencia.** `case-management/src/vectra_case/intake.py:97-99` toma `pg_advisory_xact_lock` sobre `intake:{scope}|{key}`. Las líneas 100-109 leen `intake_keys`: con el mismo hash del cuerpo devuelve el mismo `CaseRef`, con otro da 409. Si un reenvío llega mientras el primer intento sigue en curso, queda bloqueado en el candado hasta que la transacción termina. Si el primero hizo commit, el reenvío lee el mismo caso; si hizo rollback, crea el único caso. La ruta `intake` va directa a `case-service` (`routes.yaml:148-165`, `timeout: 5s`). Reenviar es seguro.
- **1b, reintentos de lectura.** La lista es explícita: un 4xx distinto de 429 no se reintenta y el 404 lo trata quien llama. Cada vuelta espera al menos 2 s, así que no hay bucle sin fin. El tope se mide con el reloj inyectado. `ReadUnavailable` usa `from None` y por eso no arrastra traza, pero conserva el estado y los intentos en el mensaje. Un 500 sigue llegando como `ApiError`. Una cosa a saber: en `driver.run` un `ReadUnavailable` del detalle de un caso no lo captura `except ApiError` y corta toda la pasada, que termina como `decisions_lectura_agotada`. Es coherente con la tarea.
- **1c, contratos cambiados.** Nadie consume `decisions.*` del manifiesto fuera de `cli.py` y las pruebas: ni `report.py`, ni los `verify`, ni los oráculos. `sim_normal_bff_no_responde` sigue vivo para un 500 o un estado 0 que no se reintente.
- **1d, `oidc.py`.** El diff es solo formato: la misma expresión partida en varias líneas.
- **3, gateway.** La orden por etiqueta y `--add-host "vectra.localtest.me:${GATEWAY_ADDRESS:?…}"` están bien formadas (las pruebas las ejecutan con un `docker` falso). Si no hay Service, `kubectl` falla, la variable queda vacía y `:?` se niega. `gateway-address.sh` de U01-T16 (lo leí en su worktree) se llama sin argumentos, así que es compatible.
- **4, `PENDING`.** Es estrecha. Con «otro-address.sh» la guía da 2 hallazgos; `pending()` solo rige mientras el archivo no exista.
- **5, lista cerrada.** Las pruebas no amplían la lista de escrituras. `git clone` y `pull` escriben solo en local, igual que el `> proxy.patch` y el `mkdir` que ya había. Lo acepto con la salvedad de F-05.
- **2, `journey-7-3`.** No puede romper D1: F7 va después de `decisions`, y `rt3` usa `analista-1`, `ingeniero-1` y `cro-1`. Además `GET /v1/cases` admite `cro` (`contracts/.../routes/__init__.py:87`) y la ruta `/casos` también (`routes.ts:41`). `cro-2` e `ingeniero-2` existen en `realm.kind.yaml` con `cro` e `ingeniero_riesgo`.

## Hallazgos
### F-01 · NARANJA · docs/paso-18-kind.md, F10 paso 4 y F0 paso 11 · El procedimiento nuevo no lleva las plantillas al PR de verificación
La guía exige que el PR traiga las plantillas `00` a `12` llenas, `cierre-demo.md` y el plan (líneas 24-28 y 758). Sin embargo, la orden de F10 solo hace `cp -r "$EVID"` al clon, y ningún paso dice en qué árbol se llenan las plantillas:
- Si se llenan en el clon, este queda sucio y `promotion-tool` se niega en F8 (`working_tree_dirty`).
- Si se llenan en la copia de trabajo, nunca llegan al PR, y el `git pull --ff-only` que la guía pide antes de F5 se niega en cuanto main toca una de ellas.

En la misma clase: la línea 751 sigue diciendo «Lee `system-verification/evidence/<fecha>-<commit>/verification-report.md`», pero ahora está en `$EVID`, fuera del repositorio, hasta F10.

### F-02 · NARANJA · tests del bloque A · Tres comportamientos nuevos sin una prueba que los ate (comprobado con mutaciones)
(a) Que un 4xx no se reintente en las lecturas: añadir 400/401/403/409/422 a `READ_RETRY_STATUSES` deja todo en verde. (b) Que el manifiesto traiga `sent` y `accepted` si la espera se interrumpe: es cierto (mi sonda leyó `{"sent": 20, "accepted": 20}` en `interrupt_section`), pero suprimirlo deja todo en verde, y la guía (línea 551 y fila de síntomas) lo promete. (c) La exclusión `idempotency_key_invalid` de `simulator.py:213` no tiene ninguna prueba (grep vacío en `tests/`).

### F-03 · AMARILLO · paso-18-kind.md F0 paso 9 y D3 · Con `EVID` fijo en `$VERIF_HOME/evid` no hay forma escrita de empezar otra verificación
Las líneas 257 y 508 piden «un directorio nuevo» u «otro `$EVID`». El bloque reutiliza siempre el primero y `prepare` se niega. Además el nombre `<fecha>-<commit>` sale del commit de F0, antes de fusionar los digests de F1.

### F-04 · AMARILLO · bitácora, guía y README, más la candidata para U01-T16 en CANDIDATAS.md · Afirmación inexacta sobre el nombre del Service
`platform/operators/envoy-gateway.yaml:34` usa `type: GatewayNamespace`: Envoy Gateway nombra el Service como el Gateway, `api-gateway`, en `vectra-edge`. Eso coincide con lo que midió el orquestador. Leer por etiqueta sigue siendo correcto, pero la candidata contra `gateway-address.sh` parte de una premisa falsa y conviene retirarla o corregirla.

### F-05 · AMARILLO · paso-18-kind.md F8 «Repetir D2» y journey-7-4.md · «borra la rama vieja, local y remota»
Borrar la rama remota es una escritura en GitHub. Queda fuera de la excepción declarada en la línea 15 («solo escriben en ese clon»).

### F-06 · AMARILLO · aidlc-docs/construction/system-verification/code/scenarios.md:71 · Falta un código nuevo
La lista de códigos de `SIM-NORMAL` no trae `sim_normal_lectura_agotada`.

### F-07 · AMARILLO · journey-7-3.md frente a la guía · Inconsistencia declarada, sin riesgo de que falle la demo (ver comprobación 2)
El codificador ya la anotó como candidata. Hay que unificar el guion y la guía a la vez.

## Tareas candidatas (fuera de alcance)
- Ninguna nueva aparte de las que el codificador ya añadió, con la corrección de F-04 sobre la de U01-T16.

## Estado final
- El worktree quedó con `git status --short` vacío y HEAD en b8aa2c9.
- Borré las copias `rev-u12t09-*` del scratchpad.
- No toqué el clúster.

```
VEREDICTO: NO-VERDE
NARANJA|docs/paso-18-kind.md F10 paso 4|El procedimiento nuevo no lleva las plantillas al PR de verificación (y la línea 751 apunta a una ruta vieja)
NARANJA|tests del bloque A|4xx sin reintento, conteos anticipados del manifiesto e idempotency_key_invalid sin prueba (mutaciones sobreviven)
AMARILLO|paso-18-kind.md F0 paso 9|EVID fijo sin forma escrita de empezar otra verificación
AMARILLO|CANDIDATAS.md (U01-T16)|el Service se llama api-gateway por GatewayNamespace: premisa de la candidata inexacta
AMARILLO|paso-18-kind.md F8|borrar la rama remota queda fuera de la excepción de git declarada
AMARILLO|aidlc-docs/.../code/scenarios.md:71|falta sim_normal_lectura_agotada
AMARILLO|demos/journey-7-3.md|analista-2 frente a cro-2 (sin riesgo para D1)
INFORME: revisiones/U12-T09/ronda-1.md
```
