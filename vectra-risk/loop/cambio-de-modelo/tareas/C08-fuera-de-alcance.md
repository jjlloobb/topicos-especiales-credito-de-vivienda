# C08 — Prueba de regresión de seed-vault grafana-token (alcance cerrado)

**Unidad:** U1 `platform-foundation`

## Alcance

**Dentro:** una prueba sin clúster de `seed-vault.sh grafana-token`, con `kubectl` y `curl` falsos, que compruebe que al salir se envía señal al `port-forward`.

**Fuera:**
- Cambiar `platform/kind/seed-vault.sh`, por ningún motivo. Si la prueba destapa un defecto, se registra como candidata.

## Archivos de contexto

- `platform/kind/seed-vault.sh`
- `platform/kind/tests/test_vault_paths.py`

## Criterios de aceptación

- [ ] **CA-1** — La prueba existe y se ejecuta.
  ```bash
  uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward
  ```
  Esperado: la prueba corre. Si falla por un defecto del script, se deja en rojo y se registra la candidata.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster.**
- Comandos desde `vectra-risk/`.
