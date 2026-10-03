# Patrones de NFR Design — U1 `platform-foundation`

Decisiones del plan (`platform-foundation-nfr-design-plan.md`, Q1–Q12 = A). Los IDs
`P-U1-xx` se referencian en Infrastructure Design y en el plan de tareas. Todas las
verificaciones corren en kind o sobre manifiestos renderizados (AUTONOMIA-01).

---

## 1. Seguridad

### P-U1-01 — Red generada desde un inventario de flujos (Q1)
- `platform/network/flows.yaml` es la única fuente de los flujos permitidos. Refleja las tablas de `component-dependency.md` (F01–F73, más los flujos nuevos que agregue el Infrastructure Design de U1).
- Cada entrada tiene `id`, `from` (namespace + ServiceAccount), `to` (namespace + ServiceAccount + puerto), `protocol` y `justification`.
- `platform/network/generate.py` produce, para cada namespace de Vectra:
  - la NetworkPolicy `deny-all` de ingress y egress;
  - una NetworkPolicy `allow-<flow-id>` por flujo;
  - el DNS hacia `kube-dns` como única excepción común;
  - los recursos `Server` y `AuthorizationPolicy` de Linkerd (P-U1-02);
  - las pruebas de conectividad: por flujo, un caso permitido y otro bloqueado.
- **Verificación**: `python platform/network/generate.py --check` (CI falla si los manifiestos versionados difieren de los generados) y la suite de conectividad en kind.
- **Satisface**: NFR-U1-20; NFR-SEC-07; AUTONOMIA-05; US-604.

### P-U1-02 — Autorización por identidad en Linkerd (Q2)
- Anotación `config.linkerd.io/default-inbound-policy: deny` en todos los namespaces de Vectra.
- Por cada flujo de `flows.yaml`: un `Server` (puerto del destino) y una `AuthorizationPolicy` con `MeshTLSAuthentication` que admite solo la identidad (ServiceAccount) de origen.
- Excepciones explícitas, también en el inventario: probes del kubelet y scrape de Prometheus al puerto 8081.
- **Verificación**: prueba en kind desde un pod de otra ServiceAccount del mismo namespace → 403 de Linkerd; `linkerd viz authz` muestra la política por flujo.
- **Satisface**: NFR-U1-21; SECURITY-08 (defensa en profundidad), SECURITY-06.

### P-U1-03 — Jerarquía de certificados (Q12)
- La jerarquía de Linkerd la gestiona cert-manager:
  - trust anchor de 1 año, con alerta 30 días antes y rotación por runbook con dos anchors en paralelo;
  - issuer intermedio rotado automáticamente cada 48 h.
- Los certificados del borde (Envoy Gateway) y de PostgreSQL duran 90 días y se renuevan a los 60.
- Alerta `CertificateExpiringSoon`: SEV2 a menos de 7 días, SEV1 a menos de 24 h.
- **Verificación**: `cmctl status certificate` en kind; prueba de rotación del issuer sin cortes (`linkerd check --proxy`).
- **Satisface**: NFR-U1-21, 22; SECURITY-01.

## 2. Resiliencia

### P-U1-04 — Readiness acotada a dependencias propias (Q3)
- **Liveness**: superficial; el proceso responde en el puerto 8081.
- **Readiness**: solo las dependencias **propias** de datos:

| Servicio | Readiness depende de |
|---|---|
| case-service | `case-db` |
| governance-service | `governance-db` |
| decision-registry-service | `registry-db` (incluida la escritura posible: réplica síncrona disponible) |
| scoring-service, explainability-service, bias, BFF, métricas | ninguna dependencia externa (solo su proceso) |

