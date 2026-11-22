# 01 — Imágenes y digests

**Estado: completa.** Llenada el 2026-11-20 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F1 (Imágenes y digests).
- Fecha: 2026-11-20 (jornada 1), entre las 12:27 y las 13:00 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 9dc027f.
- Duración real de la fase: unos 10 min (solo la imagen de U12) (estimada: 60 a 90 min; la guía pide anotarla).

Entradas de esta fase: K-06, K-07, K-08, K-09.

### K-06 — Imagenes de U3 a U11 publicadas en kind-registry y digests reales en l…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:41`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:72`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:39`, `aidlc-docs/construction/console/evidence/cierre-demo.md:70`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:50`, `CANDIDATAS.md:701`, `CANDIDATAS.md:288`, `tareas/U12-T05-imagen-y-documentacion.md:360`, `tareas/U12-T04-demos-cli-y-manifiesto.md:121`.

**Resultado esperado.** Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (un digest que no es el publicado da ImagePullBackOff; ya no queda ninguno de ejemplo)

**Comando.** Previsto: `grep -rn sha256:0000 vectra-risk-gitops/values/kind`; `arranque.sh vectra-app`.

```bash
grep -rn sha256:0000 vectra-risk-gitops/values/kind; echo "grep rc=$?"; system-verification/docs/kind/arranque.sh vectra-app | tail -6
```

**Salida.**

```text
grep rc=1
linkerd-cni: 3 pods, 0 hallazgos
ExternalSecret: 26 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (un digest que no es el publicado da ImagePullBackOff; ya no queda ninguno de ejemplo) | ningun sha256:0000; vectra-app con 25 pods y 0 hallazgos | si |

### K-07 — Governance, scoring, explainability y casos construidas del mismo comm…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:42`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:72`, `CANDIDATAS.md:484`.

**Resultado esperado.** Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR

**Comando.** Previsto: `git log --oneline origin/main`; a mano: el commit de cada imagen en la plantilla y un solo PR de digests.

```bash
git log --format='%h %ad %s' --date=short -5 -- vectra-risk-gitops/values/kind; git diff --stat 565ff2c d79a861 -- contracts | tail -1; echo 'diff de contracts entre 565ff2c y d79a861: vacio si no hay linea arriba'
```

**Salida.**

```text
2692964 2026-11-18 feat(model-serving): promover isvc-8a98ab02 (mv-2026-01-01-8a98ab02) en kind
ced9490 2026-11-17 chore(gitops): kind digests of governance and model-validation-job rebuilt from d79a861 (U04-T12)
f483cd5 2026-11-16 chore(vectra-risk): governance image digest for kind, built with the validation Job fix
9661864 2026-11-16 chore(vectra-risk): new image digests for kind after the JWKS fix and the SPA change, built from 565ff2c
49fd192 2026-11-15 chore(vectra-risk): real image digests for kind (F1 of the kind verification), built from ed0dd0f
diff de contracts entre 565ff2c y d79a861: vacio si no hay linea arriba
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR | scoring, explainability y casos salen de 565ff2c (PR de digests 9661864); governance y model-validation-job se reconstruyeron de d79a861 (PR ced9490); entre los dos commits `contracts` no cambia | parcial: no es un solo commit ni un solo PR; el tipo ServingConfig es el mismo en los dos; ver hallazgo H-2 |

### K-08 — Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) pu…

- Demo: Base. Fuentes: `identity-edge/docs/paso-16-kind.md:15`, `identity-edge/docs/paso-16-kind.md:33-57`.

**Resultado esperado.** Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado

**Comando.** Previsto: `arranque.sh vectra-identity vectra-edge`.

```bash
system-verification/docs/kind/arranque.sh vectra-identity vectra-edge | tail -8
```

**Salida.**

```text
vectra-identity: 6 pods, 0 hallazgos
vectra-edge: 8 pods, 0 hallazgos
linkerd-cni: 3 pods, 0 hallazgos
ExternalSecret: 8 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado | U2 ya estaba instalado: vectra-identity y vectra-edge sin hallazgos | si (no hizo falta publicar) |

### K-09 — Imagen de U12 publicada y corrida por digest; su memoria en el host fr…

- Demo: Base. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:363`, `tareas/U12-T05-imagen-y-documentacion.md:375`, `tareas/U12-T05-imagen-y-documentacion.md:188`.

**Resultado esperado.** Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g

**Comando.** Previsto: `docker stats --no-stream`; `memoria.sh durante`.

```bash
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/system-verification:dev; docker stats --no-stream --format '{{.Name}} {{.MemUsage}}'
```

**Salida.**

```text
localhost:5001/vectra/system-verification@sha256:d00c07690f967dcf1a8f782a51a37c29be873cdf1c5108f91000646ab633b772
cloud-provider-kind 17.44MiB / 14.82GiB
kindccm-abc7eeb4f506 8.445MiB / 14.82GiB
kind-registry 19.37MiB / 14.82GiB
vectra-worker2 3.901GiB / 14.82GiB
vectra-control-plane 2.728GiB / 14.82GiB
vectra-worker 3.723GiB / 14.82GiB
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g | imagen reconstruida del main 9dc027f (la publicada era del 2026-11-16 y no traia U12-T09) y corrida por digest sha256:d00c0769...; la memoria del contenedor bajo carga se mide en F6 | parcial: publicada y corrida por digest; la memoria frente a --memory 1g queda para F6 |

## Hallazgos

- **H-2 (U12, la guia).** Las imagenes de scoring, explainability y casos salen del commit 565ff2c y las de governance del d79a861 (U04-T12), en dos PR de digests. Entre los dos commits no cambia `contracts`, asi que el tipo `ServingConfig` es el mismo. No se reconstruyo nada para esta corrida: el diagnostico de F0 muestra las unidades sanas y desde esos commits el codigo de las imagenes solo cambio en `vectra_common/service_token.py` (U02-T28), que solo afecta a un cliente sin scopes (`identity-jobs`, ya reconstruido).
- **H-3 (U12).** La imagen de U12 publicada era del 2026-11-16 00:22 y no traia U12-T09 (`retry.py`, el reenvio del simulador). Se reconstruyo del main 9dc027f y se publico: `sha256:d00c07690f967dcf1a8f782a51a37c29be873cdf1c5108f91000646ab633b772`.
