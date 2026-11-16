# U12-T09 — La herramienta aguanta fallos transitorios y la guía de kind queda al día

**Unidad:** U12 — `system-verification`
**Historias que implementa:** ninguna nueva; cierra los hallazgos de la auditoría entre unidades del 2026-11-16 que hacen inestables las demos D1 a D4 en kind.
**Depende de:** ninguna (U01-T16 corre en paralelo y entrega `platform/kind/gateway-address.sh`; aquí solo se nombra)

---

## Alcance

**Dentro**, en dos bloques. Todo lo de abajo está leído en el código de `main`; nada se ha medido en el clúster.

> ### Bloque A — código de la herramienta
>
> 1. **`decisions` no se cae por un error transitorio del BFF.** Hoy `scenarios/sim_normal.py` (≈ líneas 107 a 112) relanza todo `ApiError` que no sea 404, `cli.py` (≈ líneas 692 a 694) lo llama en la espera sin envolver, y `driver.py` (`_ready`) lista la bandeja fuera de un `try`. Un solo 429, 503, 504 o tiempo agotado deja la sección `interrumpida` con los 2 000 casos enviados y ninguno decidido; al repetir, el simulador manda otros 2 000 con identificadores nuevos. Las lecturas (`read_cases`, `_ready`, la espera) reintentan ante estado 0 (transporte), 429, 502, 503 y 504, con espera creciente y un tope que el reloj inyectado controla; agotado el tope, la sección termina con una causa propia, no con una traza.
> 2. **El simulador reenvía lo que es seguro reenviar.** `simulator.py`, línea 40: `RESEND_STATUSES = (429, 503)`. Un 502, un 504 del gateway (la ruta `intake` corta a 5 s, `identity-edge/gateway/routes.yaml`) o un tiempo agotado de transporte cuentan hoy como rechazo, y uno solo deja `accepted != sent` y `SIM-NORMAL` en `falla`. El alta lleva llave de idempotencia: comprueba en `case-management` que reenviar con la misma llave no crea otro caso (di archivo y línea) y añade esos tres a los reenviables.
> 3. **La espera cuenta los casos en `en_sincronizacion`.** `sim_normal.py` (`sweep`) solo sondea `en_evaluacion` (matiz de `CANDIDATAS.md`, línea 676): los casos que el worker dejó para reintentar no se esperan ni se deciden, y `decided < accepted` sin que nada lo diga. O se esperan, o el resultado los cuenta y los nombra.
> 4. **`estado-final.sh` comprueba que el modelo activo es el de referencia.** Hoy solo exige que haya uno activo: con el proxy `activo` sale 0. Añade un parámetro con el `model_version_id` de referencia.
> 5. **`demos/prs/entrada.py` sabe retirar** la entrada de staging que añadió (`promotion-tool` reescribe el bloque y `git apply -R` del parche ya no aplica).
>
> ### Bloque B — la guía (`docs/paso-18-kind.md`), el `README.md`, los guiones de `demos/` y el inventario
>
> 6. **RT3-c se sube al model-store.** `model-serving/docs/paso-11-kind.md`, líneas 50 a 57, sube `RT3-a RT3-b RT3-d`; `rt3` exige `RT3-a`, `RT3-c` y `RT3-d` (`scenarios/rt3.py`, líneas 46 y 52) y sin el manifiesto U4 responde 422 con otro motivo: RT-3 da `falla`. Añade `RT3-c` al bucle y al `mc ls` de ese documento (única línea de U6 que tocas) y a K-24 del inventario.
> 7. **`promotion-tool` exige el árbol limpio y la guía lo ensucia.** `governance/promotion_tool/vectra_promotion/gitops.py`, ≈ línea 105 (`working_tree_dirty`). La guía crea `$EVID` dentro del repositorio (líneas 209 y 210) y escribe `proxy.patch` en el directorio de trabajo (≈ línea 596); además cada orden lee los values y el `main` locales y ninguna guía pide `git pull` tras fusionar un PR. La evidencia tiene que acabar en el PR de verificación, así que **no** se resuelve con `.gitignore`. Decide y escribe el procedimiento (por ejemplo, un clon limpio dedicado a `promotion-tool`, con su `git pull` antes de cada orden, y los parches fuera del árbol) y átalo con una prueba de la guía.
> 8. **`EVID` se fija una vez.** Hoy se calcula con `date -u` y `git rev-parse` (línea 209): una terminal nueva tras las 00:00 UTC o tras un `git pull` apunta a un directorio vacío y `u11`, `report` y los `verify` no encuentran el manifiesto. Se guarda una vez (por ejemplo en `$VERIF_HOME`) y las demás terminales lo leen.
> 9. **La máquina llega al gateway.** `guard.py`, línea 37, fija `vectra.localtest.me`, que por DNS es 127.0.0.1:443, donde no escucha nada (`platform/runbooks/install.md`, ≈ línea 185); el `README.md`, línea 160, dice «probado … llega al gateway». La función `vv` (líneas 212 a 223) lleva `--add-host vectra.localtest.me:<dirección>` leída del Service del gateway; F0 y los prerrequisitos de F5 (inicio de la jornada 2) corren `platform/kind/gateway-address.sh` (lo entrega U01-T16: nómbralo, y si tu prueba de «mundo cerrado» exige que exista, dilo en el informe en vez de crearlo) y dicen qué línea de `/etc/hosts` pone el operador para el navegador y `promotion-tool`. Corrige el `README.md`.
> 10. **Ventanas de tiempo que la guía no dice:**
>     - D4 solo pasa durante el día D + 1 UTC: `scenarios/u11.py`, líneas 22 a 24, lee `period="day"`, que es «ayer» (`product-metrics/src/vectra_product/compute.py`, ≈ líneas 267 y 301). F9 y K-04 llevan el tope superior (antes de las 00:00 UTC de D + 2, las 19:00 de Colombia de D + 1). Comprueba en el código si la espera hasta las 02:40 UTC hace falta o las series existen antes, y escribe lo que el código dice.
>     - La misma versión del proxy no se recongela el mismo día UTC (`bias-monitoring/src/vectra_bias/window.py`, líneas 55 a 59): el ensayo «en el otro modo» (≈ líneas 586 y 652) va otro día UTC o con otro paquete; dilo.
>     - Tras F6, comprobar que el modelo de referencia sigue `activo` (`humo modelos`): el cron de bias evalúa también esa versión con los 2 000 casos de `decisions`.
> 11. **Repetir una demo tras un fallo a medias**, con órdenes concretas para cada caso:
>     - D3: un segundo `prepare` se niega mientras los values conserven el `runId` (`manifest.py`, ≈ líneas 300 y 301), y el Job `rt5-demo-<runId>` lleva `backoffLimit: 0` y no se puede borrar con la lista cerrada. Escribe el camino (quitar el `runId` por PR, sync con prune, volver a ponerlo) en la guía y en `demos/prs/rt5-run-id/README.md`.
>     - D2: `create-promotion-pr` da `already_declared` en la segunda pasada y las ramas `promotion/*` tienen nombre fijo; con el proxy `congelado` no hay rollback sin reactivar antes (`model_fsm.py`, ≈ líneas 192 y 193). Escribe la segunda pasada y el orden en la guía y en `demos/journey-7-4.md` («Qué deja sucio»).
> 12. **Usuarios compartidos:** `analista-2` es del conductor (`driver.py`, línea 37) y del presentador, e `ingeniero-1` lo usan `promotion-tool`, `governance/docs/kind/token.sh` y `rt2`; un choque en la ventana TOTP de 30 s cuenta para el bloqueo. La guía reparte los usuarios (propón el reparto con los que existen en `identity-edge/keycloak/realm/realm.kind.yaml`) y pide una sola pestaña por usuario.
> 13. **Suspender la máquina:** una línea en «Después de reiniciar la máquina» que remita a «Tras suspender la máquina» de `install.md` (certificado de 24 h del plano de control de Linkerd).
> 14. **Lo que hoy es falso en la guía:** línea 5 («Nada de esto se ha ejecutado aún en kind»), R-2 y las líneas 53 y 286 («todos los charts llevan el digest de ejemplo»: `vectra-risk-gitops/values/kind` ya no trae ninguno), línea 57 y línea 164 (inotify), línea 112 (`components.yaml`), y la tabla de síntomas, que no trae lo medido el 2026-11-15 y el 2026-11-16 (`install.md`, «Lo medido el 2026-11-15» y «Tras suspender»: llave de cifrado en el JWKS, primera petición tras inactividad, credenciales de Calico, doble sync de `keycloak`, certificado de la malla). Corrige las citas por número de línea que ya no apuntan a su texto (`install.md` «150 a 163», `paso-16-kind.md:95`, K-01 y K-05 del inventario). Deja la guía sin números de línea de `install.md` donde puedas citar la sección por nombre: U01-T16 lo está editando.