- **Fuera de la readiness**: governance/`serving-config`, KServe, explainability y el registro, vistos desde scoring o case. Su caída la maneja el fail-closed (`serving_config_unavailable`, `explainer_unavailable`, `registry_unavailable`, BR-U0-02), que es observable y queda en el registro y en las métricas. **Criterio**: una dependencia entra en la readiness solo si su caída **no** tiene una causa tipificada de fail-closed.
- Resultados de los checks cacheados 5 s; probes de arranque para KServe y Keycloak.
- **Precisión sobre un requisito aprobado**: NFR-RES-07 («readiness profunda (BD, KServe, explainability)») queda acotado a las dependencias propias. Esto evita que una caída de explainability saque a scoring del balanceo en cascada y cambie un `FailClosed` tipificado por errores de conexión. Se anota en `requirements.md`.
- **US-610**: su escenario original («la BD no responde → la readiness de scoring-service falla») contradecía este criterio, porque scoring no tiene base propia. Se ajustó en `stories.md` (2026-10-03) con dos escenarios: `case-db` caída → case-service no listo; explainability o governance caídos → scoring sigue listo y responde con un `FailClosed` tipificado.
- **Verificación**: pruebas en kind:
  - `case-db` caída → case-service no listo (lo mismo para governance y el registro con sus bases);
  - explainability caído → scoring sigue listo y responde `FailClosed(explainer_unavailable)`;
  - governance caído → scoring sigue listo y responde `FailClosed(serving_config_unavailable)`.
- **Satisface**: NFR-RES-07 (precisado); RESILIENCY-06; NFR-U1-32.

### P-U1-05 — Simulacro de restore semanal (Q6)
- `CronJob restore-drill` (semanal) en el namespace aislado `vectra-restore-drill`, cuyas NetworkPolicies solo permiten leer del almacenamiento de backups (F75) y empujar métricas al Pushgateway (F87):
  1. crea un `Cluster` efímero de CloudNativePG desde el último backup base + WAL;
  2. corre `verify_chain` (CLI de U3) sobre la copia de `registry-db`;
  3. empuja al Pushgateway `vectra_restore_drill_success` (0/1), `vectra_restore_drill_duration_seconds` y el LSN alcanzado; Prometheus las lee por F88;
  4. destruye el cluster efímero.
- Alertas: `RestoreDrillFailed` (SEV1) y `RestoreDrillMissing` (SEV1 si `push_time_seconds` de una corrida exitosa tiene más de 8 días).
- **Sidecar nativo de Linkerd**: los pods del namespace están mallados (mTLS para F87). Con el proxy como contenedor normal, un Job nunca termina: el proxy sigue vivo después de que el contenedor principal sale, el Job no llega a `Complete` y el simulacro no reporta éxito.
  - El namespace `vectra-restore-drill` lleva la anotación `config.alpha.linkerd.io/proxy-enable-native-sidecar: "true"`, y el pod template del CronJob también, por si la herencia no aplica.
  - Con esa anotación, el proxy se inyecta como *init container* con `restartPolicy: Always` (sidecar nativo de Kubernetes). Kubernetes lo detiene cuando termina el contenedor principal, y lo arranca antes que él, así que el push a F87 ya tiene red mallada desde el inicio.
  - Cubre también los pods de Job que CloudNativePG crea para el bootstrap por recuperación del cluster efímero.
  - Requisitos: Kubernetes ≥ 1.29 (sidecars nativos habilitados por defecto), ya cubierto por NFR-U1 Q1 (≥ 1.30), y una versión de Linkerd que soporte la anotación, que se fija en `Chart.lock`.
- **Verificación**:
  - ejecución manual del CronJob en kind (`kubectl create job --from=cronjob/restore-drill`) con la salida de `verify_chain` «íntegra»;
  - el Job llega a `Complete` dentro del tiempo esperado (`kubectl wait --for=condition=complete job/<nombre> --timeout=…`);
  - `kubectl get pod -o jsonpath='{.spec.initContainers[?(@.name=="linkerd-proxy")].restartPolicy}'` devuelve `Always`.
