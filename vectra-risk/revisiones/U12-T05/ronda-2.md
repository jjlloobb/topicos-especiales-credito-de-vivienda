VEREDICTO: NO-VERDE

# Ronda 2 — U12-T05 (resumen)

**Nota del orquestador (2026-11-15):** este archivo es un **resumen** del informe del revisor, escrito por el orquestador. El informe completo se entregó en la sesión del 2026-11-14 y no se guardó a tiempo; sus registros estaban en una copia del scratchpad que ya no existe. El PR #172 se fusionó en `main` antes de que la revisión terminara.

No quedó ningún ROJO. Los ocho puntos de «Lo que se espera de la ronda 2» de `arbitraje-ronda-1.md` quedaron cerrados y comprobados ejecutando, dos de ellos con mutaciones del revisor. `make -C system-verification check` terminó en rc 0 (25:28; 1049 y 800 pruebas; `test-image` 32).

Comprobado ejecutando, dentro del contenedor (con `--network none` y un kubeconfig falso, para no tocar `kind-vectra`):
- **F-01 (era el ROJO), cerrado:** `decisions` y `rt2-setup` sin perfil seccomp terminan en `no ejecutado (2)` con `oidc:browser_launch_error`; con la bóveda inalcanzable, `oidc:vault_unreachable`; `rt2`, `rt5` y `u11` con el servidor de kubectl inalcanzable o con otro contexto, código 2. Ninguna traza.
- **F-02, cerrado:** el perfil es el de `containers-common` menos las 20 llamadas que nombra el README, con el errno por omisión en EPERM; `keyctl`, `mount` y `pivot_root` dan EPERM con el perfil nuevo.
- **F-03, cerrado:** `build-requirements.txt` con versión y hash; el README presenta `docker save`/`load` como el camino fiable.
- **F-04, cerrado:** mueren las 7 mutaciones de `readonly`.
- **F-05, cerrado:** contexto `kind-vectra` y `KUBE_CONTEXT`, prerrequisitos, Docker Engine y no Docker Desktop, Ctrl-C frente a `docker stop`.
- **`verify/rt-5.sh` paso 1, N-1 y la prueba F07:** cerrados.

## Hallazgos
- **F-01 · NARANJA · `bitacoras/U12-T05.md`:** la ronda 2 no está en la bitácora (sin rojo primero, sin mediciones, sin explicar los cambios de `src/` y `demos/`).
- **F-02 · AMARILLO · `tests/image/test_image.py`, `SYSCALL_PROBE`:** `mount` y `pivot_root` dan EPERM sin `CAP_SYS_ADMIN` aunque el perfil los permita; solo `keyctl` distingue.
- **F-03 · AMARILLO · `tests/unit/test_oracles_rt2_rt3_rt5.py:954`:** la prueba de N-1 no retoma desde el archivo.
- **F-04 · AMARILLO · `CANDIDATAS.md:774`:** la línea sigue diciendo que el perfil es «copia sin cambios»; falta la candidata del espejo con fecha de Debian.

```
VEREDICTO: NO-VERDE
NARANJA|bitacoras/U12-T05.md; CA-13|la ronda 2 no está registrada en la bitácora
INFORME: revisiones/U12-T05/ronda-2.md
```
