# U01-T04 — Prueba de regresión de seed-vault grafana-token

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** una prueba sin clúster de `seed-vault.sh grafana-token`, con `kubectl` y `curl` falsos, para los dos casos que corrigió el PR 19.

**Fuera:**
- Cambiar `seed-vault.sh`, salvo que la prueba destape un defecto real: en ese caso, empuja de vuelta.
- Otros modos del script.

## Archivos de contexto

- `platform/kind/seed-vault.sh`
- `platform/kind/tests/test_vault_paths.py` (`test_script_refuses_a_context_that_is_not_kind` es el patrón)

## Criterios de aceptación

- [ ] **CA-1** — Si `grafana-folder-permissions-token` no existe, el script termina en 0, escribe el token y no ejecuta `annotate`. Lectura de vuelta: el registro del `kubectl` falso.
  ```bash
  uv run pytest platform/kind/tests -q -k grafana_token_without_external_secret
  ```
  Esperado: `1 passed`.
- [ ] **CA-2** — Al salir no queda `unbound variable` en stderr y se envía señal al `port-forward` falso.
  ```bash
  uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward
  ```
  Esperado: `1 passed`.

## Plan de pruebas

**Rojo primero:** corre las pruebas contra el script anterior al PR 19 (`git show 1f2aaf6~1:vectra-risk/platform/kind/seed-vault.sh`, en una copia temporal) y registra el fallo.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
