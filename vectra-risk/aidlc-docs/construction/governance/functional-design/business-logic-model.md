# Modelo de lógica — U4 `governance`

## 1. Módulos lógicos

| Módulo | Responsabilidad | Reglas |
|---|---|---|
| `model_fsm` | Función pura `transition(state, action, actor, context) -> new_state \| Error` con la tabla de BR-U4-01 | BR-U4-01..04, 10 |
| `registration` | Validación de formato por extensión y bytes mágicos, y checksum, sin deserializar | BR-U4-06 |
| `validation` | Lanzar el Job (K01), recibir el informe, aplicar plazo y bloqueo | BR-U4-05, 07 |
| `promotion` | `mark_active` y `promotion-tool` (PR de un commit) | BR-U4-08, 09 |
| `policy` | Propuesta, aprobación de cuatro ojos, activación, `normative_at` | BR-U4-10..12 |
| `data_sources` | Ciclo de fuentes con `compare_source` | BR-U4-13 |
| `serving_config` | Recalcular y servir con `etag` / `If-None-Match` | BR-U4-14 |
| `evidence` | Transiciones en dos fases con el registro, reconciliador y excepción de `freeze` | BR-U4-15, 17 |
| `promotion-tool` (CLI) | `list_promotable`, `create_promotion_pr`, `mark_active` (token de usuario con MFA, F08) | BR-U4-08, 09 |
| `model-validation-job` | AUC-ROC, disparidad inicial (librería de U9), prueba de sincronía | BR-U4-07 |

`model_fsm`, `normative_at` y el cálculo del `etag` son puros y se prueban con propiedades.

## 2. Flujos

### 2.1 Transición con evidencia (BR-U4-17)

```text
acción (actor, versión, transición)
  -> U0: authn, rol o scope, MFA + auth_time <= 15 min
  -> model_fsm.transition(...)  -> 403 / 409 si no está permitida
  -> TX1: INSERT model_transitions(status=pendiente_registro)   (sin efecto)
  -> registry.append(evento, idempotency_key=transition_id)
       falla -> 503 ; la transición queda pendiente (reconciliador)
  -> TX2: status=confirmada ; aplicar estado ; recalcular serving-config (etag)
```

### 2.2 Congelamiento (excepción)

```text
bias-monitoring (governance:freeze) -> freeze(mv_id, contexto)
  -> model_fsm: activo -> congelado (solo esta identidad)
  -> TX única: estado=congelado ; serving-config recalculado ; transición pendiente_registro
  -> registry.append(freeze) ; falla -> FreezeEventPending, reintento del reconciliador
  -> réplicas de governance convergen en <= 1 s ; scoring ve el etag nuevo en <= 6 s -> FailClosed(model_frozen)
```

### 2.3 Promoción y rollback

```text
cro aprueba (MFA, ≠ registered_by) -> aprobado
humano: promotion-tool create_promotion_pr -> PR de 1 commit (predictor + explainer + evidencia)
humanos: revisión, merge y sync manual en Argo CD
ingeniero: promotion-tool mark_active (MFA, F08) -> nueva=activo, anterior=inactivo, etag nuevo
   si KServe aún no sirve la nueva -> scoring: version_mismatch (fail-closed) ; alerta a los 10 min
rollback: PR de revert + sync manual + mark_active(versión inactivo)
```

### 2.4 Validación

