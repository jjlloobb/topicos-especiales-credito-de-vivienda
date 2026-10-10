# Entidades de dominio — U12 `system-verification`

U12 no tiene datos persistentes en el clúster. Sus entidades son configuraciones de
escenarios, informes de corrida y evidencias versionadas en el PR.

---

## 1. Configuración

| Tipo | Campos |
|---|---|
| `SimulatorScenario` | `name` (`normal`, `stratified`, `rt1`, `rt4`), `volume`, `rate` (≤ 30/s), `seed`, `strata?` (para `stratified`: `min_per_cell = 30`, atributos `region` y `estrato`) |
| `DecisionMix` | `p_view` (probabilidad de abrir la explicación), `p_sigue`, `p_se_aparta`, `p_resuelve_revision` (solo con `revision_requerida`), `p_factors` (marcar factores frente a «Ninguno»), `seed` |
| `LoadProfile` | `intake_rate` (20/s), `console_users` (200, perfil de U10), `duration` (30 min), `baseline_rate` (5/s), `scale` (1 o 0,5) |

## 2. Informes de corrida

| Tipo | Campos |
|---|---|
| `RunReport` (simulador) | `scenario`, `sent`, `accepted`, `rejected_by_code`, `case_ids`, `started_at`, `finished_at` |
| `DriverReport` (conductor) | `cases_seen`, `decisions_by_kind`, `views`, `conflicts_409`, `invalid_422`, `started_at`, `finished_at` |
| `Rt2Measurement` | `run` (1..5), `batch_first_recorded_at` (el menor `recorded_at` de las `recommendation` del lote; Infrastructure Design de U12, 2026-10-10), `freeze_recorded_at`, `latency_seconds`, `passed` (≤ 1 800 s) |

Ningún informe contiene datos del solicitante: solo `case_id` y conteos.

## 3. Evidencia e informe

| Tipo | Campos |
|---|---|
| `Evidence` | `id` (`RT-1`…`RT-5`, `X01`…`X10`, `US-609`, demos), `command`, `output` (archivo), `expected`, `obtained`, `result` (`pasa` \| `falla`), `commit`, `images: {nombre: digest}`, `executed_at`, `operator` |
| `VerificationReport` | Una fila por elemento verificable: `id`, `result` (`pasa` \| `falla` \| `no ejecutado`), `evidence?`, `commit`, `images`, `date` |

Reglas del informe (BR-U12-11): sin `Evidence` → `no ejecutado`; `expected ≠ obtained` → `falla`,
aunque `result` diga otra cosa.

## 4. Elementos verificables

| Grupo | Elementos |
|---|---|
| RT | RT-1, RT-2, RT-3, RT-4, RT-5 |
| Negativas | X01–X10 |
| Historias | US-101, 106, 109, 111, 303, 305, 603, 604, 609 |
| Demos | `journey-7-3`, `journey-7-4`, `rt-5`, `dashboard` |
| Mediciones | Tamaño por caso (INF-U8-08), latencia de RT-2 |

### 4.1 Identificadores de evidencia (revisión del FD de U12, 2026-10-10)

Además de RT-1..5, X01–X10 y las cuatro demos, el generador reconoce estas evidencias:

| Id | Qué prueba | Regla |
|---|---|---|
| `SIM-NORMAL` | La corrida `normal` del simulador: `accepted = sent`, un caso por solicitud aceptada y cada caso llega a `listo` o a un estado de fail-closed documentado | BR-U12-02 |
| `RT2-LATENCY` | Las 5 corridas de latencia de RT-2, con su máximo ≤ 30 min | BR-U12-07 |
| `LOGS-NO-PII` | Durante las corridas, Loki no contiene ningún identificador ni nombre de las solicitudes enviadas (prefijo `SYN-` y el catálogo ficticio de U5) | BR-U12-12 |
| `LOAD` | La prueba de carga con su línea base | BR-U12-08 |
| `CASE-SIZE` | La medición del tamaño por caso | BR-U12-06 |

### 4.2 Mapa historia → evidencias (revisión del FD de U12, 2026-10-10)

| Historia | Evidencias requeridas |
|---|---|
| US-101 (ingesta desde el simulador) | `SIM-NORMAL` |
| US-106 (marca de baja confianza) | `RT-4` |
| US-109 (texto libre como dato) | `RT-1` |
| US-111 (fail-closed por desincronía) | `RT-3`, `journey-7-3` |
| US-303 (congelamiento automático) | `RT-2`, `RT2-LATENCY`, `journey-7-4` |
| US-305 (resolución humana del congelado) | `journey-7-4` (paso de resolución por cumplimiento con MFA), `X03` (nadie más saca de `congelado`) |
| US-603 (sin escritura al estado de crédito) | `RT-5`, `X01`, `rt-5` |
| US-604 (egress denegado y logs sin PII) | `X02`, `LOGS-NO-PII` |
| US-609 (autoscaling con carga simulada) | `LOAD` |

**Regla del generador** (complementa BR-U12-11): una historia
- **`pasa`** si y solo si **todas** sus evidencias requeridas salen `pasa`;
- **`falla`** si alguna sale `falla`;
- **`no ejecutado`** si ninguna sale `falla` pero falta alguna (aunque las demás pasen).

El mapa vive en `system-verification/report/story-map.yaml` y el generador falla si una historia
de §4 no tiene fila o si una evidencia del mapa no es un identificador conocido.
