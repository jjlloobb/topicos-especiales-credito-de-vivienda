# Revisión de código del PR 74 (2026-11-07, `/code-review 74`, a pedido del usuario)

La revisión no corrió nada: ni promtool ni pytest.

| Id | Archivo | Hallazgo |
|---|---|---|
| C-01 | `identity-edge/observability/rules/identity-edge-rules.yaml:68` | La rama de serie nueva de B12 (`X > 0 unless X offset 5m`), con `for` 0m, no se protege contra los huecos de scrape. Si el contador vale más que 0 y hubo un hueco de 5 min o más, `LdapUnavailable` dispara SEV2 durante 5 min sin ningún fallo nuevo. B11 ya protegía `BreakGlassLogin` con `last_over_time(X[1h] offset 5m)` y `up offset 5m` |
| C-02 | idem `:53` | Lo mismo pasa en `RoleConflict` |
| C-03 | idem `:83` y `:90` | `or absent(push_time_seconds{job=...})`, con `for` 0m, dispara `RealmDriftStale` y `SigningKeyAgeStale` (SEV3) cuando falla un solo scrape del Pushgateway o este se reinicia, y las alertas oscilan |
| C-04 | idem `:15` | El `absent` de Valkey con `statefulset=~"valkey-.+"` dispara solo cuando faltan los dos. Ya está en `CANDIDATAS.md` |
| C-05 | idem `:15` | Si cae kube-state-metrics, los `absent()` disparan `RateLimitBackendDown` (SEV2) aunque el rate limit y Valkey estén sanos |
| C-06 | `identity-edge/tests/unit/test_alert_rules.py:326` | `rule_problems()` llama siempre a `gateway_facts()`, que necesita `egctl`, también en los casos que no son de B14 |
| C-07 | idem `:251` | Vuelve a traducir con `egctl` en lugar de leer `.tools/xds/<env>.yaml` |
| C-08 | idem `:240` | Reimplementa la búsqueda de listener que ya existe en `test_gateway_xds.py` |
| C-09 | idem `:288` | Las comprobaciones que no dependen del entorno se repiten por entorno |
