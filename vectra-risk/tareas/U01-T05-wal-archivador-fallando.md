# U01-T05 — WalArchiveStale con el archivador fallando

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** que `WalArchiveStale` también dispare si `cnpg_pg_stat_archiver_failed_count` aumenta, sin volver a disparar en una base inactiva.

**Fuera:**
- Las demás alertas, incluida `PostgresVolumeUsageHigh`.
- Cambiar severidades.

## Archivos de contexto

- `platform/observability/rules/platform-rules.yaml` y `platform-rules.prometheusrule.yaml`
- `platform/observability/rules/tests/platform-rules-test.yaml`
- `platform/runbooks/wal-archive-stale.md`

## Criterios de aceptación

- [ ] **CA-1** — Existen casos de `promtool` para: archivador fallando (dispara), base inactiva sin fallos (no dispara) y segmentos pendientes (dispara).
  ```bash
  cd platform/observability/rules/tests && ../../../.tools/bin/promtool test rules *.yaml
  ```
  Esperado: `SUCCESS`.
- [ ] **CA-2** — Las reglas son válidas y las probadas son las desplegadas.
  ```bash
  platform/.tools/bin/promtool check rules platform/observability/rules/platform-rules.yaml && uv run pytest platform/tests/test_ci.py platform/tests/test_platform.py -q
  ```
  Esperado: todo pasa.

## Plan de pruebas

**Rojo primero:** agrega el caso del archivador fallando y registra el fallo de `promtool` antes de cambiar la regla.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
