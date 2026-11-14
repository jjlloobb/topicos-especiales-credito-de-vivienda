# D1: un modelo alterado no llega a servir y, con F22 apagado, el caso escala (journey-7-3, RT-3)

Historia: US-111 (con RT-3). Los comandos son los de la herramienta `vectra-verification`, una sección por vez (ver `aidlc-docs/construction/system-verification/code/cli.md`); los PR son los de `demos/prs/`.

## Prerrequisitos

- `vectra-verification prepare` ya corrió (hay `manifest.json` en el directorio de la verificación) y su PR de `runId` es el de D3.
- Los paquetes RT-3 (`RT3-a`, `RT3-c`, `RT3-d`) generados por `make -C reference-model release` y subidos al model-store.
- El presentador entra a la consola con `analista-2` (rol `analista`), un usuario que la herramienta **no** usa en ese momento (la herramienta usa `analista-1`, `ingeniero-1` y `cro-1`). Su contraseña y su semilla TOTP tienen que estar en la bóveda de kind y llegar al teléfono del presentador: lo comprueba U12-T06.
- Prometheus y los pods de `vectra-serving` visibles para el operador (K16).

## Tiempo real

**12,4 a 19,3 min** desde el primer caso de sonda hasta `no_disponible` (el reintento de U8 es 30 s × 2^(n−1), ±20 %, 6 intentos); la herramienta espera hasta 25 min. `FailClosedPersistente` llega a `firing` unos minutos después del **primer** caso en `no_disponible` (el gauge se publica cada 30 s, Prometheus lo raspa y la alerta tiene `for: 1m`): la herramienta la sondea hasta 5 min después de ver la escalada, en vez de leerla una vez. Aparte: dos PR con su sync (apagar y revertir F22) y el cierre de `rt3 --closing` (≤ 15 min).

## Pasos

| N | Quién | Qué hace | Qué se ve y dónde | Verify |
|---|---|---|---|---|
| 1 | operador | Abre el PR `demos/prs/f22-apagado/apagar.patch` (`env_disabled` de kind con F22), lo fusiona y sincroniza la Application `network` en Argo CD, con prune. Desaparecen 5 recursos de red hacia el explainer. | Nada en la consola todavía; los pods de `vectra-serving` siguen vivos. | `journey-7-3.sh 1` |
| 2 | operador | Opcional: genera el paquete RT3-b desde uno no registrado (`proxy/run-5`) con `vectra_reference.adversarial.rt3_package` y lo sube al model-store. Sin él, RT3-b sale `no ejecutado` y no baja RT-3. | — | — (opcional: no observable con K16) |
| 3 | operador | Corre `vectra-verification rt3 --packages-dir reference-model/.out/adversarial/rt3` (con `--rt3b-dir` si hizo el paso 2). Registra RT3-a, c y d (422 de U4), envía 5 casos de sonda y espera la escalada. | La herramienta imprime `RT-3` y `journey-7-3`. | `journey-7-3.sh 5` |
| 4 | presentador | Abre la `ruta /casos` con `analista-2` y muestra los casos de sonda: primero «En sincronización» y, pasados entre 12,4 y 19,3 min, «No disponible». | `ruta /casos`: columna de estado de la bandeja. | `journey-7-3.sh 2` |
| 5 | presentador | «Escala como incidente técnico» se enseña con la alerta `FailClosedPersistente`: la muestra en la página de alertas de Prometheus. | Alerta `FailClosedPersistente` en `firing`. | `journey-7-3.sh 3` |
| 6 | operador | Abre el PR `demos/prs/f22-apagado/revertir.patch`, lo fusiona y sincroniza la Application `network` en Argo CD, con prune. Después corre `vectra-verification rt3 --closing`. | Vuelven los 5 recursos de red hacia el explainer y un caso de sonda **nuevo** recorre el flujo y llega a `listo` (el cierre queda en el manifiesto como `closing_rt3`, aparte del resultado de `rt3`). `FailClosedPersistente` **sigue en `firing`**: los casos de la primera sonda quedan en `no_disponible` y nadie los reintenta. | `journey-7-3.sh 4` |

El presentador **no** abre la vista de fallos persistentes: está diferida (la consola muestra «No disponible»); el incidente técnico se enseña con la alerta.

## Qué deja sucio y cómo se limpia

- F22 apagado hasta el paso 6 (el PR `revertir.patch`). Revertirlo no apaga la alerta: los casos de la sonda están en `no_disponible` (el gauge `vectra_cases_failclosed_persistent` cuenta esos casos) y solo salen de ahí con el **reintento del CRO**, que hoy no existe de punta a punta (la vista de fallos persistentes está diferida: el BFF sirve la ruta de reintento, pero la consola no tiene la vista que la ofrezca: `entry: false` en `routes.ts`). El guion no lo inventa: los casos y `FailClosedPersistente` **quedan activos**. No afectan a D2, D3 ni D4 (ninguna lee ese gauge ni esa alerta).
- No se ensaya dos veces seguidas el paso 3 sin esperar a que la alerta se apague: el gauge `vectra_cases_failclosed_persistent` no distingue un ensayo anterior.
- RT3-a y RT3-d desplegados (`demos/prs/rt3-staging/`) no caben a la vez; si se hizo, se revierte el PR.

## Qué saldrá `no ejecutado`

`RT3-a-desplegado` y `RT3-d-desplegado` (K16 no llega a `vectra-staging`: decisión del usuario), y `RT3-b` si no se hizo el paso 2. Ninguno baja RT-3 si no da `falla`. Si no se espera la escalada, `journey-7-3` sale `no ejecutado`.
