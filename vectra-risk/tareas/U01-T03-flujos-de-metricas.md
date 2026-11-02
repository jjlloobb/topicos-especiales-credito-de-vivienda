# U01-T03 — Flujos de métricas de la observabilidad

**Unidad:** U1 `platform-foundation`
**Depende de:** ninguna

## Alcance

**Dentro:** declarar el flujo F130, de `prometheus` a `alertmanager` (8080), `grafana` (3000) y `prometheus-operator` (8080), para que esos targets dejen de dar 504.

**Fuera:**
- Otros flujos.
- Cambiar la autorización por identidad de Linkerd de los demás.

## Archivos de contexto

- `platform/network/flows.yaml` y `platform/network/generate.py`
- `platform/network/tests/test_flows.py`
- `aidlc-docs/inception/application-design/component-dependency.md` (F129 es la última fila de ese tipo)

## Criterios de aceptación

- [ ] **CA-1** — Existen las NetworkPolicy de ingress y egress de F130 en los tres entornos, con esos puertos y sin 4143.
  ```bash
  uv run pytest platform/network/tests -q -k f130
  ```
  Esperado: al menos 1 prueba por entorno; todas pasan.
- [ ] **CA-2** — Lo generado coincide y el inventario está al día.
  ```bash
  uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q
  ```
  Esperado: termina en 0, con todas las pruebas pasando.

## Plan de pruebas

**Rojo primero:** escribe la prueba de F130 y registra su fallo antes de tocar `flows.yaml`.

## Notas

- Trabaja solo en tu worktree. **No ejecutes nada contra un clúster** (`kubectl`, `helm install`, `argocd`): el destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red a servicios nuevos ni herramientas nuevas.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
- Modifica en su sitio `platform/network/generated/` solo con `make -C platform generate`.
- Queda sin comprobar contra el clúster: no lo afirmes en tu informe.
