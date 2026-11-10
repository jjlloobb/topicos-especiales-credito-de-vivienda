# Arbitraje de la ronda 1 — U04-T06

Orquestador, 2026-11-10. Informe: `revisiones/U04-T06/ronda-1.md`.

- **F-01 (el pod no arranca) no es de esta tarea.** Es del Paso 10 (U04-T04), que entra completo en la demo. Se abre **U04-T08** (punto de entrada del servicio: `config_from_env`, `build_app`, `main` y el cliente S3 de F47), que se despacha en cuanto se fusione U04-T06 y va **antes** de U04-T07. U04-T06 se fusiona sin F-01; el CA-9 de esta tarea solo comprueba la imagen, no el arranque.
- **F-02 entra en la ronda 2:** el runbook debe poder ejecutarse tal cual en U04-T07.
- **F-04 entra en la ronda 2** (texto).
- **F-03:** candidata.

## Qué entra en la ronda 2 (la última por RL-2)

1. **Integrar `origin/main`** (trae la enmienda §8 y U09-T02/U07-T01 si se fusionaron). Conflictos esperados solo en `CANDIDATAS.md`: conservar ambos lados.
2. **F-02, runbook de política en kind:** completo y ejecutable. Una imagen con `curl` disponible en `kind-registry` (o la que ya use otro runbook del repo), el `kubectl run` entero del paso 3 sin «…», y la verificación hecha **desde dentro del clúster** con la misma identidad, por la ruta que la malla admite. Declara como requisito previo la `ServiceAccount` `console-bff` en `vectra-app` (la crea U10): el runbook dice cómo crearla de forma temporal en kind solo para este arranque, o lo deja como bloqueo explícito con el comando que la crea; no la agregues a ningún chart. Prueba: un `shellcheck` o una prueba que lea los bloques de comandos del runbook y compruebe que no hay «…» ni hosts internos usados fuera del clúster.
3. **F-04:** NFR-U4-02, 06, 12 y 13 en `cierre-demo.md` como «pendiente de U04-T07 (guía de kind de U4)», no como diferidos por §8. Si la herramienta de trazabilidad solo acepta la sección «Diferido por la demo», déjalos allí con esa cita corregida.
4. **F-03:** a `CANDIDATAS.md`.

Nada más.
