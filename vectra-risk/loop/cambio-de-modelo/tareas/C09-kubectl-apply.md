# C09 — Aplicar la política de F130 en kind

**Unidad:** U1 `platform-foundation`

## Alcance

**Dentro:** aplicar en el clúster `kind-vectra` la NetworkPolicy generada de `vectra-observability` y comprobar que quedó.

**Fuera:** cambiar `flows.yaml`.

## Archivos de contexto

- `platform/network/generated/kind/vectra-observability.yaml`

## Criterios de aceptación

- [ ] **CA-1** — La política está en el clúster.
  ```bash
  kubectl --context kind-vectra apply -f platform/network/generated/kind/vectra-observability.yaml
  kubectl --context kind-vectra get networkpolicy -n vectra-observability
  ```
  Esperado: las políticas aparecen listadas.
