# U01-T06 — Reintentos ante tiempos de espera en folder_permissions

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** que `Grafana.request` reintente hasta 3 veces, con espera, cuando una petición agota el tiempo, y falle con un error claro si sigue fallando.

**Fuera:**
- Reintentar errores HTTP 4xx.
- Cambiar los límites de Grafana o la frecuencia del CronJob.
- Publicar imágenes o digests nuevos.

## Archivos de contexto

- `platform/observability/grafana/folder_permissions.py`
- `platform/observability/grafana/tests/test_folder_permissions.py`

## Criterios de aceptación

- [ ] **CA-1** — Contra un servidor HTTP local que no responde a tiempo las dos primeras veces, la petición termina bien; lectura de vuelta: el servidor registró 3 peticiones.
  ```bash
  uv run pytest platform/observability/grafana/tests -q -k retries_on_timeout
  ```
  Esperado: `1 passed`, con la prueba tardando segundos, no minutos.
- [ ] **CA-2** — Un 403 no se reintenta (1 petición), y tres tiempos de espera terminan en error.
  ```bash
  uv run pytest platform/observability/grafana/tests -q
  ```
  Esperado: todas pasan, incluidas las de estos dos casos.

## Plan de pruebas

**Rojo primero:** registra `retries_on_timeout` fallando con `TimeoutError` antes del cambio.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
- La causa de los tiempos de espera en kind sigue sin confirmar: no afirmes que esto la resuelve.
