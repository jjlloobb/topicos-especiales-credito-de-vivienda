# Ronda 2 — U04-T05b

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `824887d` (merge con padres `6a9b444` y `origin/main` = `9c01e46`). El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Qué metió el merge además de main (`comm -12` de los diffs contra cada padre) | Solo seis archivos difieren de los dos padres: `login.py`, `test_promotion_tool.py`, `governance/pyproject.toml`, `uv.lock`, `CANDIDATAS.md` y la bitácora |
| 1b | `CANDIDATAS.md` | 0 líneas borradas contra cada padre; se conservan las entradas de U01-T08 y de U04-T05b |
| 2 | F-01 | `login.py:57` es `f"http://127.0.0.1:{server.server_port}"`, usado en la autorización (61) y en el token (87); coincide con `domain-entities.md:67` y `realm.kind.yaml:957-958` |
| 2b | Rojo con el `login.py` de `8b760fd` | Reproducido: `Invalid parameter: redirect_uri=http://127.0.0.1:41365/callback`, 1 failed, 16 passed |
| 3 | F-03 | `pyyaml==6.0.3`, la versión del lock; `uv lock --check` rc 0 |
| 4 | Pruebas y checks | `test_promotion_tool.py` 17 passed; `make -C governance check` rc 0 (335 passed); `make -C platform check` rc 0 (800 passed) |
| 4d | `--all` en la rama y en `origin/main` | rc 1 en los dos; los fallos de la rama son un subconjunto estricto de los de main (quita NFR-U4-20 y 21). Sin fallos nuevos |

## Hallazgos

- **F-01 · AMARILLO** · `governance/tests/unit/test_promotion_tool.py:357-364`: el doble del endpoint de token no compara `redirect_uri` con el de la autorización (Keycloak sí). Hoy el código usa la misma variable; falta el candado contra una regresión. Candidata.

F-01 y F-03 de la ronda 1, cerrados. Sin tareas candidatas nuevas; sigue abierta la confirmación en un Keycloak real de que ignora el puerto en loopback.
