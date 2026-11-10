# Ronda 2 — U04-T06

VEREDICTO: NO-VERDE

Revisor, 2026-11-10, punta `85d8c2e`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Lo que pasa

- La ronda 2 solo toca lo arbitrado (5 archivos; nada en `governance/src`; el merge de main es limpio).
- El pod efímero del runbook es YAML válido, pasa 8 de 8 políticas de Kyverno de kind y PSS `restricted`; identidad y etiquetas coinciden con la ruta `console` de `flows.yaml` y con lo generado; con la imagen de governance, el `command` reemplaza el `CMD` y el cliente carga aunque el servicio no tenga punto de entrada.
- F-04: NFR-U4-02, 06, 12 y 13 citan «pendiente de U04-T07», no §8.
- `make -C governance check` rc 0 (480 passed); `make -C platform check` rc 0; `--unit governance --all` rc 0 (34); `--all` sin fallos nuevos frente a `origin/main`.

## Hallazgos

- **F-01 · ROJO** · `governance/runbooks/kind-politica-de-referencia.md:75,119`: los pasos 3 y 4 crean Secrets a mano en `vectra-app` y `disallow-plain-secrets` (Enforce en kind) los rechaza (`kyverno apply`: `pass: 0, fail: 1`). El runbook se detiene en el paso 3.
- **F-02 · ROJO** · runbook `:125-149`: la verificación va después de la limpieza y usa el ConfigMap y el Secret ya borrados.
- **F-03 · NARANJA** · `governance/tests/unit/test_kind_runbook.py:13-30`: trata todo heredoc como «dentro del pod»; no detecta un cliente urllib ejecutado en local, `bash <<EOF wget …`, el nombre corto `governance-service.vectra-app`, cercos `sh` ni marcadores `REEMPLAZA_POR_…`; una de las pruebas lee `DEFAULT` y no `RUNBOOK`.
- **F-04 · NARANJA** · runbook `:49-52,118`: `DIGEST`, `TOKEN_CRO2`, `TOKEN_CRO1` y `POLICY_ID` son marcadores manuales; el token pegado en `export` queda en el historial y `--from-literal` lo expone en los argumentos; `accessTokenLifespan: 300` puede vencer entre aprobar y verificar.
- **F-05 · AMARILLO**: `/tmp/llamar.py` no se limpia; `llamar` solo vive en la shell del paso 4; detalles de la bitácora.
- **F-06 · AMARILLO**: conflicto en `CANDIDATAS.md` con el `origin/main` actual (conservar ambos lados).

Dirección sugerida para F-01: no crear Secrets; pasar el token por stdin a un pod interactivo (`kubectl run -i` y `python` leyendo `sys.stdin`).
