# Plan de Infrastructure Design — U11 `product-metrics`

**Alcance:** llevar los componentes lógicos de U11 (`logical-components.md`) a recursos de
Kubernetes en kind, staging y producción, sobre la plataforma de U1.

**Ya decidido** (no se pregunta):
- **Namespace** `vectra-app` (U1 deployment-architecture), en la malla.
- **Réplicas y recursos** (NFR-U11-05, 13, 14): 2 réplicas fijas, PDB, spread por zona, `vectra-normal`; requests 100m / 256 MiB y limits 500m / 512 MiB por réplica, a confirmar con la prueba de memoria (P-U11-04); `maxSurge: 1`, `maxUnavailable: 0`; aporte a la cuota de `vectra-app` con el proxy y el pod del rollout.
- **Flujos existentes**: F28 (registro), F50 (Keycloak) y F60 (Prometheus). No hace falta uno nuevo. El Job de permisos de carpetas de Grafana es de U1 (F110).
- **Despliegue**: GitOps con Argo CD y sync manual, en la wave 5 (P-U1-12).

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Deployment Environment | Q5 |
| Compute Infrastructure | Q1 |
| Storage Infrastructure | Sin preguntas: U11 no tiene datos persistentes (todo se recalcula del registro) |
| Messaging Infrastructure | Sin preguntas: U11 no usa colas ni eventos; lee por HTTP |
| Networking Infrastructure | Q3 |
| Monitoring Infrastructure | Q4 |
| Shared Infrastructure | Q2, Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Exención de HPA y sondas (Compute; NFR-U1-12)

A) **Tercera exención documentada**:
   - `product-metrics` lleva `vectra.io/hpa-exempt` con la justificación «carga constante y baja; cada réplica lee y calcula por su cuenta, y escalar solo duplicaría lecturas sobre U3»; se agrega a la lista de NFR-U1-12 (hoy `bias-monitoring-service` y `console-spa`);
   - readiness (`/readyz`) y liveness (`/healthz`) solo del proceso, en 8081 (`ops_server`);
   - `terminationGracePeriodSeconds: 10`: al recibir `SIGTERM`, el servicio deja de tomar ciclos y termina la página en curso (una pasada a medias se descarta, P-U11-02);
   - **sin sonda de arranque larga**: el proceso queda listo en cuanto el `ops_server` responde, y la primera pasada completa (hasta 60 min con 10 veces el volumen) corre en segundo plano. Mientras no termina, el `Collector` no emite series de producto (P-U11-03) y `ProductMetricsStale` no dispara por la pasada en curso (P-U11-02).

   (Recomendado)

B) HPA de 2 a 2, sin exención

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: como la disponibilidad es solo del proceso, un `RollingUpdate` (`maxSurge: 1`, `maxUnavailable: 0`) da por lista a la réplica nueva antes de que termine su primera pasada. Con las dos réplicas reemplazadas, el dashboard puede quedar sin series de producto durante la pasada (minutos con el volumen esperado; hasta 60 min con 10 veces). `ProductMetricsStale` no dispara en ese lapso (P-U11-02). Se acepta, porque exigir datos para estar lista bloquearía el despliegue con U3 caído (NFR-U11-07). Mitigación: el runbook de despliegue indica esperar a que `vectra_product_metrics_last_success_timestamp` exista en la primera réplica antes de sincronizar la segunda (sync manual en la wave 5), y el INF-U11 lo registra como riesgo aceptado.
## Question 2 — Archivo de parámetros (Shared; BR-U11-09)

A) **Como el de U9**:
   - `product-metrics/chart/values-product-metrics-policy.yaml` en el monorepo, igual en los tres entornos;
   - `CODEOWNERS` de los equipos de producto y de riesgo en el monorepo y en GitOps, con la aprobación obligatoria de *code owners* que verifica `branch-protection-check` de U4;
   - `conftest` con los rangos de BR-U11-09;
   - el chart lo convierte en un `ConfigMap` montado sin `subPath`, con la anotación `checksum/config` para reiniciar los pods en el sync;
   - la `PrometheusRule` toma S del mismo archivo.

   (Recomendado)

B) Parámetros como constantes del código

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: un cambio en el archivo reinicia las dos réplicas y cada reinicio hace una pasada completa (mismo lapso sin series que en Q1). Es aceptable porque los parámetros cambian pocas veces; el runbook de cambio de parámetros remite al paso de Q1 (sincronizar una réplica a la vez).
## Question 3 — Red (Networking)

