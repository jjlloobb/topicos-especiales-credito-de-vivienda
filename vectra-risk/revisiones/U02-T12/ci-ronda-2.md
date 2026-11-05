# U02-T12 — CI tras la ronda 2 (orquestador, 2026-11-05)

La ronda 2 salió VERDE en local y la persona aprobó el PR 67. GitHub no deja fusionarlo (`mergeStateStatus: BLOCKED`), porque dos jobs del workflow `platform` fallan sobre `897166e`:

- `tests / tests`: run 41977331082, job 127079141117;
- `evidence / evidence`: run 41977331082, job 127079140991.

Los demás jobs pasan: `contracts`, `forbidden`, `policies`, `supply-chain` y `rollback-note`.

## Hallazgo

**CI-01 — ROJO.** `platform/network/tests/test_edge_selectors.py` no pasa en CI. Resultado del job `tests`: `33 failed, 712 passed`. Todas las fallas son de ese archivo y dan el mismo error:

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/topicos-especiales-credito-de-vivienda/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools/bin/helm'
```

El job `evidence` falla en las mismas pruebas.

### Causa

Para modelar el Deployment de `envoy-ratelimit`, `real_pods()` usa `identity-edge/tests/unit/test_ratelimit_deployment.py`. Ese módulo fija `HELM = ROOT / "platform" / ".tools" / "bin" / "helm"` en la línea 31.

En CI, `.github/workflows/tests.yml` instala helm en el `PATH` con `./.github/actions/setup-helm`, a la versión de `platform/tools.env`. No corre `install-tools.sh`, así que `platform/.tools/` no existe. Las pruebas de U1, como `platform/tests/test_platform.py:25` y `platform/tests/integration.py:36`, llaman a `helm` del `PATH`.

En local pasó porque el codificador y el revisor tenían `platform/.tools/`. Es la misma clase de defecto que la lección de U01-T03: los criterios no reproducían el entorno donde corre la prueba.

### Lo que se espera de la ronda 3

- `platform/network/tests/test_edge_selectors.py` pasa en el entorno de CI de `platform`: con helm en el `PATH`, a la versión de `tools.env`, y sin `platform/.tools/`.
- Las pruebas de `identity-edge` siguen pasando como hoy, con `make -C identity-edge check`.
- El cambio no pierde el pin de versión de helm. Los snapshots de `rendered/` dependen de él.
- La evidencia incluye la suite de `platform` corrida sin `platform/.tools/bin` en el `PATH` ni en disco. Por ejemplo, con `.tools` renombrado temporalmente y helm de `tools.env` en el `PATH`, que es lo que hace CI. También incluye el resultado de CI del nuevo commit.
