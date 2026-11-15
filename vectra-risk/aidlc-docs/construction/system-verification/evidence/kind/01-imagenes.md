# 01 — Imágenes y digests

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F1 (Imágenes y digests).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 60 a 90 min; la guía pide anotarla).

Entradas de esta fase: K-06, K-07, K-08, K-09.

### K-06 — Imagenes de U3 a U11 publicadas en kind-registry y digests reales en l…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:41`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:72`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:39`, `aidlc-docs/construction/console/evidence/cierre-demo.md:70`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:50`, `CANDIDATAS.md:701`, `CANDIDATAS.md:288`, `tareas/U12-T05-imagen-y-documentacion.md:360`, `tareas/U12-T04-demos-cli-y-manifiesto.md:121`.

**Resultado esperado.** Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (hoy son de ejemplo: ImagePullBackOff)

**Comando.** Previsto: `grep -rn sha256:0000 vectra-risk-gitops/values/kind`; `arranque.sh vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (hoy son de ejemplo: ImagePullBackOff) | _pendiente_ | _pendiente_ |

### K-07 — Governance, scoring, explainability y casos construidas del mismo comm…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:42`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:72`, `CANDIDATAS.md:484`.

**Resultado esperado.** Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR

**Comando.** Previsto: `git log --oneline origin/main`; a mano: el commit de cada imagen en la plantilla y un solo PR de digests.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR | _pendiente_ | _pendiente_ |

### K-08 — Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) pu…

- Demo: Base. Fuentes: `identity-edge/docs/paso-16-kind.md:15`, `identity-edge/docs/paso-16-kind.md:33-57`.

**Resultado esperado.** Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado

**Comando.** Previsto: `arranque.sh vectra-identity vectra-edge`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado | _pendiente_ | _pendiente_ |

### K-09 — Imagen de U12 publicada y corrida por digest; su memoria en el host fr…

- Demo: Base. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:363`, `tareas/U12-T05-imagen-y-documentacion.md:375`, `tareas/U12-T05-imagen-y-documentacion.md:188`.

**Resultado esperado.** Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g

**Comando.** Previsto: `docker stats --no-stream`; `memoria.sh durante`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