**Fuera:**

- El tope por solicitud de U3 (U03-T07, aparcada), la caché de JWKS de U0, el tiempo agotado del rate limit del gateway y los presupuestos de U7 y U8: son de otras unidades y van como candidatas si ves algo nuevo.
- `promotion-tool` y los servicios: no se toca código fuera de `system-verification/`, salvo la línea de `model-serving/docs/paso-11-kind.md` del punto 6.
- `platform/` (lo edita U01-T16 y U01-T15 en paralelo).
- Endurecer `test_kind_guide.py` para que compruebe el contenido de cada cita (`CANDIDATAS.md`, líneas 821 y 822): sigue como candidata. Sí entra una prueba por cada afirmación que corrijas en los puntos 7, 8, 9 y 14.
- Cualquier orden contra el clúster. Reconstruir la imagen de U12 y fijar su digest lo hace el orquestador.

---

## Archivos de contexto

- `system-verification/src/vectra_verification/`: `simulator.py`, `driver.py`, `cli.py`, `guard.py`, `manifest.py`, `clients/`, `scenarios/sim_normal.py`, `scenarios/u11.py`, `scenarios/rt2.py`, `scenarios/rt3.py`, `scenarios/waits.py`
- `system-verification/docs/paso-18-kind.md`, `system-verification/docs/kind/` (`estado-final.sh`, `inventario.yaml`, `humo.py`, `arranque.sh`), `system-verification/README.md`, `system-verification/demos/` (`journey-7-4.md`, `prs/entrada.py`, `prs/rt5-run-id/README.md`, `prs/proxy-staging/README.md`)
- `system-verification/tests/unit/` (`test_kind_guide.py`, `test_kind_inventory.py`, `test_kind_scripts.py`, `test_prepared_prs.py`, `test_demos_closed_world.py`), `system-verification/tests/doubles/`, `system-verification/Makefile`
- Solo lectura, para comprobar lo que afirmas: `case-management/src/vectra_case/` (idempotencia del alta, estados), `console/bff/src/console_bff/config.py`, `identity-edge/gateway/routes.yaml`, `governance/promotion_tool/vectra_promotion/` (`gitops.py`, `values.py`, `commands.py`), `governance/src/vectra_governance/model_fsm.py`, `bias-monitoring/src/vectra_bias/window.py`, `product-metrics/src/vectra_product/compute.py`, `model-serving/docs/paso-11-kind.md`, `platform/runbooks/install.md`
- `CANDIDATAS.md` (líneas 676, 772, 797, 800, 821 a 823), `DECISIONES-LOOP.md` §10 y §11

