# Infrastructure Design — U11 `product-metrics`

Decisiones del plan (`product-metrics-infrastructure-design-plan.md`, Q1–Q6 = A, con las notas
del usuario). Los IDs `INF-U11-xx` se referencian en el plan de tareas.

U11 no tiene almacenamiento persistente ni mensajería: todo se recalcula del registro (F28).

---

## 1. Cómputo (Q1)

### INF-U11-01 — Réplicas, recursos, sondas y rollout (NFR-U11-05, 07, 13, 14)

| Aspecto | Valor |
|---|---|
| Namespace | `vectra-app`, en la malla |
| Réplicas | 2 fijas, `vectra.io/hpa-exempt` («carga constante y baja; cada réplica lee y calcula por su cuenta, y escalar solo duplicaría lecturas sobre U3»), PDB `minAvailable: 1`, spread por zona |
| Recursos | requests 100m / 256 MiB; limits 500m / 512 MiB; a confirmar con la prueba de memoria (P-U11-04) |
| PriorityClass | `vectra-normal` |
| Rollout | `RollingUpdate` con `maxSurge: 1`, `maxUnavailable: 0`; `progressDeadlineSeconds: 4800` (80 min, por encima del plazo de 75 min de la pasada) |
| Apagado | `terminationGracePeriodSeconds: 10`: al recibir `SIGTERM` deja de tomar ciclos y termina la página en curso; una pasada a medias se descarta (P-U11-02) |
| Liveness | `/healthz` en 8081: solo el proceso |

**Readiness y rollout** (nota de Q1; ajustada en esta etapa):
- **El riesgo de la nota**: con una readiness solo del proceso, el rollout da por lista a la réplica nueva antes de que termine su primera pasada. Con las dos réplicas reemplazadas, el dashboard puede quedar sin series de producto durante la pasada (minutos con el volumen esperado, hasta 60 min con 10 veces).
- **Por qué no la mitigación propuesta**: la nota proponía que el runbook esperara a la primera réplica antes de sincronizar la segunda. No se puede hacer con un sync de Argo CD, que aplica el `Deployment` entero; pausar el rollout exigiría `kubectl rollout pause`, que AUTONOMIA-01 no permite.
- **Mitigación automática** (acotada en la revisión del Infrastructure Design de U11, 2026-10-10): `/readyz` responde 200 si y solo si:
  - el proceso tiene una instantánea publicada (terminó su primera pasada); **o**
  - el breaker hacia U3 está **abierto o semiabierto** (U3 no responde).
- **No** basta que la primera pasada haya fallado: un timeout aislado o el plazo de 75 min con U3 lento pero vivo dejarían la réplica lista sin datos, el rollout reemplazaría la segunda réplica y el dashboard quedaría vacío. Solo el breaker abierto cuenta como «U3 no responde».
- **Breaker de U11 hacia U3**: el breaker de `deps.call` en modo `consecutive_failures` de U0 (NFR-U0-23 (i)) con 3 fallos, 60 s y 1 éxito, no una implementación propia (pendientes consolidados, 2026-10-10), porque los umbrales de U7 (≥ 50 % de fallos en 20 llamadas dentro de 30 s) no se alcanzan nunca con lecturas en serie de una página a la vez y 5 s de timeout:
  - se abre con **3 fallos seguidos** (timeout, conexión o 5xx, según U0);
  - pasa a semiabierto a los 60 s;
  - se cierra con 1 éxito.

  Con U3 tan lento que toda página vence, el breaker se abre y la réplica queda lista: equivale a U3 caído. Una página lenta suelta o una pasada que vence su plazo no lo abren.
- **Cuando el breaker se cierra sin instantánea**: `/readyz` vuelve a 503 hasta que la pasada en curso (o la siguiente) termine y publique la instantánea. Semiabierto cuenta como abierto, para que la readiness no oscile cada 60 s mientras U3 sigue caído.
- **El `Service` publica las direcciones no listas** (`publishNotReadyAddresses: true`): su único consumidor es Prometheus (F60), y así una réplica no lista sigue en el scrape. `up` y las alertas por réplica la ven, y las series de operación del ciclo siguen llegando.
- Así:
  - con U3 sano, Kubernetes no reemplaza la segunda réplica hasta que la primera nueva tiene datos, y el dashboard nunca queda vacío por un despliegue;
  - con U3 caído, el breaker se abre en unos 15 s, la réplica queda lista y el despliegue no se bloquea (NFR-U11-07).
- La espera la hace el propio rollout, dentro de `progressDeadlineSeconds`.
- `vectra_common.ops_server` recibe esta regla como **predicado de readiness** (cambio a U0, §7); NFR-U11-07 y P-U1-04 cambian (§7).
- Un cambio del archivo de parámetros (`checksum/config`, INF-U11-02) reinicia las réplicas con la misma regla, una a la vez (nota de Q2).

