# 00 — Prerrequisitos

**Estado: completa, con el hallazgo H-1.** Llenada el 2026-11-20 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F0 (Prerrequisitos).
- Fecha: 2026-11-20 (jornada 1), entre las 12:27 y las 13:00 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 9dc027f.
- Duración real de la fase: unos 15 min (solo comprobaciones) (estimada: 30 min, más la instalación de la plataforma si parte de cero; la guía pide anotarla).

Entradas de esta fase: K-01, K-02, K-03, K-04, K-05.

### K-01 — Memoria del host

- Demo: Base. Fuentes: `platform/runbooks/install.md:20`, `platform/tests/test_kind_profile.py:61`, `DECISIONES-LOOP.md:78-86`, `tareas/U12-T05-imagen-y-documentacion.md:35`, `aidlc-docs/construction/model-serving/evidence/cierre-demo.md:34`.

**Resultado esperado.** Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 13,8 GiB)

**Comando.** Previsto: `free -m`; `docker stats --no-stream`; `memoria.sh antes`.

```bash
free -m; system-verification/docs/kind/memoria.sh antes | tail -2
```

**Salida.**

```text
               total        used        free      shared  buff/cache   available
Mem:           15171       11671         247         318        3911        3499
Swap:           4095        2047        2048
46 pods medidos; fase antes; disponible 3499 MiB (puerta 8192 MiB)
FALLA solo hay 3499 MiB disponibles y la puerta de `antes` pide 8192: cierra todo lo demas y no sigas (riesgo R-4)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 13,8 GiB) | 15171 MiB de RAM; unos 3500 MiB disponibles con el cluster ya instalado y sano (los tres nodos de kind ocupan unos 10,2 GiB); `memoria.sh antes` sale 1 | no: la puerta de 8 GiB es de antes de instalar y aqui el cluster ya estaba instalado; ver hallazgo H-1 |

### K-02 — U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm…

- Demo: Base. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:358-359`, `tareas/U12-T04-demos-cli-y-manifiesto.md:583`, `identity-edge/docs/realm-importacion.md:34`, `CANDIDATAS.md:711`.

**Resultado esperado.** U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py

**Comando.** Previsto: `git log --oneline origin/main`; `grep -c repair_shared_authenticator_configs system-verification/tests/doubles/keycloak_tc.py`.

```bash
for t in U12-T03 U12-T04 U12-T05 U02-T22 U00-T04; do echo "$t: $(git log --oneline origin/main --grep=$t | wc -l) commits en origin/main"; done; grep -c repair_shared_authenticator_configs system-verification/tests/doubles/keycloak_tc.py
```

**Salida.**

```text
U12-T03: 52 commits en origin/main
U12-T04: 41 commits en origin/main
U12-T05: 24 commits en origin/main
U02-T22: 14 commits en origin/main
U00-T04: 21 commits en origin/main
0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py | las cinco tareas tienen commits en origin/main; 0 apariciones de la reparacion | si |

### K-03 — Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vig…

- Demo: Base. Fuentes: `aidlc-docs/construction/plans/demo-recorte-funcional.md:388`, `CANDIDATAS.md:401`, `governance/docs/paso-20-kind.md:11-20`.

**Resultado esperado.** Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida

**Comando.** Previsto: `ls reference-model/.out`; a mano: la vigencia normativa de reference-policy.json cubre los dos dias de la corrida.

```bash
ls reference-model/.out reference-model/.out/proxy reference-model/.out/adversarial/rt3; grep -o '"effective_[a-z]*": *[^,}]*' reference-model/.out/reference-policy.json
```

**Salida.**

```text
reference-model/.out:
adversarial
datasets
package
proxy
reference-policy.json

reference-model/.out/adversarial/rt3:
RT3-a
RT3-b
RT3-c
RT3-d

reference-model/.out/proxy:
run-1
run-2
run-3
run-4
run-5
"effective_from": "2026-01-01"
"effective_to": null
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida | base, proxy/run-1 a run-5 y adversarial/rt3 (RT3-a a RT3-d); vigencia desde 2026-01-01 sin fecha de fin | si |