---

## Criterios de aceptación

- [ ] **CA-1** — `decisions` sobrevive a errores transitorios del BFF en la espera y en el conductor, y termina con una causa propia si se agota el tope.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests -q -p no:cacheprovider -k "transient or transitorio"
  ```
  Esperado: pasa, con pruebas nuevas (doble del BFF que responde 429, 503, 504 y un fallo de transporte antes de responder bien; y uno que falla siempre). Comprueba con `--collect-only` que el filtro selecciona tus pruebas. Contra `main`, la primera falla con el `ApiError` sin envolver.

- [ ] **CA-2** — El simulador reenvía 502, 504 y el fallo de transporte con la misma llave de idempotencia, y `accepted == sent` cuando el reenvío entra.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests -q -p no:cacheprovider -k "resend or reenvi"
  ```
  Esperado: pasa; una prueba comprueba que la llave del reenvío es la misma. Mutación: con `RESEND_STATUSES` de `main`, falla.

- [ ] **CA-3** — Los casos en `en_sincronizacion` se esperan o se cuentan y se nombran.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests -q -p no:cacheprovider -k "sincronizacion"
  ```
  Esperado: pasa, con una prueba nueva que falla contra `main`.

- [ ] **CA-4** — `estado-final.sh` falla con el proxy activo, y `entrada.py` retira la entrada que añadió.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_scripts.py system-verification/tests/unit/test_prepared_prs.py -q -p no:cacheprovider && make -C system-verification shellcheck
  ```
  Esperado: pasa, con casos nuevos en los dos archivos (di cuáles).

- [ ] **CA-5** — La guía y los documentos dicen lo que dice el código: RT3-c, árbol limpio para `promotion-tool`, `EVID` fijo, `--add-host` en `vv`, ventanas de D4 y de D2, repetición de D3 y D2, y sin las afirmaciones falsas del punto 14.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_guide.py system-verification/tests/unit/test_kind_inventory.py system-verification/tests/unit/test_demos_closed_world.py -q -p no:cacheprovider && grep -n 'RT3-c' model-serving/docs/paso-11-kind.md && ! grep -n -E 'Nada de esto se ha ejecutado|todos los charts llevan el digest de ejemplo|llega al gateway de kind' system-verification/docs/paso-18-kind.md system-verification/README.md
  ```
  Esperado: rc 0. Las pruebas de la guía tienen casos nuevos que fallan contra `main` para los puntos 7, 8, 9 y 14.

- [ ] **CA-6** — `system-verification` sigue en verde, y las pruebas de otras unidades que leen lo que tocaste también.
  ```bash
  cd vectra-risk && make -C system-verification check-fast && uv run python platform/tests/test_links.py && make -C model-serving lint
  ```
  Esperado: rc 0. Una sola vez, al final. (`check-fast` no construye la imagen: no la construyas.)

---

## Plan de pruebas

Las de CA-1 a CA-5. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`** ni contra `vectra.localtest.me`, ni lecturas. No construyas ni descargues imágenes.
- Cada afirmación de esta tarea sobre el código de otra unidad está leída, no medida: compruébala antes de escribirla en la guía. Si el código dice otra cosa, vale el código, y lo dices en el informe.
- La guía tiene pruebas de «mundo cerrado»: no nombra nada que no exista en el repositorio y solo escribe órdenes de la lista cerrada del operador. No amplíes la lista; lo que no quepa remite al documento dueño.
- Si `platform/tests/test_links.py` o `test_unit_plans.py` necesitan `platform/.charts`, cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No va en el commit.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u12t09-`, y borra tus copias al terminar.
- En paralelo corren U01-T15 (`platform/policies/`) y U01-T16 (`platform/kind/`, `platform/runbooks/install.md`): no toques esos archivos.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes (uno por bloque terminado: A y B). No hagas push, no fusiones, no muevas el estado de la tarea.
