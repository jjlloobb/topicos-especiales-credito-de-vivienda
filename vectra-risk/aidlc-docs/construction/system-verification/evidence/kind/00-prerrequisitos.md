# 00 — Prerrequisitos

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F0 (Prerrequisitos).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 30 min, más la instalación de la plataforma si parte de cero; la guía pide anotarla).

Entradas de esta fase: K-01, K-02, K-03, K-04, K-05.

### K-01 — Memoria del host

- Demo: Base. Fuentes: `platform/runbooks/install.md:20`, `platform/tests/test_kind_profile.py:34`, `DECISIONES-LOOP.md:78-86`, `tareas/U12-T05-imagen-y-documentacion.md:35`, `aidlc-docs/construction/model-serving/evidence/cierre-demo.md:34`.

**Resultado esperado.** Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 11,8 GiB)

**Comando.** Previsto: `free -m`; `docker stats --no-stream`; `memoria.sh antes`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 11,8 GiB) | _pendiente_ | _pendiente_ |

### K-02 — U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm…

- Demo: Base. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:358-359`, `tareas/U12-T04-demos-cli-y-manifiesto.md:583`, `identity-edge/docs/realm-importacion.md:34`, `CANDIDATAS.md:711`.

**Resultado esperado.** U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py

**Comando.** Previsto: `git log --oneline origin/main`; `grep -c repair_shared_authenticator_configs system-verification/tests/doubles/keycloak_tc.py`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py | _pendiente_ | _pendiente_ |

### K-03 — Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vig…

- Demo: Base. Fuentes: `aidlc-docs/construction/plans/demo-recorte-funcional.md:388`, `CANDIDATAS.md:401`, `governance/docs/paso-20-kind.md:11-20`.

**Resultado esperado.** Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida

**Comando.** Previsto: `ls reference-model/.out`; a mano: la vigencia normativa de reference-policy.json cubre los dos dias de la corrida.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida | _pendiente_ | _pendiente_ |

### K-04 — Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es …

- Demo: D3, D4. Fuentes: `aidlc-docs/construction/plans/demo-recorte-funcional.md:385`, `tareas/U12-T04-demos-cli-y-manifiesto.md:170`, `tareas/U12-T05-imagen-y-documentacion.md:374`, `platform/observability/values/kube-prometheus-stack-kind.yaml:5`.

**Resultado esperado.** Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; F5 a F10 caben en 3 dias (retencion de Prometheus)

**Comando.** Previsto: `date -u`; `observabilidad.sh consulta prometheus_tsdb_lowest_timestamp_seconds`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; F5 a F10 caben en 3 dias (retencion de Prometheus) | _pendiente_ | _pendiente_ |

### K-05 — La boveda de kind esta sembrada y no se ha reiniciado desde la siembra…

- Demo: Base. Fuentes: `platform/runbooks/install.md:146-152`, `identity-edge/docs/paso-16-kind.md:62-68`.

**Resultado esperado.** La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria)

**Comando.** Previsto: `kubectl --context kind-vectra get pods -n vault`; `kubectl --context kind-vectra get externalsecret -A`; `arranque.sh vault`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria) | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
