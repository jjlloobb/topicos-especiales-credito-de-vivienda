# Preguntas de revisión — Functional Design de U8 `case-management`

Dos decisiones abiertas en la revisión del 2026-10-06. Son de producto y de cumplimiento, así
que no las tomo yo. Los demás hallazgos de esa revisión ya están corregidos (ver `audit.md`).

Escribe la letra después de cada `[Answer]:`.

## Question R1 — Qué ve el analista del caso (Business Logic / Privacy; afecta a U10)
**Hallazgo.** `CaseDetail` solo trae la recomendación, la decisión y el estado del crédito.
Los identificadores salen únicamente en el expediente de `cro` y `cumplimiento`, y
`CaseSummary` ni siquiera trae el nombre. El analista (P1) no puede identificar a la persona ni
ver los datos que sustentan su decisión.

A) **El analista ve la solicitud; se ocultan sexo y estrato, y se acepta que la edad y la región queden visibles**:
   - **Bandeja (`CaseSummary`)**: `applicant_display` = nombre completo + los últimos 4 dígitos del documento, junto con el canal, la fecha, el estado y el resultado.
   - **Detalle (`CaseDetail`, `analista` y `cro`)**: la solicitud completa y el `free_text`, escapado en la consola. Se ocultan `sex` y `socioeconomic_stratum`, que solo sirven para monitoreo (FR-ING-05).
   - **Riesgo aceptado**: la fecha de nacimiento (que da la edad) y la dirección, el departamento y el municipio (que dan la región) quedan visibles, porque hacen falta para identificar a la persona y ubicar el inmueble. Se documenta como riesgo aceptado: la disparidad de las **decisiones humanas** por edad y región la vigila U9 (S4 paso 5).
   - **Auditoría de acceso**: cada `get_case` deja un log `case.viewed` (usuario, caso, rol), sin datos del solicitante.
   - Cambios en U0 §1.2 y pendiente para U10.

   (Recomendado: ocultar la edad y la región obligaría a quitar también la identificación y la dirección, que el analista necesita para tramitar)

B) **Se ocultan todas las fuentes de etiquetas protegidas**:
   - sexo y estrato;
   - fecha de nacimiento: solo se muestra «mayor de edad: sí»;
   - dirección, departamento y municipio: solo se muestran el valor y el estado del inmueble.

   El analista ve el nombre, el documento y los datos financieros. Los datos ocultos solo aparecen en el expediente de `cro` y `cumplimiento`.

C) **Mínimo**: nombre y datos financieros en el detalle; documento enmascarado siempre; los identificadores completos solo en el expediente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question R2 — Respaldos de `case-db` con identificadores ya eliminados (Compliance; afecta a U1)
**Hallazgo.** El job de retención borra los identificadores, pero los respaldos mensuales se
retienen 12 meses (NFR-U1-06), y una restauración los recupera.

A) **Volver a aplicar la eliminación después de cada restauración**:
   - el runbook de restauración (NFR-U1-07) y el `restore-drill` ejecutan `case-retention` antes de que case-service quede listo. La retención se calcula con las fechas del caso, que también se restauran, así que el resultado es el mismo;
   - el entorno del simulacro se destruye al terminar;
   - la ventana residual (copias cifradas, de acceso restringido, que contienen identificadores ya vencidos durante hasta 12 meses) se documenta como riesgo aceptado **[VERIFICAR]** con cumplimiento frente a la Ley 1581;
   - cambios: U1 (runbook y `restore-drill`) y U8 (BR-U8-20).

   (Recomendado)

B) Aceptar la ventana de 12 meses sin volver a aplicar la eliminación

X) Other (please describe after [Answer]: tag below)

[Answer]: A