**Aporte a la cuota de `vectra-app`**: 3 pods en el peor momento (2 + 1 de `maxSurge`), con el
proxy de Linkerd (P-U1-14) y el 30 % de margen: requests ≈ 0,78 CPU y 1,05 GiB; limits ≈ 3,9 CPU
y 2,44 GiB (NFR-U11-14; plan de U1, Paso 6).

- **Verificación**:
  - `helm template` + `conftest` (réplicas, exención, PDB, spread, PriorityClass, estrategia, `progressDeadlineSeconds`);
  - `kyverno test` de `require-hpa-bounds`;
  - prueba de readiness: sin instantánea y con U3 sano → 503; con instantánea → 200; sin instantánea y breaker abierto → 200; sin instantánea, breaker abierto que luego se cierra → 503 hasta la instantánea; una primera pasada que vence su plazo con U3 lento pero sin 3 fallos seguidos → 503; 3 timeouts seguidos → breaker abierto → 200;
  - en kind (operador): un rollout con U3 sano → en ningún momento faltan las series `:dedup` de producto; un rollout con U3 caído → termina sin esperar.
- **Satisface**: NFR-U11-05, 07, 13, 14; RESILIENCY-01, 08, 09.

## 2. Parámetros y secretos (Q2, Q6)

### INF-U11-02 — `values-product-metrics-policy.yaml` (BR-U11-09)
- `product-metrics/chart/values-product-metrics-policy.yaml` en el monorepo, igual en los tres entornos.
- `CODEOWNERS` de los equipos de producto y de riesgo en el monorepo y en GitOps; `branch-protection-check` de U4 verifica la aprobación obligatoria de *code owners* en los dos.
- `conftest` con los rangos de BR-U11-09.
- El chart lo convierte en un `ConfigMap` montado sin `subPath`, con `checksum/config`; la `PrometheusRule` toma S del mismo archivo.
- Un cambio reinicia las réplicas una a una, cada una con su pasada completa (INF-U11-01); como los parámetros cambian poco, el lapso se acepta y el runbook de cambio de parámetros lo dice (nota de Q2).
- **Verificación**: `conftest` dentro y fuera de rango; `CODEOWNERS` con la línea del archivo en los dos repositorios; `helm template` con `checksum/config`.
- **Satisface**: BR-U11-09; SECURITY-11.

### INF-U11-03 — Identidad (NFR-U11-20)
- `ServiceAccount` `product-metrics` con `automountServiceAccountToken: false`. El proxy de Linkerd obtiene su identidad con su propio volumen proyectado, así que no depende del token montado (nota de Q6).
- La llave privada del cliente `product-metrics` (`private_key_jwt`) llega por un `ExternalSecret` desde Vault (kind) o la bóveda del banco (staging y producción), montada como archivo de solo lectura.
- **Rotación**: el procedimiento de los demás clientes `private_key_jwt` de U2 (dos llaves publicadas durante el cambio).
- **Verificación**: `conftest` (`automountServiceAccountToken: false`, sin Secret plano); `linkerd check --proxy` en kind con la réplica en la malla.
- **Satisface**: SECURITY-06, 09, 12.

## 3. Red (Q3)

### INF-U11-04 — Puertos y políticas (NFR-U11-21)

| Pieza | Puerto | Admite | Sale hacia |
|---|---|---|---|
| `product-metrics` | 8081 (métricas y sondas) | Prometheus (F60) y las sondas del kubelet | F28 (`decision-registry-service`), F50 (Keycloak) |

- El `Service` expone solo 8081; no hay puerto 8080 porque no hay API.
- El `Server` de Linkerd en 8081 admite solo a Prometheus; las sondas del kubelet a `/healthz` y `/readyz` pasan por la autorización automática de sondas de Linkerd (nota de Q3).
- **Casos de la suite de conectividad de U1**:
  - `/readyz` desde el kubelet → 200 con el `Server` aplicado;
  - `product-metrics` → `case-service` o `governance-service` → bloqueado;
  - un pod que no es Prometheus → 8081 de `product-metrics` → bloqueado.
- **Verificación**: `platform/network/generate.py --check`; la suite en kind (operador).
- **Satisface**: SECURITY-06, 07; AUTONOMIA-03, 05.

## 4. Observabilidad (Q4)

### INF-U11-05 — Reglas, dashboards y runbooks (P-U11-05, 06)
- `PrometheusRule` del chart con las recording rules `:dedup`, las reglas generadas por `gen_rules.py` y las alertas de P-U11-06, cada una con `severity` y `runbook_url`.
- `product.json` en `Vectra / Producto`, y el panel de operación de U11 en la carpeta de operación de U1; los dos como `ConfigMap` de dashboards de Grafana, aprovisionados y de solo lectura.
- **Permisos** (nota de Q4): `folder-permissions.yaml` de U1 lista **tres** carpetas:
  - `Vectra / Sesgo`, para `cro` y `cumplimiento`;
  - `Vectra / Producto`, para `cro`, `cumplimiento` e `ingeniero_riesgo`;
  - la carpeta de operación, para `operacion`, con `Edit`.

  El runbook `grafana-folder-permissions-drift` de U1 se agrega al Paso 11 de su plan.
