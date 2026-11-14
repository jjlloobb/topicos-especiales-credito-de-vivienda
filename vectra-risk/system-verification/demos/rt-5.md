# D3: una escritura al núcleo bancario la deniega la malla y la alerta lo muestra (rt-5, RT-5)

Historia: US-603 (con RT-5 y X01).

## Prerrequisitos

- `vectra-verification prepare` corrió y produjo `case-management-runid.patch` (el `runId` de esta verificación).
- Prometheus raspa el proxy de Linkerd de `vectra-mock` (serie `inbound_http_authz_deny_total`, U01-T09) y conserva 3 días.

## Tiempo real

El Job tarda segundos. La alerta `CoreWriteAttempt` no tiene `for:` y su expresión mira 5 min: **se ve en `firing` unos 5 min y se apaga sola**. Pasada esa ventana, el presentador enseña la evidencia de `rt5` (`query_range`), no la alerta.

## Pasos

| N | Quién | Qué hace | Qué se ve y dónde | Verify |
|---|---|---|---|---|
| 1 | operador | Abre el PR `rt5-run-id` (el parche que generó `prepare`; la clave de values `probes.runId`), lo fusiona y sincroniza la Application `case-management` en Argo CD, con prune. Antes pasó `make -C case-management policy-chart`. | Nace el Job `rt5-demo-<runId>` en `vectra-app`. | `rt-5.sh 1` |
| 2 | operador | Espera al Job (segundos). | El Job termina con `succeeded`. | `rt-5.sh 2` |
| 3 | presentador | Muestra el log del Job: el 403 lo dio el proxy (`l5d-proxy-error` con valor), no la aplicación. | Log del pod del Job. | `rt-5.sh 3` |
| 4 | presentador | **En los 5 min siguientes al Job** muestra la alerta `CoreWriteAttempt` en `firing` en la página de alertas de Prometheus. | Alerta `CoreWriteAttempt`. | `rt-5.sh 4` |
| 5 | operador | Comprueba la serie `inbound_http_authz_deny_total` y que el contador `vectra_core_write_attempts_total` del mock sigue en 0. | — | `rt-5.sh 5` |
| 6 | operador | Corre `vectra-verification rt5`: `RT-5` y la evidencia `rt-5` (con `query_range`). | La herramienta imprime `RT-5`. | `rt-5.sh 6` |

## Qué deja sucio y cómo se limpia

El Job `rt5-demo-<runId>` queda en `vectra-app` y el `runId` en los values de kind: el siguiente `prepare` en otro directorio usa otro `runId`; el PR anterior se revierte aparte. El `runId` nunca va a staging ni a producción (`conftest` y `policy-chart` lo rechazan).

## Qué saldrá `no ejecutado`

`X01` (diferida por la demo): US-603 queda `no ejecutado` aunque RT-5 pase. Si la lectura de Prometheus falla, `rt5` sale `no ejecutado` con su código.
