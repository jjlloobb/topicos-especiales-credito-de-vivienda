# U01-T02 — Reglas ilm que no se acumulan

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** que repetir los `customCommands` de `ilm` de MinIO deje una sola regla por bucket, también la primera vez, con el bucket sin reglas.

**Fuera:**
- Reemplazar MinIO (issue 28).
- Limpiar las reglas duplicadas de un clúster existente.
- Probar que el lifecycle borre datos vencidos.

## Archivos de contexto

- `platform/data/minio/values.yaml` y `platform/data/minio/values-kind.yaml`
- `platform/.charts/minio/minio/templates/_helper_custom_command.txt`
- `aidlc-docs/construction/platform-foundation/evidence/simulacro-ilm.txt`
- `platform/tests/test_upstream_charts.py`

## Criterios de aceptación

- [ ] **CA-1** — Un script reproduce los comandos renderizados dos veces contra un MinIO real en Docker, con un bucket nuevo. La primera pasada no falla y al final hay una sola regla: lectura de vuelta con `mc ilm rule ls --json`.
  ```bash
  bash platform/data/minio/tests/ilm_idempotente.sh
  ```
  Esperado: termina en 0 e imprime `reglas tras 2 pasadas: 1`. Usa las imágenes `localhost:5001/minio:dev` y `localhost:5001/mc:dev` y elimina sus contenedores.
- [ ] **CA-2** — Las pruebas de los charts y el render siguen bien.
  ```bash
  uv run pytest platform/tests/test_upstream_charts.py -q
  ```
  Esperado: todo pasa.

## Plan de pruebas

**Rojo primero:** corre el script con los comandos actuales y registra `reglas tras 2 pasadas: 2`.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
- **Trampa conocida:** `mc ilm rule rm --all --force` termina en 1 si el bucket no tiene reglas, y el Job del chart corre con `set -e`. El chart ejecuta cada comando sin shell.
- Si no hay forma de resolverlo con `customCommands`, empuja de vuelta con la evidencia: esta tarea puede necesitar cambiar de enfoque.
