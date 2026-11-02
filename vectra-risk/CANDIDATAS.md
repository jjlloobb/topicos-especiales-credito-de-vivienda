# Trabajo candidato: fuera del alcance del loop

Lo que aparece y no se hace ahora. Viene de `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`.

- Failover de zona completo, en una máquina de al menos 32 GiB.
- Suite X01–X10 que corra contra el clúster.
- Causa del cambio de IP de origen de `kubelet` tras reiniciar un nodo.
- Causa de los reinicios de Grafana.
- `PostgresVolumeUsageHigh` en kind, sin métricas de volumen.
- Implementar el S3 del banco y ESO por namespace (issue 28).
- Grafana sigue intentando salir a Internet al arrancar: `grafana.update.checker` y `plugin.angulardetectorsprovider.dynamic` (revisor, U01-T01).
- Prueba de render con el overlay de kind, en los charts con `kind_values` (revisor, U01-T01, F-01).
- `push_metric` sin reintentos: un tiempo agotado contra Pushgateway tumba el `check` (revisor, U01-T06).
- Publicar imagen y digest nuevos de `folder_permissions`: los reintentos no llegan al clúster hasta entonces (revisor, U01-T06).
- Prueba genérica que ate cada flujo a sus destinos declarados, y `kind` en las referencias de autorización (revisor, U01-T03, F-04 y F-07).
- `prometheus` hacia sí mismo en 8080 y 9090 sin declarar, sin comprobar (revisor, U01-T03).
- Tareas de flujos con `test_integration.py` entre sus criterios: `U01-T03` los cumplía y rompía esa prueba (revisor, U01-T03).
- Decidir si un solo fallo de archivado debe disparar un SEV1, fijar la ventana de 5 minutos con una prueba y actualizar el diseño de U1 (revisor, U01-T05).
- `seed-vault.sh grafana-token`: el bucle `until curl … /api/health` no tiene límite; si el port-forward muere, el script queda colgado (revisor, U01-T04, ronda 1).
- El fixture de `test_vault_paths.py` no limpia el `sleep` del kubectl falso si este muere por SIGKILL (revisor, U01-T04, ronda 2, F-01).
- Ninguna prueba fija el contenido de las reglas `ilm` (`--expire-days`, `--noncurrent-expire-days`) (revisor, U01-T02).
- La prueba de orden `ilm` acepta un `add … || true` y recorre solo loki y tempo; el script crea todos los buckets con lock y aborta sin diagnóstico con 0 reglas (revisor, U01-T02, ronda 2, F-01 a F-04).
- Instalar shellcheck en `platform/.tools/bin` y correrlo sobre `platform/**/tests/*.sh`; aplicar `ruff format` a `test_upstream_charts.py`, que ya fallaba en `main` (codificador y revisor, U01-T02).
- La nota de `tareas/U01-T02-ilm-idempotente.md` dice que el chart ejecuta los comandos sin shell; es falso, corren dentro de `/bin/sh` (revisor, U01-T02, F-04). Error de especificación del orquestador.
