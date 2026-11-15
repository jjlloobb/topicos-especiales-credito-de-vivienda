VEREDICTO: NO-VERDE

# Ronda 1 — U12-T08

Revisada `48c66f2` (diff propio `776626c..48c66f2`, 17 archivos). Mutaciones en una copia privada, ya borrada. Nada contra `kind-vectra`. **[E]** = ejecutado por el revisor; **[L]** = solo leído.

**Nota del orquestador (2026-11-15):** el PR #182 se fusionó en `main` antes de que esta revisión terminara. No hay ningún ROJO. Los tres NARANJA y los AMARILLO quedan en `CANDIDATAS.md`; no se abre otra tarea de pulido antes de desplegar.

## Criterios de aceptación, verificados por el revisor

| # | Comando | Resultado |
|---|---|---|
| CA-1 | `make -C identity-edge render-keycloak` y `cmp` contra `origin/main` | pasa [E]: staging y prod idénticos byte a byte; en kind solo cambia la línea 176, `maxReplicas: 4 → 1` |
| CA-2 | `make -C identity-edge policy-keycloak policy-keycloak-u1 check-keycloak-rendered policy-gateway`; `pytest identity-edge/tests/unit/test_keycloak_deploy.py` | pasa [E]: rc 0; 364 passed |
| CA-3 | `pytest platform --rootdir=platform --import-mode=importlib` sin `platform/.tools` | pasa [E]: 952 passed, 0 skipped; `PENDING_UNBOUNDED` ya no existe |
| CA-4 | `! grep -rn '11,8' …` y `pytest test_kind_guide test_kind_inventory test_demos_closed_world` | pasa [E]: 164 passed |
| CA-5 | el mismo pytest y un driver propio de mutaciones | pasa [E]: las tres mutaciones de F-02 mueren |
| CA-6 | `pytest test_kind_scripts.py -k vault` | pasa [E]: 13 passed |
| CA-7 | `make -C system-verification check`, una vez | pasa [E]: rc 0 en 25:33; 1247, 978 y 32 passed; 625 Markdown sin enlaces rotos; 0 skipped |

**Keycloak 1-1 [E].** Con `--combine`, `hpa-max-replicas` muerde en todos los casos (kind con 0, 2, 3, 4, 5, 100 o `"1"`; staging y prod con 0, 1, 2, 3, 5 o 100; sin `maxReplicas` en los tres; `min 3 max 2`). Kind con 1 y staging y prod con 4 pasan. Staging o prod con la señal de kind y el HPA 1-1 caen por `config-cli-only-kind`. **Sin `--combine`, todos pasan** (F-06).

**Presupuesto [E].** Pico de D2: 13,7344 GiB y 10,665 CPU (render 12,5781 + Job de validación 1,0195 + kube-system 0,1367). Margen frente a los topes (13,8 y 10,7): 0,0656 GiB y 0,035 CPU; frente a la máquina (14,8157 GiB): 1,0813 GiB. `growable_hpas` devuelve `[]`. La prueba general de los HPA sigue mordiendo (Keycloak de kind con máximo 2; `decision-registry` con máximo 6).

**Cifras atadas [E].** `BUDGET_GIB = 13.9` en la copia → 8 fallan, con hallazgos en los 5 archivos. No se tocaron «14 GiB como mínimo, 16 recomendados» ni el mínimo de la guía.

**Bóveda [E].** 17 de 17 casos con el doble dan el código esperado, incluidos 0 reinicios y sincronizada antes del arranque → 1, y lista vacía → 1. El caso O es F-03.

**Alcance [E].** Nada en `src/`, `demos/`, `Dockerfile`, `seccomp/`, `platform/runbooks/` ni `seed-vault.sh`; del README, una línea; `CANDIDATAS.md` añade al final.

## Hallazgos

### F-01 · NARANJA · `paso-18-kind.md:42,56,58,59`; `inventario.yaml:48,76`; `evidence/kind/00-prerrequisitos.md:15` · Citas por número de línea que ya no apuntan a lo que dicen
`install.md`, «líneas 150 a 163», es desde U01-T13 el «Simulacro de failover de zona»; «Vault reiniciado» está en 169 a 179. `PERFIL:34` y `test_kind_profile.py:34` no son `BUDGET_GIB` (está en la 61). `INST:146-152` cae en «10. Otros». Ninguna prueba ata estas citas. Arreglo: citar por ancla o por nombre, sin número de línea, y que la prueba lo prohíba.