- **Satisface**: NFR-U1-06, 07; RESILIENCY-12, 13; US-608.

### P-U1-06 — Controladores críticos en HA (Q9)

| Controlador | Réplicas | Reparto | Notas |
|---|---|---|---|
| Kyverno (admission controller) | 3 | por zona + PDB | `failurePolicy: Fail`; excluye `kube-system`, `kyverno` y `linkerd` del webhook para poder recuperarse |
| Linkerd (plano de control) | modo HA (3) | por zona + PDB | El proxy-injector también excluye su propio namespace |
| cert-manager (+ webhook) | 2 | por zona + PDB | — |
| CloudNativePG (operador) | 2 | por zona | — |
| Argo CD | 1 | — | No es crítico en un failover: los cambios son manuales |

- Alerta SEV1 si Kyverno o el plano de control de Linkerd no tienen réplicas listas.
- **Verificación**: escenario de fallo de zona en kind (NFR-U1-03) → los pods nuevos se admiten y se inyectan.
- **Satisface**: NFR-U1-08, 25; RESILIENCY-08.

### P-U1-07 — Latido del sistema de alertas (Q11)
- La alerta `Watchdog` está siempre activa y Alertmanager la envía cada 5 min por F72 a un receptor de latido del banco. Si deja de llegar, la observabilidad está caída.
- Alertas sobre Prometheus (scrape fallido, reglas que fallan), Loki (ingesta) y Alertmanager (notificaciones fallidas).
- **Verificación**: `promtool test rules`; en kind, el receptor de prueba recibe el latido.
- **Satisface**: RESILIENCY-05, 07; NFR-U1-32.

## 3. Escalabilidad y rendimiento

### P-U1-08 — Conexiones directas con pools acotados (Q7)
- Sin PgBouncer. Cada réplica abre como máximo 5 conexiones a su base.
- `max_connections = (réplicas máximas del HPA × 5) + 20 %` de margen + conexiones del operador y de los backups. Se calcula en Infrastructure Design con los máximos de NFR-U1-12.
- Alerta si las conexiones superan el 80 % de `max_connections`.
- **Verificación**: prueba de carga (NFR-U1-11) sin errores `too many connections`; regla de alerta probada con `promtool`.

### P-U1-09 — PriorityClasses (Q8)

| PriorityClass | Valor | Cargas | Preemptible |
|---|---|---|---|
| `vectra-critical` | 1 000 000 | PostgreSQL, decision-registry-service, Linkerd, Kyverno, CloudNativePG | No |
| `vectra-high` | 100 000 | scoring, explainability, case, governance, Keycloak, gateway, KServe | No |
| `vectra-normal` | 10 000 | BFF, bias, product-metrics, observabilidad | No |
| `vectra-low` | 100 | channel-simulator, jobs batch, `restore-drill` | Sí |

- Una política de Kyverno exige `priorityClassName` en todo Pod de Vectra.
- **Verificación**: `kyverno test`; prueba en kind con nodos saturados → se desalojan primero las cargas `vectra-low`.
- **Satisface**: RESILIENCY-09; NFR-U1-13.

## 4. Operación

### P-U1-10 — Severidades, runbooks y COE (Q4, R9)

| Severidad | Ejemplos | Respuesta |
|---|---|---|
| SEV1 | Ruta de recomendación caída; `registry-db` sin escrituras; cadena de hashes rota; WAL o backup vencido; restore drill fallido; Kyverno o Linkerd sin réplicas | 15 min en horario operativo |
| SEV2 | Una zona caída; réplica rezagada; `FailClosedPersistente`; certificado a menos de 7 días; fallos de authn/authz repetidos; burn rate rápido | 1 h |
| SEV3 | Lo demás | Siguiente día hábil |

