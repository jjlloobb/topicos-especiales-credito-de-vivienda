# Infrastructure Design — U7 `scoring-explainability`

Decisiones del plan (`scoring-explainability-infrastructure-design-plan.md`, Q1–Q3 = A). Se
apoya en la infraestructura compartida de U1. Los IDs `INF-U7-xx` se referencian en el plan
de tareas. Lo que se verifica «en kind» lo ejecuta el operador después de un PR aprobado
(AUTONOMIA-01).

---

## 1. Cómputo (Q1)

### INF-U7-01 — Recursos, escalado y probes

| Servicio | Requests | Limits | Escalado | PriorityClass |
|---|---|---|---|---|
| `scoring-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 % (estabilización 60 s hacia arriba / 300 s hacia abajo); spread por zona; PDB `minAvailable: 1` | `vectra-high` |
| `explainability-service` | 250m / 256 MiB | 1 CPU / 512 MiB | Igual | `vectra-high` |

- Namespace `vectra-app` y pool `general` (U1).
- Readiness (`/readyz`, puerto 8081) cada 5 s y liveness (`/livez`) cada 10 s, ambas solo con el proceso (P-U1-04).
- Sin `startupProbe`: la precarga del diccionario no bloquea el arranque (NFR-U7-21).
- Sidecar nativo de Linkerd (P-U1-05). Imágenes firmadas y verificadas por Kyverno (U1).
- Los valores son iniciales y se ajustan con la prueba de carga de U12 (NFR-U7-01).
- **Verificación**: `helm template` + `conftest`: requests y limits presentes, HPA 2–6, PDB, `topologySpreadConstraints` y `priorityClassName`.

### INF-U7-02 — Aporte a la cuota de `vectra-app` (NFR-U1-13)

| Concepto | CPU | Memoria |
|---|---|---|
| Requests en el máximo del HPA (12 pods) | 3 | 3 GiB |
| Limits en el máximo del HPA | 12 | 6 GiB |
| **Requests + 30 %** | **3,9** | **3,9 GiB** |
| **Limits + 30 %** | **15,6** | **7,8 GiB** |

- La `ResourceQuota` de `vectra-app` es la suma de los aportes de U3, U4, U7, U8, U9 y U11. Cada unidad declara el suyo en su Infrastructure Design y U1 la compone en su chart de namespaces.
- **Verificación**: prueba sobre el chart de U1: la cuota de `vectra-app` es ≥ la suma de los aportes declarados.

## 2. Apagado ordenado (Q2)

### INF-U7-03 — Drenaje antes de terminar
- `lifecycle.preStop.sleep.seconds: 5`. Es la acción `sleep` nativa de Kubernetes (habilitada desde 1.30, el mínimo de U1), así que no hace falta un binario `sleep` en la imagen. Da tiempo a que Linkerd y los `Endpoints` dejen de enviar tráfico al pod.
- Al recibir `SIGTERM`, uvicorn deja de aceptar conexiones y espera las solicitudes en curso con `timeout_graceful_shutdown = 10`.
- `terminationGracePeriodSeconds: 20`, que cubre 5 + 10 + margen y supera el peor caso de 6,1 s de P-U7-02.
- El proxy nativo de Linkerd termina después del contenedor de la app (sidecar nativo).
- Igual en explainability, aunque su peor caso sea de 700 ms.
- **Resultado**: un despliegue, un escalado hacia abajo o un desalojo voluntario no abandona un append, así que no produce entradas `recommendation` no entregadas (P-U7-03). Esas entradas quedan reservadas para fallas reales del registro.
- **Verificación**:
  - `conftest`: `preStop.sleep`, `terminationGracePeriodSeconds ≥ 20` y el parámetro de uvicorn en el comando del contenedor;
  - prueba de integración: con un registro doble que responde a los 3 s, se envía `SIGTERM` al proceso a los 0,5 s y la solicitud termina con `Recommendation` y `registry_entry_id`;
  - en kind (operador): un `rollout restart` de scoring durante la prueba de carga deja `vectra_registry_append_abandoned_total` en 0.
- **Satisface**: RESILIENCY-04 (despliegue sin pérdida de solicitudes), RESILIENCY-10; AUTONOMIA-06; P-U7-03.

## 3. Configuración (Q3)

### INF-U7-04 — Presupuestos de tiempo en el código
- Los presupuestos son constantes tipadas en `scoring/config.py` y `explainability/config.py`: 700 ms, los timeouts por llamada de NFR-U7-10, los intentos y el timeout del append, el timeout de `fail_closed`, los tamaños de pool de P-U7-04 y los umbrales del circuit breaker de NFR-U7-11. No se leen de variables de entorno.
- El chart solo inyecta URLs y puertos de las dependencias, la audiencia de cada cliente (U2), el endpoint de telemetría y el nivel de log. La llave privada del cliente de Keycloak (`private_key_jwt`) se monta desde un `ExternalSecret` (U2).
- Cambiar un presupuesto exige un PR al código que pase las pruebas de P-U7-01, 02 y 04.
- **Verificación**:
  - prueba unitaria: `PRE_REGISTRY_BUDGET + FAIL_CLOSED_APPEND_TIMEOUT + PROCESS_MARGIN ≤ 1000 ms`, y `TERMINATION_GRACE (20 s) > PRE_REGISTRY_BUDGET + 2 × APPEND_TIMEOUT + JITTER_MAX`;
  - `conftest`: el `Deployment` no define variables con los nombres de los presupuestos.
- **Satisface**: AUTONOMIA-02 (los valores verificados son los que corren); RESILIENCY-10.

## 4. Red

### INF-U7-05 — Sin flujos nuevos
- Entrada:
  - scoring: F15 (case-service);
  - explainability: F20 (scoring) y F12 (BFF).
- Salida:
  - scoring: F18, F19, F20 y F21;
  - explainability: F22, F23 y F103.
- Observabilidad: K02, K03 y K13.
- Todo ya está en `component-dependency.md`. Ningún egress (X01, X02), y las `NetworkPolicy` y `AuthorizationPolicy` de U1 y U2 ya cubren estos flujos.
- **Verificación**: suite de conectividad de U1 en kind (operador): los flujos permitidos responden; una llamada de scoring al core o a internet se bloquea.
- **Satisface**: AUTONOMIA-03, 05; SECURITY-07.

## 5. Cambios a otros artefactos

| Artefacto | Cambio |
|---|---|
| U7 FD `business-rules.md` §6 | Fila del apagado ordenado y del pendiente para U8 |
| Pendiente para U8 (case-service) | case-service también escribe en el registro (F16). Debe adoptar INF-U7-03 con su propio peor caso |

No se modifican artefactos de U0 ni de U1: no hay un chart común y la convención queda en
cada servicio que escribe evidencia.

## 6. Cumplimiento de extensiones (Infrastructure Design U7)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Las verificaciones en kind (INF-U7-03, 05) las ejecuta el operador después de un PR aprobado |
| AUTONOMIA-02 | Cumple | Cada `INF-U7-xx` tiene su «Verificación»; INF-U7-04 asegura que los presupuestos verificados son los que corren |
| AUTONOMIA-03 / 05 | Cumple | INF-U7-05 (sin egress ni acceso al core) |
| AUTONOMIA-06 | Cumple | INF-U7-03 (un despliegue no abandona un append) |
| SECURITY-07 | Cumple | INF-U7-05 (solo los flujos inventariados; deny by default de U1) |
| RESILIENCY-01 | Cumple | INF-U7-01 (`vectra-high`) |
| RESILIENCY-04 | Cumple | INF-U7-03 |
| RESILIENCY-06 | Cumple | INF-U7-01 (probes solo con el proceso) |
| RESILIENCY-08 / 09 | Cumple | INF-U7-01 (spread por zona, HPA, PDB), INF-U7-02 (cuota con margen) |
| RESILIENCY-10 | Cumple | INF-U7-03, 04 |