### F-02 · NARANJA · `test_kind_guide.py`, `runbook_step_number_findings` · Compara conjuntos de números por paso y solo mira los seis primeros pasos
Sobreviven: intercambiar dentro del paso 6 (Keycloak citando el paso 7 y PostgreSQL el 8), y una cita nueva en el paso 7 de la guía.

### F-03 · NARANJA · `docs/kind/arranque.sh:82-91` · Un ExternalSecret roto por otra causa recibe el diagnóstico «resembrar»
Con 0 reinicios, tres ExternalSecret resembrados y uno en `SecretSyncedError` con `refreshTime` posterior al arranque, el guion dice «no se sincronizaron después de su arranque … vuelve a sembrar». Es falso, y resembrar no cambia nada (`seed-vault.sh` conserva lo que existe). Escenario realista: `seed-vault.sh identity` deja `Ready=False` los ExternalSecret de U3 a U11 tras una resiembra. Arreglo: separar «sincronizado antes del arranque» (resembrar) de «no `SecretSynced` después del arranque» (otra causa: mirar ese ExternalSecret).

### F-04 · AMARILLO · `test_kind_guide.py`, `ORDER_VERBS` · Lista de verbos cerrada
Sobreviven, en prosa sin acentos graves: `kubectl scale statefulset tempo`, `kubectl edit statefulset loki`, `argocd app terminate-op alloy`, y «Abre Loki con kubectl port-forward».

### F-05 · AMARILLO · `test_kind_guide.py`, `asks_for` · Falsos positivos en menciones históricas («En los logs de Tempo…», `grafana/loki`, «El status de Loki era 403»). Con el texto real de la guía no hay ninguno.

### F-06 · AMARILLO · `identity-edge/keycloak/policy/keycloak.rego` · La pasada por documento ya no vigila ni el mínimo ni el máximo del HPA
Ningún objetivo la corre sola. **Ningún workflow de la CI corre las políticas de identity-edge** (ya era así).

### F-07 · AMARILLO · `test_demos_closed_world.py:1180`; `platform/tests/test_kind_profile.py:58` · Comentarios desfasados

### F-08 · AMARILLO · `test_kind_scripts.py`, `refresh_policy_findings` · No cubre `refreshInterval: 0` (hoy no hay ninguno)

## Tareas candidatas
- U1, `platform/runbooks/install.md:33`: dice «requests de CPU (11,2)» y «14,75 GiB con Keycloak en 2 réplicas (13,73 con 1)»; los valores actuales son 10,7 CPU y Keycloak fijo en 1-1.
- CI: ningún workflow corre `make -C identity-edge policy-keycloak` ni `policy-gateway`.
- U12: la puerta de la bóveda limitada a los ExternalSecret cuyo almacén es la bóveda.

```
VEREDICTO: NO-VERDE
NARANJA|paso-18-kind.md:42,56,58,59; inventario.yaml:48,76; evidence/kind/00-prerrequisitos.md:15|citas por número de línea desfasadas y sin atar
NARANJA|tests/unit/test_kind_guide.py:runbook_step_number_findings|comparación por conjuntos y solo seis pasos
NARANJA|docs/kind/arranque.sh:82-91|un ExternalSecret roto por otra causa recibe «vuelve a sembrar»
AMARILLO|tests/unit/test_kind_guide.py:ORDER_VERBS|sobreviven órdenes en prosa con scale, edit, terminate-op
AMARILLO|tests/unit/test_kind_guide.py:asks_for|falsos positivos en menciones históricas
AMARILLO|identity-edge/keycloak/policy/keycloak.rego|la pasada sin --combine no vigila ni el mínimo ni el máximo
AMARILLO|test_demos_closed_world.py:1180; test_kind_profile.py:58|comentarios desfasados
AMARILLO|tests/unit/test_kind_scripts.py:refresh_policy_findings|no cubre refreshInterval: 0
INFORME: revisiones/U12-T08/ronda-1.md
```