### K-04 — Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es …

- Demo: D3, D4. Fuentes: `aidlc-docs/construction/plans/demo-recorte-funcional.md:385`, `tareas/U12-T04-demos-cli-y-manifiesto.md:170`, `tareas/U12-T05-imagen-y-documentacion.md:374`, `platform/observability/values/kube-prometheus-stack-kind.yaml:5`.

**Resultado esperado.** Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; D4 solo pasa durante el dia D + 1 UTC (hasta las 00:00 UTC de D + 2); F5 a F10 caben en 3 dias (retencion de Prometheus)

**Comando.** Previsto: `date -u`; `observabilidad.sh consulta prometheus_tsdb_lowest_timestamp_seconds`.

```bash
date -u; system-verification/docs/kind/observabilidad.sh consulta prometheus_tsdb_lowest_timestamp_seconds | sed 's/.*} /lowest_timestamp_seconds /'; date -u -d @1794895200
```

**Salida.**

```text
Fri Nov 20 12:32:48 PM UTC 2026
lowest_timestamp_seconds 1794895200
Tue Nov 17 06:00:00 AM UTC 2026
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; D4 solo pasa durante el dia D + 1 UTC (hasta las 00:00 UTC de D + 2); F5 a F10 caben en 3 dias (retencion de Prometheus) | jornada 1 el 2026-11-20; dia D previsto el 2026-11-21 y D + 1 el 2026-11-22 (no es dia 1); el dato mas viejo de Prometheus es del 2026-11-17 06:00 UTC | si (el lanzamiento de decisions antes de las 22:18 UTC se comprueba en F6) |

### K-05 — La boveda de kind esta sembrada y no se ha reiniciado desde la siembra…

- Demo: Base. Fuentes: `platform/runbooks/install.md:169-178`, `identity-edge/docs/paso-16-kind.md:62-68`.

**Resultado esperado.** La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria)

**Comando.** Previsto: `kubectl --context kind-vectra get pods -n vault`; `kubectl --context kind-vectra get externalsecret -A`; `arranque.sh vault`.

```bash
kubectl --context kind-vectra get pods -n vault; kubectl --context kind-vectra get externalsecret -A --no-headers | grep -vc SecretSynced; system-verification/docs/kind/arranque.sh vault | tail -8
```

**Salida.**

```text
NAME      READY   STATUS    RESTARTS       AGE
vault-0   1/1     Running   23 (10h ago)   18d
0
AVISO vault/vault-0 [vault]: la boveda se reinicio (23 reinicios, ultimo codigo 255), resembrada: todos los ExternalSecret se sincronizaron despues de su arranque (K-05)
vault: 1 pods, 0 hallazgos
linkerd-cni: 3 pods, 0 hallazgos
ExternalSecret: 0 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria) | vault-0 Running; 0 ExternalSecret sin SecretSynced; la boveda se reinicio con la maquina el 2026-11-19 y se resembro despues (`arranque.sh` lo dice como AVISO, no como hallazgo) | si |

## Hallazgos

- **H-1 (U12, la guia y `memoria.sh`; riesgo R-4). Resuelto en el PR #223.** `memoria.sh antes` salio 1 con unos 3500 MiB disponibles frente a una puerta de 8192. Causa: el guion lee los pods y Prometheus, asi que solo corre con el cluster instalado, y su puerta era la de antes de instalar; con el kind sano los tres nodos ocupan unos 10,4 GiB de los 14,8 y esa puerta no podia pasar. La memoria de la maquina esta bien: ningun `OOMKilled`, ningun pod sin programar y el intercambio (2 GiB usados) no se mueve en reposo. El PR #223 deja la puerta de `antes` en 3072 MiB (la de `durante`, 1536, mas el contenedor de U12, 1024, mas 512 para los pods de modelo de D2); con el, `memoria.sh antes` sale 0 contra el cluster (3537 MiB disponibles). Los 8 GiB de K-01 son una lectura de `free -m` antes de instalar, y no se midieron: el cluster ya estaba instalado. El pico real de D2 se mide en F8.