- Alertmanager enruta por la etiqueta `severity` a F72. Toda regla tiene `severity` y `runbook_url`.
- Plantilla de runbook en `platform/runbooks/_template.md`: síntoma, impacto, diagnóstico, mitigación, escalamiento y verificación.
- **COE** obligatorio en 5 días hábiles para SEV1 y SEV2. Plantilla en `platform/runbooks/coe-template.md`, con acciones de seguimiento en issues etiquetados `coe-action`.
- **Verificación**: un test verifica que cada regla tiene `severity` válida y un `runbook_url` que apunta a un archivo existente (US-610).
- **Satisface**: RESILIENCY-15; NFR-RES-15; NFR-U1-32.

### P-U1-11 — SLO con dos indicadores (Q5)
- **SLI de disponibilidad**: proporción de requests a `POST /v1/recommendations` con una respuesta 200 tipificada (`Recommendation` o `FailClosed`) dentro del timeout. **SLO 99,5 %** mensual en horario operativo.
- **SLI de recomendación usable**: `Recommendation` / total. Sin SLO; dashboard y alerta `FailClosedPersistente` (SEV2).
- Alertas de **burn rate en dos ventanas**: rápida (1 h y 5 min, factor 14,4) → SEV2; lenta (6 h y 30 min, factor 6) → SEV3.
- Reglas de grabación (`recording rules`) en Prometheus sobre las métricas HTTP del middleware de U0.
- **Verificación**: `promtool test rules` con series sintéticas que disparan cada ventana.
- **Satisface**: RESILIENCY-02, 05; NFR-RES-02.

## 5. Estructura GitOps

### P-U1-12 — App-of-apps por entorno con sync waves (Q10)
- Repositorio `vectra-risk-gitops`: `apps/{kind,staging,prod}/root.yaml`, una `Application` por componente y values por entorno en `envs/{env}/`.
- Sync waves:

| Wave | Contenido |
|---|---|
| 0 | CRDs y operadores (CloudNativePG, cert-manager, ESO, Kyverno, Linkerd CRDs) |
| 1 | Políticas de Kyverno y plano de control de Linkerd; PriorityClasses; namespaces y NetworkPolicies |
| 2 | Datos: clusters de PostgreSQL, MinIO (kind) |
| 3 | Identidad: Keycloak |
| 4 | Observabilidad |
| 5 | Servicios de Vectra |
| 6 | InferenceServices |

- Toda `Application` sin `syncPolicy.automated` (NFR-U1-43). El aprobador sincroniza la raíz en orden.
- **Verificación**: test de política sobre los manifiestos de las Applications (sin auto-sync, con anotación de wave); `argocd app diff` en kind adjunto al PR.
- **Satisface**: NFR-U1-43; RESILIENCY-03, 04; AUTONOMIA-01; US-607.

## 6. Cumplimiento de extensiones (NFR Design U1)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | P-U1-09, P-U1-11 |
| RESILIENCY-03 / 04 | Cumple | P-U1-12 |
| RESILIENCY-05 / 06 / 07 | Cumple | P-U1-04, 07, 10, 11 |
| RESILIENCY-08 | Cumple | P-U1-06 |
| RESILIENCY-09 | Cumple | P-U1-08, 09 |
| RESILIENCY-10 | N/A en U1 | De los servicios |
| RESILIENCY-11 / 12 / 13 | Cumple | P-U1-05 |
| RESILIENCY-14 | Cumple | Decisión del proyecto = C; escenarios de NFR-U1-03 y 07 y P-U1-05 |
| RESILIENCY-15 | Cumple | P-U1-10 |
| SECURITY-01 | Cumple | P-U1-03 |
| SECURITY-06 / 07 / 08 | Cumple | P-U1-01, 02 |
| SECURITY-14 | Cumple | P-U1-10 (alertas de authn/authz SEV2) |
| AUTONOMIA-01 | Cumple | P-U1-12 (sync manual); verificaciones solo en kind |
| AUTONOMIA-05 | Cumple | P-U1-01 (egress solo por inventario) |