- Runbooks de U11 en `product-metrics/observability/runbooks/`, con el test de runbooks de U1.
- **Verificación**: `promtool test rules`; prueba de referencias a series crudas (P-U11-05); test de runbooks; prueba del aprovisionamiento con las tres carpetas.
- **Satisface**: RESILIENCY-05, 07, 15.

## 5. Entornos y prueba de volumen (Q5)

### INF-U11-06 — CI, kind, staging y producción (NFR-U11-02, 12, 13)

| Entorno | Datos | Qué se mide |
|---|---|---|
| CI | Doble de U3 con la API `metrics` (paginación por `seq`, filtros) y **10 veces** el volumen de NFR-U3-30 durante 7 meses, con la latencia de página del p95 de U3 | Duración de la pasada (NFR-U11-02), pico de memoria con `tracemalloc` y RSS (NFR-U11-12, 13), ninguna lectura simultánea (P-U11-02) |
| kind (operador) | Registro real con los datos de la demostración de U12 (2 000 decisiones, BR-U12-06) | Alertas, deduplicación, readiness en un rollout, permisos de carpetas con los usuarios de U2 |
| staging | Datos sintéticos de U12 | Humo después del sync |
| producción | Registro real | — |

- Ninguna identidad de prueba gana permiso para escribir en el registro.
- **Límite de la prueba** (nota de Q5): el doble no reproduce la contención del pool `projections` de U3 (una conexión) con carga real. Esa medición a 10 veces contra U3 queda para Operations (RESILIENCY-14 = C, U0 P-U0-08).
- La prueba en kind usa los datos de demostración de U12: **2 000** casos `normal` decididos por el conductor (U12 BR-U12-06 y plan, Paso 6), con la lectura del día siguiente (cerrado en pendientes consolidados, segunda tanda, 2026-10-10).
- **Satisface**: NFR-U11-02, 12, 13; AUTONOMIA-01.

## 6. Cumplimiento de extensiones (Infrastructure Design U11)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-06 / 07 | Cumple | INF-U11-03, 04 |
| SECURITY-09 / 12 | Cumple | INF-U11-03 (`ExternalSecret`, sin token montado) |
| SECURITY-11 | Cumple | INF-U11-02 (rangos y revisión de los parámetros) |
| RESILIENCY-01 / 08 / 09 | Cumple | INF-U11-01 |
| RESILIENCY-05 / 07 / 15 | Cumple | INF-U11-05 |
| AUTONOMIA-01 | Cumple | Sync manual en la wave 5; el rollout espera solo por readiness, sin pasos manuales en el clúster (INF-U11-01) |
| AUTONOMIA-03 / 05 | Cumple | INF-U11-04 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U11 NFR-U11-07 | Readiness: lista con instantánea o con el breaker hacia U3 abierto o semiabierto (antes, solo el proceso; acotada en la revisión del Infrastructure Design de U11, 2026-10-10: una pasada fallida ya no basta) | Q1 (ajuste de esta etapa); revisión del Infrastructure Design de U11, 2026-10-10 |
| U11 NFR-U11-09 y P-U11-01 | Breaker hacia U3 (el breaker de `deps.call` en modo `consecutive_failures` de U0 (NFR-U0-23 (i)); pendientes consolidados, 2026-10-10): 3 fallos seguidos, semiabierto a los 60 s, 1 éxito para cerrar (los umbrales de U7 no se alcanzan con lecturas en serie) | revisión del Infrastructure Design de U11, 2026-10-10 |
| U0 NFR-U0-48, logical-components y plan (Paso 10) | `ops_server` recibe un predicado de readiness opcional (por omisión, solo el proceso); caso nuevo en `test_ops_server.py` | revisión del Infrastructure Design de U11, 2026-10-10 |
| U1 P-U1-04 | Fila propia de `product-metrics`: readiness con instantánea o breaker hacia U3 abierto (antes en la fila «bias, BFF, métricas → solo su proceso») | revisión del Infrastructure Design de U11, 2026-10-10 |
| U11 NFR-U11-02 y NFR-U11-13 | Verificación: CI con doble de U3 a 10 veces y kind a 1 vez; la medición a 10 veces contra U3 real queda para Operations | Q5 |
| U1 NFR-U1-12 | `product-metrics` en la lista de exenciones de HPA, con su justificación | Q1 |
| U1 plan (Pasos 3 y 10) y suite de conectividad | Casos de INF-U11-04; `folder-permissions.yaml` con la carpeta de operación | Q3, Q4 |
| U1 plan (Paso 11) | Runbook `grafana-folder-permissions-drift` | Q4 |
| U12 BR-U12-06 y plan (Paso 6) | Datos de demostración para la prueba en kind de U11: 2 000 casos `normal` decididos (cerrado en pendientes consolidados, segunda tanda, 2026-10-10) | Q5 |