A) **Sin puerto de API**:
   - el `Service` expone solo 8081 (métricas y sondas); no hay puerto 8080 porque no hay API;
   - `Server` de Linkerd en 8081 que admite solo a Prometheus (F60);
   - salidas: F28 hacia `decision-registry-service` y F50 hacia Keycloak;
   - casos bloqueados en la suite de conectividad de U1: `product-metrics` → cualquier otro servicio de `vectra-app` (por ejemplo, `case-service` o `governance-service`); cualquier pod que no sea Prometheus → 8081 de `product-metrics`.

   (Recomendado)

B) Exponer también 8080 para una futura API

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: el `Server` de Linkerd en 8081 debe dejar pasar las sondas del kubelet a `/healthz` y `/readyz` (autorización automática de sondas de Linkerd); la suite de conectividad de U1 incluye `/readyz` → 200 con el `Server` aplicado, además de los dos casos bloqueados.
## Question 4 — Reglas, dashboards y runbooks (Monitoring)

A)
   - `PrometheusRule` del chart con las recording rules `:dedup`, las reglas generadas por `gen_rules.py` y las alertas de P-U11-06, cada una con `severity` y `runbook_url`;
   - `product.json` en la carpeta `Vectra / Producto` (permisos por el Job de U1, F110) y el panel de operación en la carpeta de operación de U1;
   - los dos como `ConfigMap` de dashboards de Grafana (U1), aprovisionados y de solo lectura;
   - runbooks de P-U11-06 en `product-metrics/observability/runbooks/`, con el test de runbooks de U1.

   (Recomendado)

B) Dashboards creados a mano en Grafana

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: el panel de operación va en la carpeta de operación de U1, cuyos permisos hay que listar en `folder-permissions.yaml` (hoy ese archivo solo tiene `Vectra / Sesgo` y `Vectra / Producto`). El runbook de `GrafanaFolderPermissionsDrift` es de U1 y sigue sin estar en el Paso 11 de su plan: se registra como cambio a U1.
## Question 5 — Entornos y prueba de volumen (Deployment Environment; NFR-U11-02, 12, 13)
Para medir con 10 veces el volumen hace falta un registro con mucho más que el volumen de la
demostración, y U11 no puede escribir en el registro.

A) **10 veces en CI con un doble; volumen real en kind**:
   - **CI**: un doble de U3 con la API de `metrics` (paginación por `seq`, filtros) sirve 10 veces el volumen de NFR-U3-30 durante 7 meses, con la latencia de página del p95 de U3; mide la duración de la pasada, el pico de memoria (`tracemalloc` y RSS) y la ausencia de lecturas simultáneas;
   - **kind** (operador): el registro real con los datos de la demostración de U12 (volumen × 1) y las pruebas de alertas, deduplicación y permisos de carpetas con los usuarios de U2;
   - **staging**: datos sintéticos de U12; **producción**: el registro real, sin datos de prueba;
   - ninguna identidad de prueba gana permiso para escribir en el registro.

   (Recomendado)

B) Un Job de kind que siembre el registro con 10 veces el volumen usando una identidad de escritura de prueba

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: con esta respuesta cambia la verificación de NFR-U11-02 y NFR-U11-13, hoy «prueba de carga en kind con 10 veces el volumen». Pasa a ser CI con doble de U3 a 10× (duración de la pasada, memoria y no-simultaneidad), más kind a 1× con el registro real. El doble no reproduce la contención del pool `projections` de U3 (una conexión) con carga real; esa medición a 10× contra U3 queda para Operations (RESILIENCY-14 = C, U0 P-U0-08). Se registra el cambio en NFR-U11-02 y 13. Depende de los datos de demostración de U12, que aún no están definidos.
## Question 6 — Credencial del cliente de Keycloak (Shared; NFR-U11-20)

A) **`ExternalSecret` como los demás servicios**: la llave privada del cliente `product-metrics` (`private_key_jwt`) llega por ESO desde Vault (kind) o la bóveda del banco (staging y producción), montada como archivo de solo lectura; `ServiceAccount` propia `product-metrics` sin token de Kubernetes montado. (Recomendado)

B) Secret creado a mano

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: `automountServiceAccountToken: false` en la `ServiceAccount`; el proxy de Linkerd obtiene su identidad con su propio volumen proyectado, así que no depende del token montado. La rotación de la llave del cliente `product-metrics` sigue el mismo procedimiento que los demás clientes `private_key_jwt` de U2 (dos llaves en el JWKS durante el cambio).
---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `infrastructure-design.md` (INF-U11-xx)
- [x] `deployment-architecture.md`
- [x] Cambios a otras unidades (U1 NFR-U1-12, cuotas y suite de conectividad) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
