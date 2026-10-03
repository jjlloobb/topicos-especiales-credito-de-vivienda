# Plan de NFR Requirements — U3 `decision-registry`

**Alcance:** requisitos no funcionales y stack del único componente Critical, sobre el
Functional Design aprobado (BR-U3-01..16). Incluye la decisión pendiente desde U0
(domain-entities §5.4, BR-U0-95): retención y supresión frente a la Ley 1581 de 2012.

**Ya decidido** (no se pregunta):
- Python 3.12 + FastAPI + Pydantic v2 + `vectra_common` (U0);
- `registry-db` en CloudNativePG con 3 instancias, réplica síncrona y WAL cada 60 s (U1);
- RPO 0 ante fallo de zona y ≤ 5 min ante pérdida del sitio; RTO ≤ 4 h (U1);
- backups con PITR de 30 días y mensuales retenidos 12 meses, con object lock (U1, NFR-U1-06);
- Hypothesis para PBT (U0); readiness = su base (P-U1-04).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Retención, supresión y Ley 1581 (Compliance)
El registro guarda datos **seudonimizados** e inmutables. Los backups de U1 se retienen
como máximo 12 meses, pero la evidencia de una decisión de crédito suele exigirse por años.

A) **Retención de 10 años** de las entradas del registro desde la fecha de la decisión. Es la referencia para la conservación de documentos comerciales en Colombia (Código de Comercio art. 60, Ley 962 de 2005 art. 28) **[VERIFICAR con cumplimiento y con la normativa de la Superintendencia Financiera]**.
   - **Supresión (habeas data)**: las entradas del registro **no** se borran, porque la base legal es una obligación legal de conservación **[VERIFICAR]**.
   - Al vencer la retención de case-db, los identificadores directos del caso se eliminan allí (lo diseña U8). A partir de ese momento las entradas del registro ya no se pueden volver a unir con una persona.
   - **Archivo de largo plazo**: un export mensual firmado de los segmentos de la cadena (entradas + checkpoints) a un bucket WORM con retención de 10 años, independiente de los backups de 12 meses de U1.

   (Recomendado)

B) **Crypto-shredding**: cifrar `feature_vector` y `monitoring_labels` con una llave por caso, para que «suprimir» sea destruir la llave sin romper la cadena (es la opción B que se descartó en U0 Q7)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Objetivos de rendimiento (Performance)
El append está en la ruta de cada recomendación y espera la réplica síncrona en otra zona.

A)
   - **Append**: p95 ≤ 50 ms y p99 ≤ 200 ms, sostenido a **50 entradas/s** (unas 10 veces el pico de diseño de U1, contando recomendaciones, decisiones, consultas de explicación y eventos).
   - **Expediente**: p95 ≤ 2 s.
   - **Verificación incremental** (15 min de entradas): ≤ 30 s.

   Se miden con una prueba de carga en kind que ejecuta el operador (recomendado)

B) Sin objetivos propios: solo el SLO de la ruta de recomendación (U1)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Crecimiento a 10 años (Scalability / Storage)
Estimación: ~10 000 entradas/día (unas 3,6 M al año), ~15 GB al año, ~150 GB a 10 años.
Supera los 100 Gi iniciales de `registry-db` (INF-U1-02).

A) **Particionado declarativo por rango de `seq`** (una partición por año, creada por migración antes de que se necesite), expansión del volumen cuando llegue al 70 % (`allowVolumeExpansion`, U1) y una alerta de proyección de llenado a 90 días. Las particiones antiguas siguen siendo consultables por el expediente. No se mueven a otro almacenamiento (recomendado)

B) Una sola tabla y expansión del volumen cuando haga falta

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Costo de la verificación completa con el tiempo (Performance / Business Rules)
BR-U3-11 fija una verificación **completa** cada noche. A 10 años implicaría volver a
hashear decenas de millones de entradas (~150 GB) cada noche.

A) **Verificación en dos niveles**:
   - **Cada noche**: la cadena de checkpoints completa (firmas y enlaces de todos), el re-hash de las entradas de los **últimos 7 días** y una **muestra aleatoria** del 1 % de los segmentos más antiguos (entre checkpoints), cambiando la muestra cada noche.
   - **Cada mes**: re-hash completo, fuera del horario operativo y con prioridad baja.
   - Bajo demanda (CRO con MFA) y en `restore-drill`, el completo de siempre.
   - Se actualiza BR-U3-11 con estos modos.

   (Recomendado: detecta cualquier reescritura por los checkpoints y acota el costo diario)

B) Mantener el re-hash completo cada noche

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Custodia de la llave de checkpoints (Security)

A) **La llave nunca sale de la bóveda**: el registro firma cada checkpoint con el motor de firma de la bóveda (Vault Transit en kind; el servicio equivalente de la bóveda o el HSM del banco en producción). Firmar una vez por hora hace que la latencia de la bóveda no importe. Si la bóveda no responde, el checkpoint se atrasa (`CheckpointMissing`, SEV2) pero los appends siguen. Agrega un egress del registro hacia la bóveda del banco en producción (recomendado: un pod comprometido no puede robar la llave)

B) Llave privada entregada por ESO como Secret montado en el pod

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Driver de base de datos y pruebas de integración (Tech Stack)

A) **psycopg 3** (modo async) con pool acotado (≤ 5 conexiones, P-U1-08), `synchronous_commit = remote_apply` por transacción y `pg_advisory_xact_lock`. Pruebas de integración contra **PostgreSQL real** con Testcontainers en CI (contenedores locales, sin clúster). La propiedad stateful PBT-U3-01 usa `hypothesis.stateful.RuleBasedStateMachine` contra esa base (recomendado)

B) asyncpg, con pruebas de integración solo en kind

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U3, los NFR heredados (U1) y la decisión pendiente de la Ley 1581
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/decision-registry/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/decision-registry/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Si la Q4 cambia BR-U3-11, actualizar el Functional Design y registrarlo
- [x] 6. Verificar el cumplimiento de las extensiones (incluida una autorrevisión de la tabla contra el cuerpo)
