# U01-T01 — Grafana sin descargas de plugins

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** que Grafana no intente instalar plugins desde Internet al arrancar, en todos los entornos.

**Fuera:**
- Los reinicios de Grafana y sus límites de CPU o memoria.
- `grafana-folder-check` y los flujos de métricas (otras tareas).

## Archivos de contexto

- `platform/observability/values/kube-prometheus-stack.yaml`
- `platform/tests/test_upstream_charts.py`
- `platform/runbooks/install.md`

## Criterios de aceptación

- [ ] **CA-1** — El Deployment renderizado define `GF_PLUGINS_PREINSTALL_DISABLED=true` en el contenedor `grafana`.
  ```bash
  uv run pytest platform/tests/test_upstream_charts.py -q -k grafana_does_not_preinstall_plugins
  ```
  Esperado: `1 passed`. La prueba lee el valor del render del chart, no de los values.
- [ ] **CA-2** — Nada más cambió en el comportamiento de los charts.
  ```bash
  uv run pytest platform/tests/test_upstream_charts.py -q && uv run ruff check platform
  ```
  Esperado: todo pasa.

## Plan de pruebas

Agrega `test_grafana_does_not_preinstall_plugins`. **Rojo primero:** muéstrala fallando en la bitácora antes del cambio.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
- Motivo: en kind, `plugin.backgroundinstaller` registró fallos de instalación, y dentro del banco nada debe salir a Internet.
