# Requisitos no funcionales — U3 `decision-registry`

Decisiones del plan (`decision-registry-nfr-requirements-plan.md`, Q1–Q6 = A). Las
verificaciones «en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01);
las demás corren en CI.

Los IDs `NFR-U3-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Retención y protección de datos (Q1; BR-U0-95)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U3-01 | **Retención de 10 años** de las entradas del registro desde la fecha de la decisión (Código de Comercio art. 60, Ley 962 de 2005 art. 28). **[VERIFICAR con cumplimiento y con la normativa de la Superintendencia Financiera]** | Parámetro `retention_years = 10` documentado en `decision-registry/docs/retention.md` con la referencia normativa y la firma de cumplimiento pendiente |
| NFR-U3-02 | **Sin supresión en el registro**: ante una solicitud de habeas data, las entradas no se borran, porque la base legal es la obligación de conservación **[VERIFICAR]**. La respuesta al titular la gestiona el banco con ese fundamento | Procedimiento en `docs/retention.md`; una prueba confirma que no existe ningún endpoint ni rol que borre entradas (BR-U3-01, 02) |
| NFR-U3-03 | **Pérdida de la re-identificación al vencer la retención de case-db**: U8 elimina los identificadores directos del caso en case-db; desde entonces, las entradas del registro ya no se pueden volver a unir con una persona. U3 no participa en esa eliminación | Dependencia registrada para el Functional Design de U8 |
| NFR-U3-04 | **Archivo de largo plazo**: un export **mensual** de los segmentos de la cadena (entradas en bytes canónicos + checkpoints) a un bucket WORM con object lock de **10 años**, firmado con la llave de checkpoints, independiente de los backups de 12 meses de U1. El export se verifica con la CLI antes de cerrar el mes | Job mensual con `vectra-registry verify --source archive` sobre el export → `exit 0`; alerta `ArchiveExportFailed` (SEV2) |

## 2. Disponibilidad y recuperación

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U3-10 | Criticidad **Critical**. Hereda de U1: RPO 0 ante fallo de zona, RPO ≤ 5 min ante pérdida del sitio, RTO ≤ 4 h, PITR de 30 días y simulacro de restore semanal con `verify_chain` | Referencia a NFR-U1-02..07 y P-U1-05 |
| NFR-U3-11 | ≥ 2 réplicas del servicio repartidas por zona, PDB y HPA; readiness = `registry-db` con escritura posible (réplica síncrona disponible), según P-U1-04 | `helm template` + `conftest` |
| NFR-U3-12 | Si la bóveda no responde, los appends siguen; solo se atrasa el checkpoint (`CheckpointMissing` SEV2 tras 2 h) | Prueba de integración con un doble de la bóveda caído |

## 3. Rendimiento (Q2)

### 3.1 Dos cifras distintas: volumen esperado y capacidad de diseño

NFR-U3-20 (50 entradas/s) y NFR-U3-30 (~10 000 entradas/día) no se contradicen, pero miden
cosas distintas, y el documento no lo decía:

| Cifra | Qué es | De dónde sale | Para qué se usa |
|---|---|---|---|
| **Volumen esperado** | Lo que el banco procesará en la operación normal | ~2 000 solicitudes/día (banco mediano) × ~5 entradas por solicitud | Almacenamiento y crecimiento (§4) |
| **Capacidad de diseño** | El pico que el registro debe absorber sin degradarse | Pico de U1 (10 solicitudes/s, NFR-U1-10) × ≤ 2 entradas síncronas por solicitud = 20 entradas/s, con margen de 2,5× | Rendimiento (NFR-U3-20, 22) |

- **Entradas por solicitud (volumen esperado):** 1 `recommendation`, ~0,5 `fail_closed` (reintentos), ~2 `explanation_view`, 1 `human_decision` y ~0,5 de gobierno y checkpoints repartidos ≈ 5.
- **Entradas síncronas por solicitud (capacidad):** en la ruta de recomendación solo hay 1 `recommendation`, o 1 `fail_closed` en un reintento; las de case-service (`human_decision`, `explanation_view`) llegan al ritmo humano y no suman al pico.
- Los «2 solicitudes/s sostenidas» de NFR-U1-10 son **capacidad**, no volumen esperado. Si el banco los sostuviera todo el día (~170 000 solicitudes/día, unas 86 veces el volumen esperado), el almacenamiento crecería a ~1,3 TB/año. Eso **no** es un objetivo de diseño; lo vigila NFR-U3-34.

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U3-20 | **Append**: p95 ≤ 50 ms y p99 ≤ 200 ms, sostenido a **50 entradas/s** (capacidad de diseño: 2,5× el pico de 20 entradas síncronas/s de §3.1), con réplica síncrona en otra zona | Prueba de carga en kind (operador), con el reporte adjunto al PR |
| NFR-U3-21 | **Expediente**: p95 ≤ 2 s para un caso típico (≤ 20 entradas), incluida la verificación `range` | Misma prueba |
| NFR-U3-22 | **Verificación incremental** de 15 min de entradas: ≤ 30 s | Benchmark en CI con Testcontainers y 50 entradas/s × 15 min sintéticas |
| NFR-U3-23 | **Verificación `nightly`**: ≤ 30 min con 10 años de datos simulados (36 M entradas) | Benchmark en kind con datos sintéticos generados (operador) |

## 4. Escalabilidad y almacenamiento (Q3, Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U3-30 | **Volumen esperado** (§3.1): ~10 000 entradas/día, ~3,6 M/año, ~15 GB/año (~40 MB/día, dominado por las `recommendation` de ~20 KB), ~150 GB a 10 años. Es la base del dimensionamiento del almacenamiento; la capacidad de diseño de NFR-U3-20 **no** se usa para dimensionar disco | `docs/capacity.md`, con las dos cifras y su derivación |
| NFR-U3-31 | **Particionado declarativo por rango de `seq`**, una partición por año, creada por migración **antes** de necesitarla (alerta si la partición siguiente no existe 30 días antes) | Prueba de migración con Testcontainers; alerta `RegistryPartitionMissing` (SEV2) probada con `promtool` |
| NFR-U3-32 | Expansión del volumen cuando llega al 70 %; alerta de proyección de llenado a 90 días (`predict_linear`) | Regla `RegistryVolumeFillForecast` probada con `promtool` |
| NFR-U3-33 | Verificación en dos niveles: `nightly` (cadena de checkpoints + 7 días + muestra del 1 %) y `full` mensual (BR-U3-11, precisado por Q4) | Pruebas de la CLI por modo; PBT-U3-03 garantiza que la reescritura se detecta con los checkpoints |
| NFR-U3-34 | **Crecimiento por encima del volumen esperado**: si las entradas diarias superan 3× el volumen esperado durante 7 días seguidos, alerta `RegistryGrowthAboveForecast` (SEV3) para rehacer el pronóstico de capacidad (particiones, volumen y verificación `nightly`) | Regla probada con `promtool` con series sintéticas |

## 5. Seguridad

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-40 | **La llave de checkpoints nunca sale de la bóveda**: la firma la hace el motor de la bóveda (Vault Transit en kind; la bóveda o el HSM del banco en prod) | Q5, SECURITY-12, 13 | Prueba de que ningún Secret ni variable del pod contiene la llave privada; la firma se verifica con la llave pública |
| NFR-U3-41 | Un **egress** nuevo del registro hacia la bóveda del banco en producción (y un flujo in-cluster hacia Vault en kind). Sin datos de solicitantes: solo el digest a firmar | Q5, AUTONOMIA-05 | Flujo en `flows.yaml`; prueba de que la solicitud a la bóveda solo contiene `{checkpoint_seq, checkpoint_hash, recorded_at}` |
| NFR-U3-42 | Roles de base de mínimo privilegio (`registry_app`, `registry_verifier`, `registry_migrator`) con contraseñas desde ESO y TLS `verify-full` | SECURITY-06, 01 | Prueba SQL de permisos (US-401) |
| NFR-U3-43 | El verificador con MFA bajo demanda: una sola verificación `full` a la vez (las solicitudes concurrentes reciben `409 conflict_state`) | SECURITY-11 | Prueba de integración |

## 6. Pruebas (Q6, PBT-09)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U3-50 | psycopg 3 async; integración contra PostgreSQL real con **Testcontainers** en CI (sin clúster) | `uv run pytest decision-registry/tests/integration` |
| NFR-U3-51 | PBT-U3-01 con `RuleBasedStateMachine` de Hypothesis contra la base de Testcontainers; PBT-U3-02..08 con el perfil `ci` (500 ejemplos, semilla impresa) | `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property` |
| NFR-U3-52 | Cobertura de ramas ≥ 95 % y **100 %** en `chain`, `verify` y `append`; mutation testing en `chain` y `verify` (como U0) | `pytest --cov --cov-branch` + `mutmut` |

## 7. Cumplimiento de extensiones (NFR Requirements U3)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | NFR-U3-10 (Critical; RPO y RTO heredados de U1) |
| RESILIENCY-05 / 07 / 15 | Cumple | Alertas `ArchiveExportFailed`, `CheckpointMissing`, `RegistryPartitionMissing`, `RegistryVolumeFillForecast` y `RegistryGrowthAboveForecast` (NFR-U3-04, 12, 31, 32, 34), con el proceso de U1 |
| RESILIENCY-06 | Cumple | NFR-U3-11 (readiness = escritura posible) |
| RESILIENCY-08 / 09 | Cumple | NFR-U3-11, 20, 30..32, 34 (capacidad de diseño y volumen esperado separados en §3.1) |
| RESILIENCY-10 | Cumple | NFR-U3-12 (la caída de la bóveda no detiene los appends) |
| RESILIENCY-11 / 12 | Cumple | NFR-U3-04 (archivo de 10 años), NFR-U3-10 (backups de U1) |
| SECURITY-01 | Cumple | NFR-U3-42 (TLS `verify-full`) |
| SECURITY-06 | Cumple | NFR-U3-42 |
| SECURITY-11 | Cumple | NFR-U3-43 |
| SECURITY-12 / 13 | Cumple | NFR-U3-40, 04 (export firmado y verificado) |
| SECURITY-14 | Cumple | Alertas nombradas con severidad: `ArchiveExportFailed` (NFR-U3-04), `CheckpointMissing` (NFR-U3-12), `RegistryPartitionMissing` (NFR-U3-31), `RegistryVolumeFillForecast` (NFR-U3-32) y `RegistryGrowthAboveForecast` (NFR-U3-34) |
| SECURITY-15 | Cumple | NFR-U3-12: si la bóveda no responde, los appends siguen y solo se atrasa el checkpoint; se degrada sin detener la escritura de evidencia |
| PBT-06 / 08 / 09 | Cumple | NFR-U3-51 (stateful; semilla; Hypothesis) |
| AUTONOMIA-01 / 02 | Cumple | Verificaciones estáticas en CI, en kind por el operador; cada requisito con su verificación |
| AUTONOMIA-05 | Cumple | NFR-U3-41 (el egress hacia la bóveda solo lleva el digest) |

## 8. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio |
|---|---|
| U3 FD BR-U3-11, domain-entities §2.1 y §5–6, business-logic-model `cli` | Modo `nightly` y `full` mensual (Q4); firma por la bóveda (Q5) |
| U3 FD BR-U3-08 | La bóveda firma; si no responde, el checkpoint se atrasa |
| U0 domain-entities §5.4 y BR-U0-95 | Remiten a la decisión de NFR-U3-01..04 |
| U8 (pendiente) | NFR-U3-03: eliminar los identificadores de case-db al vencer su retención |
| U3 Infrastructure Design (pendiente) | Bucket WORM de 10 años, bucket de checkpoints y flujo hacia la bóveda |
