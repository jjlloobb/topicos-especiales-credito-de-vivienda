# D2: un modelo con sesgo se congela solo; el paquete se revisa y se reactiva (journey-7-4, RT-2)

Historias: US-303 y US-304 (con RT-2 y RT2-LATENCY).

## Prerrequisitos

- `prepare` corrió; el modelo de referencia está `activo`; `reference-model/.out/proxy/run-1` existe (`make -C reference-model release`).
- El presentador entra con `cumplimiento-2` (rol `cumplimiento`) si usa el modo `presenter`; con el modo `tool` la herramienta usa `cumplimiento-1`. La contraseña y la semilla de `cumplimiento-2` tienen que estar en la bóveda de kind y llegar al teléfono del presentador (U12-T06).
- Riesgo aceptado (U03-T07, aparcada): el servicio de decisiones puede dar 504 al cron de U9 bajo carga; D2 puede repetir una corrida.
- La vista de sesgo está diferida: no se abre.

## Tiempo real

**Más de 75 min** con una versión del proxy (DD-1): lote de 1 500 solicitudes a 10/s (≈ 2,5 min), `freeze` (hasta 30 min), 3 corridas de bias (≈ 45 min, el cron es cada 15 min), reactivación, **1 corrida más** (≤ 15 min; `no_recongela` espera siempre 2 corridas del cron tras reactivar, ≈ 30 min más) y el barrido de U8 (5 min). Aparte: 4 PR de `promotion-tool` y 2 de `proxy-staging`.

## Dos modos de reactivación (`--reactivation {tool,presenter}`)

- **`tool` (por omisión):** la herramienta hace el step-up de `cumplimiento-1` y envía la reactivación. Sirve para ensayar sin presentador.
- **`presenter`:** la herramienta **no** inicia sesión con ningún usuario de cumplimiento ni envía la reactivación; espera (plazo `--reactivation-timeout`) a que el presentador la haga en la consola con `cumplimiento-2`, en `ruta /congelamientos/:freezeId` (`ResolveFrozenDialog`, con step-up que impone el BFF, no la herramienta). Después verifica lo mismo. Vencido el plazo, la sección queda `no ejecutado` en la fase `reactivacion` y se retoma volviendo a correr `rt2`.

## Pasos

| N | Quién | Qué hace | Qué se ve y dónde | Verify |
|---|---|---|---|---|
| 1 | operador | Abre el PR `proxy-staging` (plantilla `demos/prs/proxy-staging/proxy.patch.tpl` con el `model_version_id` de `reference-model/.out/proxy/run-1`), lo fusiona y sincroniza la Application `model-serving` en Argo CD. | — | — (no observable con K16: `vectra-staging`) |
| 2 | operador | Corre `vectra-verification rt2-setup`: `ingeniero-1` registra y valida la versión, `cro-1` la aprueba. | La herramienta imprime `rt2-setup`. | — (no observable con K16: la versión vive en governance) |
| 3 | operador | Crea los PR de `promotion-tool` (ver `demos/prs/promocion/README.md`): `create-promotion-pr`, fusión, sync de la Application `model-serving` en Argo CD con prune, y `mark-active`. | — | `journey-7-4.sh 1 isvc-<8 hex>` |
| 4 | operador | Corre `vectra-verification rt2 --reactivation presenter` (o `tool`). Envía el lote estratificado y espera el `freeze`. | — | `journey-7-4.sh 2` |
| 5 | presentador | Con `cumplimiento-2`, abre la `ruta /congelamientos` y entra a `ruta /congelamientos/:freezeId`: muestra el paquete (antes, después, últimos 7 días, atributo, volumen afectado) y el texto «Modelo congelado». | `ruta /congelamientos/:freezeId`: el paquete de congelamiento. | — (no observable con K16: lo lee la sección `rt2`) |
| 6 | presentador | En modo `presenter`, resuelve con «reactivar» en `ResolveFrozenDialog` (pide MFA). | «Congelado» pasa a modelo activo. | — (no observable con K16: lo verifica `rt2`) |
| 7 | operador | La herramienta verifica `frozen_resolution`, que no se recongele (2 corridas de bias más) y el barrido de casos. Cierre: `rollback-pr`, fusión y sync al modelo de referencia. | — | `journey-7-4.sh 3` |
| 8 | operador | Comprueba que el modelo de referencia sirve otra vez. | — | `journey-7-4.sh 4 isvc-<8 hex>` |

## Qué deja sucio y cómo se limpia

El modelo del proxy queda registrado y aprobado (U4 no borra versiones): el cierre es el rollback del paso 7. Los casos `no_disponible` de D1 y la alerta siguen activos.

## Qué saldrá `no ejecutado`

Las celdas inalcanzables (menos de 30 filas en `test`) se informan en la evidencia de RT-2. `RT2-LATENCY` dice «1 medición» y cita DD-1. En modo `presenter`, sin la acción del presentador a tiempo: `rt2` queda `no ejecutado` con `rt2_reactivacion_pendiente_del_presentador`.