```text
start_validation -> Job en vectra-staging (K01), deadline 2 h
Job -> PUT /v1/models/{id}/validation-report (F32)
   sync_check.passed ? -> lista_para_aprobacion : validacion_fallida
   AUC y disparidad -> se informan con sus umbrales (no bloquean)
sin informe a las 2 h -> validacion_fallida (timeout)
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U4-01 | `model_fsm` | **Stateful (PBT-06)**: para toda secuencia de acciones con actores arbitrarios (incluidos bias, jobs, CRO y cumplimiento con y sin MFA), se cumplen siempre: a lo sumo una versión `activo` o `congelado`; `congelado → activo` solo ocurre con `cumplimiento` + MFA + `reactivar`; bias nunca produce un estado distinto de `congelado`; los estados terminales no cambian | Stateful (máquina contra un modelo de referencia) | Secuencias de acciones × actores × estados de MFA |
| PBT-U4-02 | `model_fsm` | `transition` coincide con la tabla de BR-U4-01 para toda combinación (estado, acción, actor) | Oráculo | Producto completo de estados × acciones × actores |
| PBT-U4-03 | `policy` | `normative_at(p, d)` devuelve el único parámetro vigente en `d`, o nulo, para toda lista sin solapes y toda fecha; y la validación rechaza toda lista con solapes | Oráculo + invariante | Listas de vigencias con huecos, bordes y solapes |
| PBT-U4-04 | `policy` | Cuatro ojos: aprobar ⇔ `approved_by ≠ proposed_by` y rol `cro` con MFA | Oráculo | Pares de usuarios y roles |
| PBT-U4-05 | `serving_config` | `etag(a) == etag(b)` ⇔ el contenido canónico (sin `bias_monitoring_age_s`) de `a` y `b` es igual | Invariante | Pares de configuraciones que difieren en un campo o en nada |
| PBT-U4-06 | `registration` | Para todos los bytes generados: un archivo con bytes mágicos de `pickle`/`joblib` se rechaza con cualquier extensión, y un checksum distinto se rechaza siempre; ningún camino llama a un deserializador | Invariante | Bytes aleatorios con y sin cabeceras de pickle/zip/ONNX |
| PBT-U4-07 | `evidence` | Para toda secuencia de fallos del registro, ninguna transición distinta de `freeze` cambia el estado sin un `registry_entry_id`; los reintentos nunca crean dos eventos (misma `idempotency_key`) | Invariante (stateful) | Secuencias de acciones con el registro caído o lento al azar |

**Pruebas de ejemplo obligatorias (PBT-10):**
- registro válido → `registrado`; checksum alterado → rechazo sin deserializar (US-201);
- validación con sincronía fallida → `validacion_fallida` (US-202);
- `cro` aprueba → 200 y evento; `ingeniero_riesgo` aprueba → 403 (US-203);
- `promotion-tool` genera un PR de un commit con la evidencia; sin sync automático (US-204);
- política P2 propuesta mientras P1 sigue activa; scoring intenta escribir política → denegado (US-205);
- aprobación de P2 por otro CRO → P2 activa, P1 histórica, nuevas recomendaciones con P2 (US-206);
- rollback: `mark_active` de M1 `inactivo` → M1 activo, M2 inactivo (US-208);
- cumplimiento reactiva con justificación; CRO, job o webhook → denegado (US-305);
- el script de CI no encuentra rutas `congelado → activo` fuera del endpoint de cumplimiento;
- vigencia normativa vencida → `normative_current` nulo (la consecuencia en scoring, `revision_requerida` con `parametro_normativo_no_vigente`, la prueba U7).

## 4. Cumplimiento de extensiones (Functional Design U4)

Revisada contra el cuerpo de los tres artefactos antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | BR-U4-09 (promoción por PR, sin sync ni apply) |
| AUTONOMIA-03 | N/A en U4 | Governance no tiene flujo ni scope hacia core-banking-mock (F17 y `core:read-credit` son solo de case-service); este FD no agrega ninguno |
| AUTONOMIA-04 | Cumple | BR-U4-01, 03 (solo cumplimiento saca de `congelado`; script de CI); PBT-U4-01 |
| AUTONOMIA-06 | Cumple | BR-U4-08 (promoción incompleta → `version_mismatch`), BR-U4-11 (`normative_current` nulo cuando no hay vigencia; scoring lo convierte en revisión humana obligatoria, U7) |
| SECURITY-05 | Cumple | BR-U4-06 (formato y checksum), BR-U4-13 (fuentes no aprobadas → 422) |
| SECURITY-08 | Cumple | BR-U4-01, 04, 10, 12 (transiciones por actor, cuatro ojos, sin escritura de servicios) |
| SECURITY-11 | Cumple | Casos de abuso de la lógica de negocio con prueba: BR-U4-03 (script de CI que falla si existe otra ruta `congelado → activo` fuera del endpoint de cumplimiento), BR-U4-04 (bias solo congela, X04) y BR-U4-10 (cuatro ojos). Defensa en profundidad: en BR-U4-03, la restricción del endpoint (rol, MFA, step-up) más el script. Lógica crítica aislada en `model_fsm`, una función pura (§1). El rate limiting de los endpoints públicos es del gateway (U2) |
| SECURITY-13 | Cumple | BR-U4-06 (sin deserializar; sin pickle/joblib), BR-U4-17 (cambios críticos auditables) |
| SECURITY-14 | Cumple | Alertas de §9 |
| SECURITY-15 | Cumple | BR-U4-17 (sin evidencia, sin efecto); BR-U4-15 (congelar es inmediato) |
| RESILIENCY-05 / 07 / 15 | Cumple | Alertas con severidad de §9, dentro del proceso de U1 |
| PBT-01 | Cumple | §3 |
| PBT-06 | Cumple | PBT-U4-01, 07 |
| PBT-07 | Cumple | Columna «Generadores» de §3 |
| PBT-10 | Cumple | Pruebas de ejemplo de §3 |
