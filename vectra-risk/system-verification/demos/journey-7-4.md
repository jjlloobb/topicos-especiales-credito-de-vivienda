# D2: un modelo con sesgo se congela solo; el paquete se revisa y se reactiva (journey-7-4, RT-2)

Historias: US-303 y US-304 (con RT-2 y RT2-LATENCY).

## Prerrequisitos

- `prepare` corrió; el modelo de referencia está `activo`; `reference-model/.out/proxy/run-1` existe (`make -C reference-model release`).
- El presentador entra con `cumplimiento-2` (rol `cumplimiento`) si usa el modo `presenter`; con el modo `tool` la herramienta usa `cumplimiento-1`. La contraseña y la semilla de `cumplimiento-2` tienen que estar en la bóveda de kind y llegar al teléfono del presentador (U12-T06).
- Riesgo aceptado (U03-T07, aparcada): el servicio de decisiones puede dar 504 al cron de U9 bajo carga; D2 puede repetir una corrida.
- La vista de sesgo está diferida: no se abre.

## Tiempo real

**Más de 75 min** con una versión del proxy (DD-1): lote de 1 500 solicitudes a 10/s (≈ 2,5 min), `freeze` (hasta 30 min), 3 corridas de bias (≈ 45 min, el cron es cada 15 min), reactivación, **1 corrida más** (≤ 15 min; `no_recongela` espera siempre 2 corridas del cron tras reactivar, ≈ 30 min más) y el barrido de U8 (5 min). Aparte: 4 PR de `promotion-tool` (`create-promotion-pr`, `post-activation-pr`, `rollback-pr` y, opcional, el `post-activation-pr` de `<M2>`), más el de `proxy-staging`.

## Dos modos de reactivación (`--reactivation {tool,presenter}`)

- **`tool` (por omisión):** la herramienta hace el step-up de `cumplimiento-1` y envía la reactivación. Sirve para ensayar sin presentador.
- **`presenter`:** la herramienta **no** inicia sesión con ningún usuario de cumplimiento ni envía la reactivación; espera (plazo `--reactivation-timeout`) a que el presentador la haga en la consola con `cumplimiento-2`, en `ruta /congelamientos/:freezeId` (`ResolveFrozenDialog`, con step-up que impone el BFF, no la herramienta). Después verifica lo mismo. Vencido el plazo, la sección queda `no ejecutado` en la fase `reactivacion` y se retoma volviendo a correr `rt2`.

## Pasos

`<M1>` es el modelo de referencia (activo) y `<M2>` la versión del proxy (`reference-model/.out/proxy/run-1`). La secuencia de `promotion-tool` es la de `governance/docs/paso-20-kind.md` (secciones 5.4 y 6) y no se cambia: `post-activation-pr` solo vale **después** del `mark-active` de la versión nueva, y `rollback-pr` solo vale sobre una entrada `inactive`.

| N | Quién | Qué hace | Qué se ve y dónde | Verify |
|---|---|---|---|---|
| 1 | operador | Arma el PR `proxy-staging` con `demos/prs/entrada.py` sobre los values **tal como estén** (ver `demos/prs/proxy-staging/README.md`; con la referencia ya promovida una plantilla fija no aplicaría), lo fusiona y sincroniza la Application `model-serving` en Argo CD. | — | — (no observable con K16: `vectra-staging`) |
| 2 | operador | Corre `vectra-verification rt2-setup`: `ingeniero-1` registra y valida la versión, `cro-1` la aprueba. | La herramienta imprime `rt2-setup`. | `journey-7-4.sh 5` |
| 3 | operador | Promueve `<M2>` con `promotion-tool` (ver `demos/prs/promocion/README.md`), en este orden: `promotion-tool create-promotion-pr <M2>`, fusión, sync de la Application `model-serving` en Argo CD con prune; `promotion-tool mark-active <M2>` (governance deja a `<M1>` `inactivo`); `promotion-tool post-activation-pr <M1>`, fusión y sync (`<M1>` baja a 1 réplica). | — | `journey-7-4.sh 1 isvc-<8 hex>` |
| 4 | operador | Corre `vectra-verification rt2 --reactivation presenter` (o `tool`). Envía el lote estratificado y espera el `freeze`. Al terminar las fases, `rt2` **espera el cierre del paso 7** (plazo `--operator-timeout`, 3 600 s) e imprime qué falta. | — | `journey-7-4.sh 2` |
| 5 | presentador | Con `cumplimiento-2`, abre la `ruta /congelamientos` y entra a `ruta /congelamientos/:freezeId`: muestra el paquete (antes, después, últimos 7 días, atributo, volumen afectado) y el texto «Modelo congelado». | `ruta /congelamientos/:freezeId`: el paquete de congelamiento. | — (no observable con K16: lo lee la sección `rt2`) |
| 6 | presentador | En modo `presenter`, resuelve con «reactivar» en `ResolveFrozenDialog` (pide MFA). | «Congelado» pasa a modelo activo. | — (no observable con K16: lo verifica `rt2`) |
| 7 | operador | Mientras `rt2` verifica `frozen_resolution`, que no se recongele (2 corridas de bias más) y el barrido de casos, y **cuando imprime que espera el cierre**: `promotion-tool rollback-pr <M1>`, fusión, sync de la Application `model-serving` en Argo CD, espera a que los pods de `<M1>` estén `Ready` y, **después**, `promotion-tool mark-active <M1>` (governance deja a `<M2>` `inactivo`). `rt2` lo ve y termina. | — | `journey-7-4.sh 3` |
| 8 | operador | Comprueba que el modelo de referencia sirve otra vez y está `activo`: su `InferenceService` está `Ready` y `rt2` registró el cierre (`closing_rt2`) en el manifiesto. | — | `journey-7-4.sh 4 isvc-<8 hex>` |
| 9 | operador | Opcional: `promotion-tool post-activation-pr <M2>`, fusión y sync, para dejar el entorno sin una versión `inactivo` a 2 réplicas. | — | — (opcional: no observable con K16) |

## Qué deja sucio y cómo se limpia

El modelo del proxy queda registrado y aprobado (U4 no borra versiones) y su entrada `staging` queda en los values de kind (`proxy-staging`): el cierre es el `rollback-pr` y el `mark-active` del paso 7, y el paso 9 baja `<M2>` a 1 réplica. Si `rt2` se corta antes del cierre, el proxy sesgado sigue siendo el modelo activo hasta que se haga el paso 7 a mano. Los casos `no_disponible` de D1 y la alerta siguen activos.

## Qué saldrá `no ejecutado`

Las celdas inalcanzables (menos de 30 filas en `test`) se informan en la evidencia de RT-2. `RT2-LATENCY` dice «1 medición» y cita DD-1. En modo `presenter`, sin la acción del presentador a tiempo: `rt2` queda `no ejecutado` con `rt2_reactivacion_pendiente_del_presentador`.
