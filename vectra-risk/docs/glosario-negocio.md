# Glosario de negocio — Vectra Risk

Términos del negocio que el proyecto usa, definidos como los usa el proyecto, con la regla que los gobierna y el archivo donde viven.
Cómo leerlo: busca por tema en el índice de arriba o por nombre en el índice alfabético del final; las rutas son relativas a la raíz del repositorio y las cifras citan el archivo que las fija.
Fecha: 2026-11-21. Complemento: [glosario de tecnología](glosario-tecnologia.md).

Convenciones: **BR-Ux-nn** es una regla de negocio de la unidad x; **FR-…** un requisito funcional; **US-…** una historia de usuario. Las etiquetas **[INTERNO]** y **[VERIFICAR]** son del propio proyecto (ver [Etiquetas INTERNO y VERIFICAR](#etiquetas-interno-y-verificar)).

<!-- INDICE-TEMAS -->
## Índice por temas

- [1. Producto y documentos de origen](#1-producto-y-documentos-de-origen) (11 entradas)
- [2. Problema, usuarios y regulación](#2-problema-usuarios-y-regulación) (12 entradas)
- [3. La solicitud y sus variables](#3-la-solicitud-y-sus-variables) (11 entradas)
- [4. Scoring, política y recomendación](#4-scoring-política-y-recomendación) (13 entradas)
- [5. Explicación](#5-explicación) (10 entradas)
- [6. Fail-closed](#6-fail-closed) (5 entradas)
- [7. El caso y la decisión humana](#7-el-caso-y-la-decisión-humana) (18 entradas)
- [8. Registro de decisiones](#8-registro-de-decisiones) (8 entradas)
- [9. Gobierno de modelos](#9-gobierno-de-modelos) (12 entradas)
- [10. Sesgo y equidad](#10-sesgo-y-equidad) (17 entradas)
- [11. Core bancario e identidad](#11-core-bancario-e-identidad) (8 entradas)
- [12. Métricas de producto](#12-métricas-de-producto) (6 entradas)
- [13. Demos y verificación](#13-demos-y-verificación) (7 entradas)
- [Índice alfabético](#índice-alfabético)

Total: 138 entradas.
<!-- /INDICE-TEMAS -->

---

## 1. Producto y documentos de origen

### Vectra Risk
Motor de *scoring* (puntuación de riesgo) de crédito de vivienda, explicable y auditable, que corre *self-hosted* (alojado por el propio cliente) dentro del clúster de Kubernetes del banco.
- **En el proyecto:** es un producto hipotético construido para un curso. Lema de los requisitos: «El modelo puntúa, el analista decide, el registro queda» (`vectra-risk/aidlc-docs/inception/requirements/requirements.md`, §1). Definición de producto en `vectra-risk/entradas/prd.md`.
- **Relacionados:** [PRD](#prd-product-requirements-document), [Soberanía del dato](#soberanía-del-dato).
- **Ojo:** no hay banco piloto ni datos reales. Todo corre con datos sintéticos y solo en kind.

### PVB (Product Vision Board)
Tablero de visión del producto: problema, segmento, ventaja competitiva, arena competitiva, modelo económico, métricas y riesgos en una hoja.
- **En el proyecto:** `vectra-risk/entradas/pvb.md`. Marca la ventaja primaria como «Trust» y la corrige con una advertencia: explicabilidad y monitoreo de sesgo ya son estándar del mercado.
- **Relacionados:** [PRD](#prd-product-requirements-document), [Moat](#moat-ventaja-competitiva-defendible).
- **Ojo:** todas las cifras del modelo económico (planes de 2.500 y 8.000 USD al mes, margen de ~71 %) están marcadas [INTERNO]: son proyecciones propias.

### PRD (Product Requirements Document)
Documento de requisitos del producto. Es la fuente autoritativa de requisitos del proyecto.
- **En el proyecto:** `vectra-risk/entradas/prd.md`. Abre con una tabla de siete conflictos entre los documentos de investigación y la decisión tomada en cada uno (§0). Fija los cinco principios de diseño (§6), el alcance MoSCoW (§8) y los cinco escenarios de *red-teaming* (§11).
- **Relacionados:** [Principios de diseño P1 a P5](#principios-de-diseño-p1-a-p5), [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5).

### ICP (Ideal Customer Profile)
Perfil de cliente ideal: a quién se le vende.
- **En el proyecto:** bancos medianos y cooperativas financieras colombianas que ya originan crédito de vivienda, ya operan Kubernetes y tienen un modelo propio que nunca llegó a producción (`vectra-risk/entradas/icp.md`; `vectra-risk/entradas/prd.md`, §3).
- **Relacionados:** [CRO](#cro-director-de-riesgo), [LQN Hipotecas](#lqn-hipotecas).
- **Ojo:** el PRD lo llama «hipótesis falsable»: dos de las tres señales de calificación son inferencia, no dato de campo. No hubo entrevistas.

### JTBD (Job to be Done)
El trabajo que el cliente quiere resolver, escrito en primera persona.
- **En el proyecto:** servir en la infraestructura propia el modelo que el área de riesgo ya entrenó, con explicación calculada en el momento de la decisión y monitoreo de sesgo continuo, sin ceder el dato ni el criterio a un tercero (`vectra-risk/entradas/prd.md`, §1).
- **Relacionados:** [ICP](#icp-ideal-customer-profile).

### Moat (ventaja competitiva defendible)
*Moat* (foso): lo que un competidor con el mismo modelo no copia rápido.
- **En el proyecto:** el PRD lo define como soberanía del dato más conocimiento normativo colombiano, y prohíbe venderlo como «explicamos las decisiones» (`vectra-risk/entradas/prd.md`, §0 y §4). En la sustentación se suman la integración ya resuelta en el clúster y las pruebas y políticas propias que se acumulan.
- **Relacionados:** [Soberanía del dato](#soberanía-del-dato), [Registro de decisiones](#registro-de-decisiones).
- **Ojo:** la crítica lo debilita con tres preguntas: el historial de un banco no se transfiere a otro, al comprador le importa poco a diario y no sobrevive a un core con Zest AI integrado (`vectra-risk/entradas/critica.md`, §4).

### Soberanía del dato
Principio 2 del PRD: el modelo, los datos del solicitante y el historial corren dentro de la infraestructura del banco, no en la nube del proveedor.
- **En el proyecto:** regla AUTONOMIA-05. Consecuencia verificable: salida de red denegada por defecto, sin datos personales en los logs y ningún LLM ni API externa (`vectra-risk/aidlc-docs/inception/requirements/requirements.md`, §3).
- **Relacionados:** [Moat](#moat-ventaja-competitiva-defendible), [Datos de identificación](#datos-de-identificación).
- **Ojo:** que los vendedores globales no ofrezcan *self-hosted* en Latinoamérica está marcado [VERIFICAR] en los cinco documentos de entrada: es ausencia de evidencia, no evidencia de ausencia.

### Etiquetas INTERNO y VERIFICAR
Marcas que el proyecto pone a sus propias cifras.
- **En el proyecto:** **[INTERNO]** es una cifra o meta propia, sin fuente externa (por ejemplo el umbral de 5 puntos porcentuales). **[VERIFICAR]** es una afirmación sin confirmar contra la fuente (por ejemplo el tope de usura). El PRD declara que ninguna etiqueta se convirtió en hecho al redactarlo (`vectra-risk/entradas/prd.md`, encabezado).
- **Relacionados:** [Datos sintéticos](#datos-sintéticos).

### Datos sintéticos
Datos generados por programa, sin ninguna persona real detrás.
- **En el proyecto:** el generador de la unidad U5 produce 120 000 filas (84 000 de entrenamiento, 18 000 de validación, 18 000 de prueba), deterministas por versión del generador y semilla; los identificadores llevan el prefijo `SYN-` (BR-U5-01 a BR-U5-05; `vectra-risk/reference-model/config/generator.yaml`).
- **Relacionados:** [Modelo de referencia](#modelo-de-referencia), [Variables proxy](#variables-proxy).
- **Ojo:** la tasa de mora objetivo (4 %) y el tope VIS sintético están marcados [VERIFICAR]. Ninguna métrica del proyecto se midió sobre cartera real.

### Principios de diseño P1 a P5
Las cinco restricciones no negociables del PRD.
- **En el proyecto:** P1 el modelo puntúa y el humano decide; P2 soberanía del dato; P3 *fail-closed* entre scoring y explicación; P4 el monitoreo de sesgo mide y alerta, no certifica; P5 la explicación es una aproximación (`vectra-risk/entradas/prd.md`, §6).
- **Relacionados:** [Reglas AUTONOMIA-01 a AUTONOMIA-06](#reglas-autonomia-01-a-autonomia-06).

### Reglas AUTONOMIA-01 a AUTONOMIA-06
Límites de autonomía que los requisitos atan a los principios.
- **En el proyecto:** 01, los cambios a infraestructura solo entran por *pull request* aprobado; 02, cada criterio de aceptación es un comando; 03, ningún servicio escribe estado de crédito; 04, congelamiento automático y reactivación solo manual; 05, soberanía del dato; 06, sin explicación de la misma versión no hay puntaje usable (`vectra-risk/aidlc-docs/inception/requirements/requirements.md`, §3).
- **Relacionados:** [Principios de diseño P1 a P5](#principios-de-diseño-p1-a-p5).

---

## 2. Problema, usuarios y regulación

### Crédito de vivienda
Préstamo de largo plazo para comprar vivienda, con la vivienda como garantía (definición general).
- **En el proyecto:** es el único producto de crédito cubierto. El PRD cita una cartera hipotecaria colombiana de 153,2 billones de pesos al cuarto trimestre de 2025, equivalente al 7,4 % del PIB (`vectra-risk/entradas/prd.md`, §2.1, con su fuente).
- **Relacionados:** [Originación](#originación), [VIS y no VIS](#vis-y-no-vis).

### Originación
Proceso que va de recibir la solicitud a decidir el crédito (definición general).
- **En el proyecto:** Vectra cubre solo el tramo de la solicitud a la recomendación explicada y la decisión registrada; no desembolsa. La métrica «tiempo de originación» mide de `received_at` a `evaluated_at` (BR-U11-05, `vectra-risk/aidlc-docs/construction/product-metrics/functional-design/business-rules.md`).
- **Relacionados:** [Tiempo de originación](#tiempo-de-originación), [Caso](#caso).

### Comité de crédito
Instancia del banco que firma la aprobación o el rechazo.
- **En el proyecto:** es el destinatario de la recomendación que prepara el analista. No tiene rol propio en el sistema: «la revisión del comité no está en el sistema» (BR-U11-04).
- **Relacionados:** [Analista de crédito](#analista-de-crédito), [Recomendaciones sostenidas](#recomendaciones-sostenidas).

### Analista de crédito
Persona que revisa cada caso y registra la decisión. Rol `analista`; en la consola, «Analista» (*Analyst*).
- **En el proyecto:** usa la bandeja, abre la explicación y decide. No aprueba modelos ni políticas ni reactiva modelos. Su segundo factor es opcional (`vectra-risk/aidlc-docs/inception/user-stories/personas.md`, P1).
- **Relacionados:** [Decisión humana](#decisión-humana), [Irrelevancia silenciosa](#irrelevancia-silenciosa).

### Ingeniero de riesgo
Persona técnica del área de riesgo que entrenó el modelo. Rol `ingeniero_riesgo`; en la consola, «Ingeniero de riesgo» (*Risk engineer*).
- **En el proyecto:** registra una versión de modelo, lanza su validación y ejecuta la promoción con `promotion-tool`. Segundo factor obligatorio (BR-U4-01, `vectra-risk/aidlc-docs/construction/governance/functional-design/business-rules.md`).
- **Relacionados:** [Versión de modelo](#versión-de-modelo), [Promoción](#promoción).
- **Ojo:** el repositorio no usa el nombre «ingeniero de modelos». El término del proyecto es «ingeniero de riesgo».

### CRO (director de riesgo)
*Chief Risk Officer*. Rol `cro`; en la consola, «Director de riesgo (CRO)». Los documentos de entrada lo llaman «VP de Riesgo / CRO».
- **En el proyecto:** es el comprador que decide. Aprueba versiones de modelo y de política, ve la bandeja sin decidir, reintenta casos en «No disponible» y consulta el expediente (BR-U10-12, `vectra-risk/aidlc-docs/construction/console/functional-design/business-rules.md`).
- **Relacionados:** [Aprobación](#aprobación), [Separación de funciones](#separación-de-funciones-cuatro-ojos).

### Oficial de cumplimiento
Persona con veto en la compra y con la última palabra sobre un modelo congelado. Rol `cumplimiento`; en la consola, «Cumplimiento» (*Compliance*).
- **En el proyecto:** es el único rol que resuelve un congelamiento y que aprueba o rechaza fuentes de datos, siempre con segundo factor (BR-U4-03).
- **Relacionados:** [Resolución de congelamiento](#resolución-de-congelamiento), [SARLAFT](#sarlaft).

### SFC (Superintendencia Financiera de Colombia)
Regulador financiero colombiano.
- **En el proyecto:** aparece como el regulador ante quien el banco debe poder defender un rechazo. El proyecto afirma que **no** existe una circular vinculante y específica de la SFC sobre explicabilidad de inteligencia artificial en scoring de crédito (`vectra-risk/entradas/pvb.md`, §9.2; `vectra-risk/entradas/critica.md`, resumen inicial).
- **Relacionados:** [Circular Externa 029 de 2014](#circular-externa-029-de-2014).

### Circular Externa 029 de 2014
Circular general de gestión de riesgos de la SFC. Es la única norma colombiana que el proyecto cita por número.
- **En el proyecto:** sostiene el argumento de venta permitido: «su marco de gestión de riesgo ya vigente exige esto», nunca «la regulación de IA lo exige» (`vectra-risk/entradas/prd.md`, §0 decisión 4; `vectra-risk/entradas/pvb.md`, §9.2).
- **Relacionados:** [SFC](#sfc-superintendencia-financiera-de-colombia).
- **Ojo:** el repositorio no cita artículos ni el texto de la circular. Como contexto global cita un informe del BIS de diciembre de 2024, a través de una nota de prensa enlazada en `vectra-risk/entradas/pvb.md`.

### SARLAFT
Sistema de Administración del Riesgo de Lavado de Activos y de la Financiación del Terrorismo (definición general; el repositorio no desarrolla la sigla).
- **En el proyecto:** solo nombra a la segunda persona compradora, «Oficial de cumplimiento / SARLAFT» (`vectra-risk/entradas/icp.md`). El sistema no implementa controles de lavado de activos.
- **Relacionados:** [Oficial de cumplimiento](#oficial-de-cumplimiento).

### LQN Hipotecas
Originador tecnológico colombiano de crédito hipotecario.
- **En el proyecto:** es competidor o canal, no cliente: Vectra vende a los bancos que compiten con LQN. El PRD le atribuye, con fuente, la promesa de desembolso en 10 días frente a más de 100 (`vectra-risk/entradas/prd.md`, §0 y §2.1).
- **Relacionados:** [ICP](#icp-ideal-customer-profile).

### Irrelevancia silenciosa
Modo de fracaso del producto: el comité deja de usar la explicación sin decirlo.
- **En el proyecto:** la crítica la señala como el fracaso más probable (`vectra-risk/entradas/critica.md`, §5). Por eso existen la North Star y la métrica de ruido.
- **Relacionados:** [North Star](#north-star), [Tasa de consulta de la explicación](#tasa-de-consulta-de-la-explicación-métrica-de-ruido).

---

## 3. La solicitud y sus variables

### Solicitud
Petición de crédito que entra al sistema. En el contrato, `ApplicationIn`.
- **En el proyecto:** la valida el contrato de U0 y la guarda `case-service`; una solicitud inválida no crea caso (BR-U8-01). Límites del formulario: plazo de 12 a 360 meses, monto solicitado no mayor al valor del inmueble, cuerpo de 32 KiB como máximo (`vectra-risk/aidlc-docs/construction/contracts/functional-design/domain-entities.md`, §1.1).
- **Relacionados:** [Caso](#caso), [Canal](#canal).

### Canal
Vía por la que llega la solicitud. Campo `channel`; la consola muestra «Web» y «Manual».
- **En el proyecto:** hay dos entradas: la ingesta de un canal (`POST /v1/intake/applications`) y el alta manual de un analista (`POST /v1/cases`). Las dos exigen una clave de idempotencia (BR-U8-02, BR-U8-04; `vectra-risk/aidlc-docs/construction/case-management/functional-design/business-rules.md`).
- **Relacionados:** [Simulador de canal](#simulador-de-canal), [Idempotencia](#idempotencia).
- **Ojo:** el formulario de alta manual está diferido en la demo (`vectra-risk/aidlc-docs/construction/plans/demo-recorte-funcional.md`).

### Simulador de canal
Identidad de servicio `channel-simulator` que envía solicitudes sintéticas y casos adversariales.
- **En el proyecto:** existe solo fuera de producción (kind y staging). Envía 10 solicitudes por segundo por omisión y 30 como máximo (BR-U12-02, `vectra-risk/aidlc-docs/construction/system-verification/functional-design/business-rules.md`).
- **Relacionados:** [Datos sintéticos](#datos-sintéticos), [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5).

### Datos de identificación
Campos que identifican a la persona: nombre, tipo y número de documento, fecha de nacimiento, teléfono, correo, dirección y municipio.
- **En el proyecto:** nunca son variables del modelo ni entran al registro de decisiones (BR-U0-34, BR-U0-95). El catálogo los lista en `IDENTIFICATION_FIELDS` (`vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`). `case-service` los guarda aparte.
- **Relacionados:** [Texto libre](#texto-libre-observaciones), [Soberanía del dato](#soberanía-del-dato).
- **Ojo:** el vector de variables, las etiquetas de monitoreo y el identificador de caso que sí van al registro son datos seudonimizados, no anónimos.

### Texto libre (observaciones)
Campo `free_text` de la solicitud, de hasta 2 000 caracteres; en la consola, «Observaciones».
- **En el proyecto:** se trata como dato, nunca como instrucción: se guarda tal cual, no se envía al scoring y se escapa al mostrarlo (BR-U0-29, BR-U8-01; FR-ING-04). Tampoco entra al registro.
- **Relacionados:** [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5).

### Relación cuota-ingreso
Cuota mensual del crédito dividida entre el ingreso mensual. Variable `installment_to_income`.
- **En el proyecto:** se deriva en U0: la cuota sale de la fórmula de amortización con la tasa propuesta y el plazo (BR-U0-11), y se divide entre ingreso mensual más otros ingresos (BR-U0-12). Es variable del modelo de referencia y define las bandas de capacidad de pago.
- **Relacionados:** [Banda de capacidad de pago](#banda-de-capacidad-de-pago), [Modelo de referencia](#modelo-de-referencia).

### LTV (loan to value)
Relación entre el monto solicitado y el valor del inmueble. Variable `loan_to_value`.
- **En el proyecto:** es una de las 12 variables del modelo de referencia (`vectra-risk/aidlc-docs/construction/reference-model/functional-design/domain-entities.md`, §3.1). El contrato solo exige que el monto no supere el valor del inmueble; el LTV máximo «es de política».
- **Relacionados:** [Solicitud](#solicitud).

### Tasa propuesta (E.A.)
Tasa de interés efectiva anual de la solicitud. Campo `proposed_rate_ea`.
- **En el proyecto:** es variable del modelo y se compara contra el tope de usura de la política vigente.
- **Relacionados:** [Tope de usura](#tope-de-usura).

### VIS y no VIS
Vivienda de interés social: categoría legal colombiana de vivienda con precio tope (definición general). En Vectra es más estrecho: una clasificación informativa de la política.
- **En el proyecto:** un caso es `vis` si el valor del inmueble no supera `vis_max_property_value` de la política vigente, y `no_vis` si lo supera. Aparece como motivo de la recomendación y no cambia el resultado (BR-U7-04, `vectra-risk/aidlc-docs/construction/scoring-explainability/functional-design/business-rules.md`). En la consola: «Vivienda de interés social» (*Social interest housing (VIS)*).
- **Relacionados:** [Parámetros normativos](#parámetros-normativos), [Motivos de la recomendación](#motivos-de-la-recomendación).
- **Ojo:** VIS no es un campo de la solicitud ni una variable del modelo. El tope de la política de referencia (200 000 000 de pesos, `vectra-risk/reference-model/config/generator.yaml`) es sintético y está marcado [VERIFICAR].

### Tope de usura
Tasa máxima legal de interés (definición general).
- **En el proyecto:** parámetro `usury_cap_ea` de la política, con fecha de vigencia. Si la tasa propuesta lo supera, la recomendación pasa a «revisión requerida» con el motivo `tasa_sobre_usura`; una tasa igual al tope no lo supera (BR-U7-04).
- **Relacionados:** [Parámetros normativos](#parámetros-normativos).
- **Ojo:** el valor de la política de referencia (0,28) es sintético. Los valores reales están marcados [VERIFICAR] contra la fuente oficial (FR-POL-02).

### Estrato
Estrato socioeconómico de la vivienda, de 1 a 6 o «no informado» (*Socioeconomic stratum*).
- **En el proyecto:** es una etiqueta de monitoreo de sesgo, no una variable del modelo, y no se le muestra al analista (BR-U8-13b).
- **Relacionados:** [Atributo protegido](#atributo-protegido-etiqueta-de-monitoreo).

---

## 4. Scoring, política y recomendación

### Scoring
Cálculo de un puntaje de riesgo con un modelo estadístico (definición general).
- **En el proyecto:** lo hace `scoring-service` llamando al modelo activo; nunca decide: entrega «siempre una recomendación o un FailClosed» (BR-U7-02).
- **Relacionados:** [Puntaje](#puntaje-score), [Recomendación](#recomendación).

### Puntaje (score)
Probabilidad de incumplimiento, entre 0 y 1, con cuatro decimales. Más alto significa más riesgo.
- **En el proyecto:** la consola lo muestra como «riesgo estimado» (BR-U0-07; `vectra-risk/aidlc-docs/construction/scoring-explainability/functional-design/domain-entities.md`, §1). Un valor fuera de rango produce el *fail-closed* `model_output_invalid`.
- **Relacionados:** [Corte](#corte-cutoff), [Confianza](#confianza).
- **Ojo:** al revés que un puntaje de buró: aquí un número bajo es bueno.

### Confianza
Número entre 0 y 1 que dice cuánto se parece la solicitud a los datos con que se entrenó el modelo.
- **En el proyecto:** la calcula el predictor: vale 0 si hay una categoría nunca vista; si no, el menor entre la fracción de variables dentro del rango de entrenamiento y una medida de distancia a la distribución (BR-U5-11 a BR-U5-13, `vectra-risk/aidlc-docs/construction/reference-model/functional-design/business-rules.md`).
- **Relacionados:** [Baja confianza](#baja-confianza), [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5).

### Baja confianza
Marca de una recomendación cuya confianza queda por debajo del umbral de la política.
- **En el proyecto:** fuerza el resultado «revisión requerida» con el motivo `baja_confianza`; nunca se presenta como segura (FR-SCO-03, BR-U7-04).
- **Relacionados:** [Confianza](#confianza), [Revisión requerida](#revisión-requerida).

### Corte (cutoff)
Umbral de puntaje de la política vigente.
- **En el proyecto:** puntaje menor que el corte da «favorable»; igual o mayor, «desfavorable». Puede haber un corte distinto por canal (BR-U7-04). La política sintética de referencia usa 0,0800 (`vectra-risk/reference-model/config/generator.yaml`).
- **Relacionados:** [Política vigente](#política-vigente).

### Política vigente
Versión activa de la política de negocio: un artefacto versionado e independiente del modelo.
- **En el proyecto:** contiene el corte, el umbral de baja confianza, las reglas por canal y los parámetros normativos. Solo el rol `cro` la escribe; aprobarla la activa de inmediato y hay como máximo una activa (BR-U4-11, BR-U4-12; FR-POL-01 a FR-POL-04). Estados: propuesta, activa, rechazada, histórica.
- **Relacionados:** [Parámetros normativos](#parámetros-normativos), [Separación de funciones](#separación-de-funciones-cuatro-ojos).
- **Ojo:** los servicios no pueden modificar su propia política. Separar modelo y política es una exigencia del oficial de cumplimiento en el ICP.

### Parámetros normativos
Parte de la política con fecha de vigencia: tope de valor VIS y tope de usura.
- **En el proyecto:** periodos de vigencia que no se solapan, cada uno con su referencia a la fuente. Si hoy no hay periodo vigente, la recomendación sale como «revisión requerida» con el motivo `parametro_normativo_no_vigente`; no es un *fail-closed* (BR-U7-06, BR-U4-11). La alerta `NormativeParamsExpiring` avisa 15 días antes del vencimiento.
- **Relacionados:** [VIS y no VIS](#vis-y-no-vis), [Tope de usura](#tope-de-usura).

### Recomendación
Salida del modelo más la política: puntaje, confianza, resultado, motivos y explicación completa. Tipo `Recommendation`; en la consola, «Recomendación del modelo».
- **En el proyecto:** se guarda en el registro antes de entregarse; si no se puede guardar, no se entrega (FR-SCO-08). Una recomendación entregada no se vuelve a calcular.
- **Relacionados:** [Decisión humana](#decisión-humana), [Resultado de la recomendación](#resultado-de-la-recomendación).
- **Ojo:** recomendación no es decisión. La recomendación es de la máquina; la decisión es siempre de una persona (principio P1).

### Resultado de la recomendación
Uno de tres valores del catálogo `Outcome`: `favorable` (*Favorable*), `desfavorable` (*Unfavorable*) o `revision_requerida` (*Review required*).
- **En el proyecto:** cinco reglas, todas evaluadas: sin parámetro normativo vigente, tasa sobre usura o baja confianza fuerzan «revisión requerida»; si ninguna aplica, decide el corte; la clasificación VIS es solo informativa (BR-U7-04, BR-U7-05; `vectra-risk/scoring-explainability/scoring/src/scoring/policy.py`).
- **Relacionados:** [Motivos de la recomendación](#motivos-de-la-recomendación).

### Revisión requerida
Resultado que no se inclina por favorable ni desfavorable: pide que una persona resuelva.
- **En el proyecto:** el analista lo cierra con la decisión `resuelve_revision` y una justificación obligatoria. En el monitoreo de sesgo cuenta como no favorable (BR-U9-01).
- **Relacionados:** [Baja confianza](#baja-confianza), [Decisión humana](#decisión-humana).

### Motivos de la recomendación
Códigos cerrados que dicen qué regla de política produjo el resultado. Catálogo `ReasonCode`.
- **En el proyecto:** `score_bajo_corte`, `score_sobre_corte`, `baja_confianza`, `vis`, `no_vis`, `tasa_sobre_usura` y `parametro_normativo_no_vigente` (`vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`). La consola los traduce, por ejemplo «Puntaje por debajo del corte» (`vectra-risk/console/spa/src/i18n/labels.es.json`).
- **Relacionados:** [Factores de la explicación](#factores-de-la-explicación).
- **Ojo:** motivos y factores son cosas distintas. Los motivos vienen de la política; los factores, de la explicación del modelo.

### Modelo de referencia
Modelo que hace de «banco que entrega su modelo». Queda fuera de la frontera del producto.
- **En el proyecto:** XGBoost con hiperparámetros y semilla fijos, 12 variables: relación cuota-ingreso, LTV, ingreso mensual, otros ingresos, obligaciones mensuales, tipo de empleo, antigüedad laboral, máximo de días de mora en 12 meses, plazo, tasa propuesta, condición del inmueble y canal (`vectra-risk/aidlc-docs/construction/reference-model/functional-design/domain-entities.md`, §3.1).
- **Relacionados:** [Datos sintéticos](#datos-sintéticos), [AUC-ROC](#auc-roc).
- **Ojo:** sexo, estrato, región, edad, municipio y texto libre están excluidos de las variables. Vectra acepta cualquier modelo tabular; este es solo el de la demo.

### AUC-ROC
Área bajo la curva ROC: medida de 0 a 1 de qué tan bien un modelo separa buenos y malos pagadores (definición general).
- **En el proyecto:** meta mayor que 0,85 [INTERNO]. La entrega del modelo de referencia falla si la validación queda por debajo (`min_auc: 0.85` en `vectra-risk/reference-model/config/generator.yaml`). En la validación de gobierno se informa y no bloquea: decide el CRO (BR-U4-07).
- **Relacionados:** [Validación](#validación).
- **Ojo:** el 0,85 viene de un estudio académico sobre otros datos (hasta 88,29 %, citado en `vectra-risk/entradas/prd.md`); no está validado contra cartera real.

---

## 5. Explicación

### Explicabilidad
Capacidad de decir por qué un modelo dio un puntaje (definición general).
- **En el proyecto:** la explicación se calcula en la misma petición que el puntaje y contra la misma versión de modelo (FR-EXP-01). No se vende como diferenciador: el PRD reconoce que ya es estándar del mercado.
- **Relacionados:** [Explicación](#explicación), [Sin explicación no hay recomendación](#sin-explicación-no-hay-recomendación).

### Explicación
Objeto que acompaña a cada recomendación: contribuciones por variable, narrativa, aviso de aproximación, método y versiones.
- **En el proyecto:** la produce `explainability-service` a partir del explicador de la misma versión del modelo. Una explicación entregada siempre pasó la verificación de factualidad (BR-U7-08 a BR-U7-11, `vectra-risk/aidlc-docs/construction/scoring-explainability/functional-design/business-rules.md`).
- **Relacionados:** [SHAP](#shap), [Narrativa](#narrativa), [Aproximación post-hoc](#aproximación-post-hoc).

### SHAP
*SHapley Additive exPlanations*: técnica que reparte el puntaje de un caso entre sus variables (definición general).
- **En el proyecto:** las contribuciones se calculan con TreeSHAP del propio XGBoost (`pred_contribs`), sin la librería `shap`, en el explicador de KServe de la misma versión.
- **Relacionados:** [Factores de la explicación](#factores-de-la-explicación).
- **Ojo:** LIME, que el PVB menciona, quedó fuera del alcance (FR-EXP-07).

### Factores de la explicación
Las variables que más movieron el puntaje de un caso; la consola las muestra como razones.
- **En el proyecto:** hasta 5 factores, ordenados por valor absoluto de la contribución. Cada uno lleva la frase de dirección del diccionario y una intensidad: fuerte (al menos 0,30 del total), moderada (de 0,10 a 0,30) o leve (BR-U7-10).
- **Relacionados:** [Diccionario de variables](#diccionario-de-variables), [Factores usados](#factores-usados).

### Narrativa
Texto en español, sin jerga, que cuenta los factores en orden.
- **En el proyecto:** sale de una plantilla determinista (`template:v1`), sin LLM y sin números de SHAP (`vectra-risk/scoring-explainability/explainability/templates/template_v1.txt`; FR-EXP-03).
- **Relacionados:** [Factualidad](#factualidad).
- **Ojo:** el PRD recomendaba un LLM con solo SHAP como entrada; el proyecto eligió la plantilla. La interfaz para un generador LLM dentro del clúster está prevista y no implementada (FR-EXP-06).

### Aproximación post-hoc
Aviso fijo de toda explicación: describe qué variables movieron el riesgo estimado; no es una lectura del razonamiento del modelo.
- **En el proyecto:** principio P5 y FR-EXP-04. El validador de factualidad exige que el aviso llegue sin cambios.
- **Relacionados:** [Explicación](#explicación).

### Factualidad
Comprobación automática de que la narrativa dice lo mismo que las contribuciones: mismos factores, mismo orden, mismo signo.
- **En el proyecto:** un validador independiente del generador lee la narrativa y la compara; cualquier diferencia produce el *fail-closed* `factuality_failed` (BR-U7-11; FR-EXP-05).
- **Relacionados:** [Narrativa](#narrativa), [Causas de fail-closed](#causas-de-fail-closed).

### Diccionario de variables
Tabla por versión de modelo con el nombre legible de cada variable y sus frases de «sube el riesgo» y «baja el riesgo». Tipo `FeatureDictionary`.
- **En el proyecto:** lo entrega el paquete del modelo, lo guarda y sirve gobierno, y lo consume la explicación. Debe cubrir todas las variables; si falta una, hay *fail-closed* `feature_dictionary_incomplete` (BR-U4-18, BR-U0-80, BR-U0-81).
- **Relacionados:** [Versión de modelo](#versión-de-modelo).

### Resumen para el solicitante
Texto para la persona a quien se le negó el crédito: hasta 3 factores aptos para mostrar, sin puntaje ni versión.
- **En el proyecto:** BR-U7-13 y BR-U7-14; solo si la decisión final es desfavorable.
- **Relacionados:** [Explicación](#explicación).
- **Ojo:** está diseñado y diferido en la demo (`vectra-risk/aidlc-docs/construction/plans/demo-recorte-funcional.md`).

### Sin explicación no hay recomendación
Principio P3: un puntaje nunca se entrega como usable si su explicación falló o es de otra versión de modelo.
- **En el proyecto:** regla AUTONOMIA-06. El constructor de `Recommendation` del contrato hace cumplir la sincronía. Razón de negocio: el banco no puede defender ante cumplimiento o el regulador una decisión cuyo porqué no corresponde al modelo que la produjo.
- **Relacionados:** [Fail-closed](#fail-closed).

---

## 6. Fail-closed

### Fail-closed
Fallar cerrado: ante la duda, el sistema no entrega nada en vez de entregar algo dudoso (definición general).
- **En el proyecto:** si no se pueden garantizar la sincronía entre puntaje y explicación o el guardado en el registro, no hay recomendación ni explicación sustituta (BR-U0-05, `vectra-risk/aidlc-docs/construction/contracts/functional-design/business-rules.md`). En el registro queda una entrada «Recomendación no emitida» (*Recommendation not issued*).
- **Relacionados:** [Causas de fail-closed](#causas-de-fail-closed), [En sincronización](#en-sincronización).
- **Ojo:** el fail-closed degrada velocidad, no corrección: el banco conserva su proceso manual.

### Causas de fail-closed
Catálogo cerrado de diez causas, en orden de precedencia: si aplican varias, gana la de menor número (BR-U0-02, BR-U0-03).
- **En el proyecto:** `FailClosedCause` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`; textos en `vectra-risk/console/spa/src/i18n/labels.es.json`. La categoría agrupa las causas: dependencia (algo no respondió), calidad (respondió mal), desincronía (respondió otra versión) y congelamiento.

| # | Causa | En la consola | Categoría | Qué significa y qué la provoca |
|---|---|---|---|---|
| 1 | `model_frozen` | Modelo congelado | congelamiento | La versión activa está congelada por el monitoreo de sesgo. No se reintenta. |
| 2 | `serving_config_unavailable` | Configuración de servicio no disponible | dependencia | El scoring no pudo leer de gobierno qué versión y qué política sirven. |
| 3 | `model_output_invalid` | Resultado del modelo no válido | calidad | El modelo devolvió un puntaje no finito o fuera de 0 a 1. |
| 4 | `timeout` | Tiempo de espera agotado | dependencia | La explicación no llegó dentro del plazo. |
| 5 | `explainer_unavailable` | Explicación no disponible | dependencia | El servicio de explicación está caído, saturado o con el cortacircuitos abierto. |
| 6 | `explainer_error` | Error en la explicación | calidad | La explicación respondió con un error que no es caída ni demora: un defecto. |
| 7 | `version_mismatch` | Versión que no coincide | desincronía | La explicación o el diccionario son de otra versión de modelo que el puntaje. |
| 8 | `feature_dictionary_incomplete` | Diccionario de variables incompleto | desincronía | Falta el diccionario de esa versión o no cubre un factor. |
| 9 | `factuality_failed` | Explicación no verificada | calidad | La narrativa no coincide con las contribuciones (factores, orden o signo). |
| 10 | `registry_unavailable` | Registro no disponible | dependencia | El registro no confirmó el guardado; sin registro no se entrega. |

- **Relacionados:** [Reintento](#reintento), [Modelo congelado (estado del caso)](#modelo-congelado-estado-del-caso), [Factualidad](#factualidad).
- **Ojo:** en la demo D1, con el flujo F22 apagado, la causa es `explainer_error` y no `timeout`: la malla responde 403 al instante y el servicio de explicación trata un 4xx del explicador como defecto, no como caída (`vectra-risk/scoring-explainability/explainability/src/explainability/explain.py`). Los tiempos de espera están solo en el código (`vectra-risk/scoring-explainability/scoring/src/scoring/config.py`).

### Causa local
Causa que anota `case-service` cuando ni siquiera obtuvo respuesta del scoring. Catálogo `LocalCause`.
- **En el proyecto:** `serving_config_unavailable`, `scoring_unreachable` («Servicio de puntaje inalcanzable») y `scoring_rejected` («Servicio de puntaje rechazó la solicitud»).
- **Relacionados:** [No disponible (estado del caso)](#no-disponible-estado-del-caso).

### Reintento
Nueva evaluación de un caso que quedó sin recomendación.
- **En el proyecto:** automático: 6 intentos como máximo, con espera de 30 s que se duplica cada vez y variación de ±20 % (BR-U8-07; `vectra-risk/case-management/src/vectra_case/config.py`). Manual: solo el CRO, solo desde «No disponible», sin segundo factor (BR-U8-11).
- **Relacionados:** [Fail-closed persistente](#fail-closed-persistente).
- **Ojo:** el reintento manual del CRO no existe de punta a punta en la demo: la vista de fallos persistentes está diferida (`vectra-risk/system-verification/demos/journey-7-3.md`).

### Fail-closed persistente
Caso que agotó los reintentos y escaló como incidente técnico.
- **En el proyecto:** el caso pasa a «No disponible», se escribe una entrada de escalamiento y se dispara la alerta `FailClosedPersistente`; runbook en `vectra-risk/platform/runbooks/fail-closed-persistente.md`.
- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4).

---

## 7. El caso y la decisión humana

### Caso
Unidad de trabajo que nace con cada solicitud válida. Su `case_id` es también la referencia del crédito ante el core.
- **En el proyecto:** `vectra-risk/aidlc-docs/construction/case-management/functional-design/domain-entities.md`. Sus siete estados están en el catálogo `CaseState`, y las transiciones las vigilan el dominio y un disparador de la base de datos (BR-U8-12).
- **Relacionados:** [Bandeja](#bandeja), [Solicitud](#solicitud).

### Bandeja
Lista común de casos para analistas y CRO, sin analista asignado.
- **En el proyecto:** ruta `/casos` de la consola. Muestra el nombre y los últimos 4 dígitos del documento, se refresca cada 15 s y no incluye los vencidos salvo que se filtren (BR-U8-13, BR-U10-10).
- **Relacionados:** [Caso](#caso).

### Identificador del caso
Campo `case_id`: un UUID que nombra el caso. No es un dato personal.
- **En el proyecto:** la consola tiene «Ir al caso», que abre el detalle a partir del identificador. No hay búsqueda por nombre: pondría el nombre en la URL, el historial y los logs de acceso (BR-U10-10; `vectra-risk/console/spa/src/views/cases/GoToCase.tsx`).
- **Relacionados:** [Caso](#caso), [Datos de identificación](#datos-de-identificación).
- **Ojo:** en el registro, el identificador de caso es un dato seudonimizado: no dice quién es la persona, pero la enlaza con sus datos en `case-service`.

### En evaluación
Estado `en_evaluacion` (*In evaluation*): el caso espera su primera evaluación o una nueva.
- **En el proyecto:** lo provocan la ingesta válida, el reintento del CRO o el barrido tras reactivar un modelo congelado.
- **Relacionados:** [Listo](#listo), [En sincronización](#en-sincronización).

### Listo
Estado `listo` (*Ready*): llegó una recomendación con su explicación.
- **En el proyecto:** es el único estado desde el que el analista puede decidir. Nunca se reevalúa. Si el modelo se congela después, el caso sigue listo con un aviso de cautela (BR-U8-14).
- **Relacionados:** [Decidido](#decidido).

### En sincronización
Estado `en_sincronizacion` (*Syncing*): hubo un fail-closed que se puede reintentar y quedan intentos.
- **En el proyecto:** es lo que ve el analista durante una desincronía entre puntaje y explicación (recorrido 7.3 del PRD). No muestra puntaje.
- **Relacionados:** [Reintento](#reintento), [No disponible (estado del caso)](#no-disponible-estado-del-caso).

### No disponible (estado del caso)
Estado `no_disponible` (*Unavailable*): falló el sexto intento o el scoring rechazó la solicitud sin posibilidad de reintento.
- **En el proyecto:** sale solo con el reintento del CRO o por vencimiento. La consola lo muestra sin puntaje (FR-UI-02).
- **Relacionados:** [Fail-closed persistente](#fail-closed-persistente).
- **Ojo:** «No disponible» es también un valor del estado de crédito y del estado de servicio. Son tres cosas distintas con la misma etiqueta.

### Modelo congelado (estado del caso)
Estado `modelo_congelado` (*Model frozen*): el caso llegó cuando la versión activa estaba congelada.
- **En el proyecto:** no se reintenta. Un barrido cada 5 minutos lo devuelve a «En evaluación» cuando el modelo vuelve a estar activo (BR-U8-10).
- **Relacionados:** [Congelamiento](#congelamiento).

### Decidido
Estado `decidido` (*Decided*): terminal. El registro confirmó la decisión humana.
- **En el proyecto:** el caso solo pasa a decidido cuando el registro responde; si no responde, la decisión queda pendiente y se reconcilia después (BR-U8-18).
- **Relacionados:** [Decisión humana](#decisión-humana).

### Vencido
Estado `vencido` (*Expired*): terminal. Pasó el plazo de retención sin decisión.
- **En el proyecto:** plazos de 2 años sin decidir y 10 años decidido, ambos [VERIFICAR] (BR-U8-20; `vectra-risk/case-management/chart/values.yaml`).
- **Relacionados:** [Datos de identificación](#datos-de-identificación).
- **Ojo:** el trabajo programado que vence y anonimiza casos está retirado del chart en la demo.

### Decisión humana
Lo que el analista registra sobre un caso listo: resultado final (favorable o desfavorable) y su relación con la recomendación. Entrada `human_decision`.
- **En el proyecto:** solo el rol `analista`, en nombre propio, con el caso en «Listo» (BR-U8-15). No exige segundo factor, y eso está marcado [VERIFICAR] con cumplimiento (BR-U10-09b).
- **Relacionados:** [Sigue la recomendación](#sigue-la-recomendación), [Se aparta de la recomendación](#se-aparta-de-la-recomendación), [Resuelve la revisión](#resuelve-la-revisión).

### Sigue la recomendación
Valor `sigue` (*Follows the recommendation*): el resultado final coincide con el recomendado.
- **En el proyecto:** BR-U0-35. La justificación es opcional.
- **Relacionados:** [Recomendaciones sostenidas](#recomendaciones-sostenidas).

### Se aparta de la recomendación
Valor `se_aparta` (*Overrides the recommendation*): el analista elige el resultado contrario al recomendado.
- **En el proyecto:** exige una justificación de 20 a 2 000 caracteres (BR-U0-36, BR-U8-16). Es la evidencia de que la persona decide y no el modelo.
- **Relacionados:** [North Star](#north-star), [Justificación](#justificación).

### Resuelve la revisión
Valor `resuelve_revision` (*Resolves the review*): el analista cierra una recomendación de «revisión requerida».
- **En el proyecto:** es el único valor válido cuando el resultado recomendado fue revisión requerida; justificación obligatoria (BR-U0-35, BR-U0-36).
- **Relacionados:** [Revisión requerida](#revisión-requerida).

### Justificación
Texto del analista que sustenta su decisión.
- **En el proyecto:** obligatoria al apartarse o resolver una revisión; mínimo 20 y máximo 2 000 caracteres. Texto de la consola en `vectra-risk/console/spa/src/i18n/messages.es.json`.
- **Relacionados:** [Factores usados](#factores-usados).

### Factores usados
Lista de factores de la explicación que el analista declara haber usado, o exactamente «ninguno».
- **En el proyecto:** campo `used_factors` de la decisión (BR-U8-16). Alimenta el numerador de la North Star.
- **Relacionados:** [North Star](#north-star).

### Consulta de la explicación
Evento que deja constancia de que un analista abrió el detalle de la explicación. Entrada `explanation_view`.
- **En el proyecto:** solo cuenta el botón «Ver explicación», una vez por caso y usuario (BR-U8-19, BR-U10-08). No es requisito para decidir: el sistema solo anota si ocurrió antes (`explanation_viewed_before`, BR-U8-17).
- **Relacionados:** [Tasa de consulta de la explicación](#tasa-de-consulta-de-la-explicación-métrica-de-ruido).

### Expediente
Reconstrucción de todo lo ocurrido con un caso, tal como se mostró, para defender una decisión. Tipo `Dossier`.
- **En el proyecto:** solo para `cro` y `cumplimiento` (BR-U3-14, BR-U10-03). Responde al caso de uso 2 del PRD: defender un rechazo.
- **Relacionados:** [Registro de decisiones](#registro-de-decisiones).
- **Ojo:** diseñado; no lo ejercita ninguna demo.

---

## 8. Registro de decisiones

### Registro de decisiones
Bitácora única y encadenada de todo lo que el sistema recomendó y de lo que las personas decidieron. Servicio `decision-registry`.
- **En el proyecto:** es el único componente de criticidad *Critical*, por ser la evidencia regulatoria (`vectra-risk/aidlc-docs/inception/application-design/unit-of-work.md`, U3). Reglas en `vectra-risk/aidlc-docs/construction/decision-registry/functional-design/business-rules.md`.
- **Relacionados:** [Inmutabilidad](#inmutabilidad-append-only), [Entrada del registro](#entrada-del-registro).

### Inmutabilidad (append-only)
*Append-only* (solo añadir): una entrada escrita no se modifica ni se borra.
- **En el proyecto:** tres capas: el rol de base de datos de la aplicación solo tiene `INSERT` y `SELECT` (BR-U3-01); un disparador rechaza `UPDATE`, `DELETE` y `TRUNCATE` para cualquier rol (BR-U3-02); y la cadena de hashes con puntos de control firmados detecta a quien se salte las dos anteriores (BR-U3-08).
- **Relacionados:** [Cadena de hashes](#cadena-de-hashes), [Punto de control](#punto-de-control-checkpoint).

### Entrada del registro
Cada renglón del registro, con número de secuencia, tipo, contenido canónico y hash.
- **En el proyecto:** once tipos (`EntryType`): `recommendation`, `fail_closed`, `human_decision`, `explanation_view`, `model_event`, `policy_event`, `data_source_event`, `freeze`, `frozen_resolution`, `genesis` y `checkpoint`. Cada tipo tiene un único servicio que lo escribe (BR-U3-03). Tamaño máximo de 64 KiB.
- **Relacionados:** [Idempotencia](#idempotencia).

### Cadena de hashes
Cada entrada guarda el hash de la anterior, así que cambiar una rompe todas las siguientes (definición general).
- **En el proyecto:** secuencia contigua desde 0 y `hash = SHA-256(hash anterior + contenido canónico)` (BR-U3-04, BR-U3-07). La entrada 0 es `genesis`, «Inicio del registro».
- **Relacionados:** [Verificación de integridad](#verificación-de-integridad).

### Punto de control (checkpoint)
Entrada que fija, con firma, la cabeza de la cadena en un momento dado.
- **En el proyecto:** cada hora un trabajo programado hace firmar el número de secuencia y el hash de cabeza, añade la entrada `checkpoint` y copia el resultado a un almacenamiento que no se puede reescribir (BR-U3-08).
- **Relacionados:** [Inmutabilidad](#inmutabilidad-append-only).
- **Ojo:** en la demo los trabajos de punto de control, verificación y archivo están diferidos: en `vectra-risk/decision-registry/chart/templates` solo existe el del agregador.

### Verificación de integridad
Recorrido de la cadena que recalcula los hashes y dice si está íntegra.
- **En el proyecto:** modos incremental, nocturno, completo y por rango; resultado `integra`, `inconsistente` o `error`. Una inconsistencia dispara la alerta `RegistryChainBroken` y los expedientes pasan a mostrar «integridad NO verificada» (BR-U3-11 a BR-U3-13b).
- **Relacionados:** [Cadena de hashes](#cadena-de-hashes).

### Agregador
Trabajo programado `registry-aggregator` que lee la cadena y mantiene tablas de conteos para el monitoreo de sesgo.
- **En el proyecto:** corre cada 5 minutos y guarda marginales por atributo, nunca la combinación de etiquetas (BR-U3-17; `vectra-risk/decision-registry/chart/values.yaml`). Si se atrasa más de 30 minutos, alerta y la corrida de sesgo falla.
- **Relacionados:** [Monitoreo de sesgo](#monitoreo-de-sesgo).

### Idempotencia
Repetir la misma petición con la misma clave produce el mismo resultado, sin duplicar (definición general).
- **En el proyecto:** toda escritura al registro lleva una clave única: mismo contenido devuelve la confirmación original; contenido distinto devuelve 409 (BR-U3-06). La ingesta de solicitudes hace lo mismo (BR-U8-02).
- **Relacionados:** [Entrada del registro](#entrada-del-registro).

---

## 9. Gobierno de modelos

### Gobierno de modelos
Reglas sobre quién registra, valida, aprueba, activa y retira un modelo. Servicio `governance-service`.
- **En el proyecto:** máquina de estados con transiciones acotadas por identidad (BR-U4-01, `vectra-risk/aidlc-docs/construction/governance/functional-design/business-rules.md`; código en `vectra-risk/governance/src/vectra_governance/model_fsm.py`). Ninguna transición surte efecto sin evidencia en el registro, salvo el congelamiento (BR-U4-17).
- **Relacionados:** [Estados de una versión de modelo](#estados-de-una-versión-de-modelo).

### Versión de modelo
Paquete inmutable de un modelo con su explicador, su diccionario y su especificación de variables. Identificador `model_version_id`.
- **En el proyecto:** formato `mv-<fecha>-<8 hexadecimales del hash del manifiesto>`. Predictor y explicador se despliegan como una unidad; un despliegue parcial deja la versión sin servir (FR-MOD-04).
- **Relacionados:** [Diccionario de variables](#diccionario-de-variables), [Especificación de variables](#especificación-de-variables).

### Estados de una versión de modelo
Diez estados; la consola los lista en `MODEL_STATES`.
- **En el proyecto:** `registrado` → `en_validacion` → `lista_para_aprobacion` (o `validacion_fallida`) → `aprobado` (o `rechazado`) → `activo` → `inactivo`, `congelado` o `retirado`. Como máximo una versión está activa o congelada a la vez (BR-U4-02).
- **Relacionados:** [Activo e inactivo](#activo-e-inactivo), [Congelamiento](#congelamiento).
- **Ojo:** el requisito FR-MOD-05 enumera seis estados; el diseño de gobierno y la consola usan diez.

### Validación
Paso automático que revisa una versión antes de pedir aprobación. La ejecuta `model-validation-job`.
- **En el proyecto:** calcula el AUC-ROC, la disparidad inicial y la comprobación de sincronía entre predictor y explicador. Solo la sincronía bloquea; AUC y disparidad se informan con sus umbrales y decide el CRO (BR-U4-05, BR-U4-07). Plazo de 2 horas (`vectra-risk/governance/src/vectra_governance/evidence.py`).
- **Relacionados:** [AUC-ROC](#auc-roc), [Aprobación](#aprobación).

### Aprobación
Acto humano, con segundo factor, que autoriza una versión de modelo o de política.
- **En el proyecto:** la da el CRO. Para un modelo debe ser distinto de quien lo registró; para una política, distinto del CRO que la propuso (BR-U4-10).
- **Relacionados:** [Separación de funciones](#separación-de-funciones-cuatro-ojos), [Segundo factor](#segundo-factor).

### Separación de funciones (cuatro ojos)
Quien aprueba es distinto de quien propuso o registró.
- **En el proyecto:** gobierno compara el identificador de usuario de ambos (BR-U4-10, BR-U2-02). Además, solo el monitoreo de sesgo congela y solo cumplimiento descongela (BR-U4-03, BR-U4-04).
- **Relacionados:** [Aprobación](#aprobación).
- **Ojo:** el diseño anota que producción necesita al menos 2 usuarios con rol `cro`.

### Promoción
Paso de una versión aprobada a servir en producción.
- **En el proyecto:** siempre por *pull request*: `promotion-tool` genera un PR de un commit, una persona lo fusiona y sincroniza a mano, y después `mark_active` cambia el estado. La herramienta nunca aplica ni sincroniza (BR-U4-08, BR-U4-09; FR-MOD-03).
- **Relacionados:** [Activo e inactivo](#activo-e-inactivo), [Rollback](#rollback).

### Activo e inactivo
`activo` es la versión que sirve recomendaciones; `inactivo`, la que dejó de servir porque otra se activó.
- **En el proyecto:** al activar una versión, el sistema pasa la anterior a inactiva en la misma operación (BR-U4-01). Durante la promoción conviven dos versiones desplegadas; después queda una activa y la anterior inactiva (`vectra-risk/DECISIONES-LOOP.md`, §7).
- **Relacionados:** [Configuración de servicio](#configuración-de-servicio-serving-config).

### Rollback
Vuelta a la versión anterior.
- **En el proyecto:** un PR que restaura el despliegue de la versión inactiva, sincronización manual y `mark_active` sobre ella (BR-U4-09; US-208). Con la versión actual congelada no hay rollback sin reactivar antes: gobierno responde 409 `active_version_frozen`.
- **Relacionados:** [Promoción](#promoción).

### Configuración de servicio (serving config)
Renglón único que dice qué versión de modelo y qué política sirven ahora, y en qué estado.
- **En el proyecto:** la compone gobierno; el scoring la guarda en caché 5 s como máximo, así que un congelamiento surte efecto en 6 s o menos (BR-U4-14; `vectra-risk/scoring-explainability/scoring/src/scoring/config.py`). El estado de servicio (`ServingState`) es `activo`, `congelado` o `no_disponible`.
- **Relacionados:** [Política vigente](#política-vigente).

### Especificación de variables
Lista ordenada de las variables que espera una versión de modelo y de dónde sale cada una. Archivo `feature_spec.json` del paquete.
- **En el proyecto:** inmutable por versión; la lee `case-worker` para armar el vector de variables (BR-U4-19, BR-U5-07).
- **Relacionados:** [Versión de modelo](#versión-de-modelo).

### Fuente de datos
Origen nuevo de datos que una versión de modelo declara usar.
- **En el proyecto:** su incorporación exige medir la disparidad antes y después y la aprobación del oficial de cumplimiento (FR-BIA-06; BR-U4-13, BR-U9-17). Estados: propuesta, en evaluación, aprobada o rechazada.
- **Relacionados:** [Disparidad](#disparidad).
- **Ojo:** diferido en la demo (historia US-306). El recorrido 7.4 del PRD habla de una fuente nueva; la demo D2 usa en su lugar un modelo con variables proxy.

---

## 10. Sesgo y equidad

### Monitoreo de sesgo
Medición continua de si el modelo recomienda favorablemente en proporciones distintas a grupos distintos. Servicio `bias-monitoring-service` y su trabajo programado.
- **En el proyecto:** corre cada 15 minutos, todo o nada (BR-U9-10; `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`). Si deja de correr 1 hora, alerta `MonitoreoSesgoDetenido`; el modelo sigue sirviendo (BR-U9-21).
- **Relacionados:** [Disparidad](#disparidad), [Congelamiento](#congelamiento).

### Atributo protegido (etiqueta de monitoreo)
Característica de la persona sobre la que se vigila el trato desigual. El diseño la llama «etiqueta de monitoreo» (`MonitoringLabels`).
- **En el proyecto:** cuatro: `sexo`, `rango_edad`, `region` y `estrato`. Se capturan solo para monitorear; no son variables del modelo ni aparecen en logs (FR-ING-05, BR-U9-02).
- **Relacionados:** [Grupo](#grupo), [Variables proxy](#variables-proxy).

### Grupo
Un valor de un atributo protegido.
- **En el proyecto:** sexo: F, M, no informado; edad: 18-25, 26-35, 36-45, 46-55, 56-65, 66+; región: andina, caribe, pacífica, orinoquía, amazonía, insular; estrato: 1 a 6 y no informado (`vectra-risk/aidlc-docs/construction/contracts/functional-design/domain-entities.md`, §2.2). «No informado» se reporta y nunca entra al máximo ni al mínimo.
- **Relacionados:** [Celda](#celda).

### Banda de capacidad de pago
Tramo de la relación cuota-ingreso dentro del cual se comparan los grupos.
- **En el proyecto:** `lt_20` (menos de 0,20), `20_30` (de 0,20 a 0,30) y `gt_30` (más de 0,30) (BR-U0-42; `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/labels.py`). La consola: «Menos de 20», «De 20 a 30», «Más de 30».
- **Relacionados:** [Relación cuota-ingreso](#relación-cuota-ingreso), [Disparidad](#disparidad).
- **Ojo:** las bandas existen para «controlar por capacidad de pago»: comparar personas que pueden pagar parecido. No son bandas de puntaje.

### Celda
Combinación de atributo, grupo y banda. Es la unidad mínima del cálculo.
- **En el proyecto:** BR-U9-02. La consola marca cada celda como «Muestra suficiente» o «Muestra insuficiente».
- **Relacionados:** [Muestra mínima](#muestra-mínima-y-muestra-insuficiente).

### Tasa favorable
Recomendaciones favorables de un grupo divididas entre el total del grupo.
- **En el proyecto:** «revisión requerida» cuenta como no favorable (BR-U9-01).
- **Relacionados:** [Disparidad](#disparidad).

### Disparidad
Diferencia de tasas favorables entre grupos, en puntos porcentuales (diferencia de paridad demográfica).
- **En el proyecto:** tres niveles: por banda, la tasa mayor menos la menor entre grupos con muestra suficiente (BR-U9-03); agregada del atributo, el promedio de las bandas ponderado por tamaño (BR-U9-04); agregada del modelo, la mayor de los cuatro atributos (BR-U9-05). Reglas en `vectra-risk/aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md`.
- **Relacionados:** [Umbral de disparidad](#umbral-de-disparidad), [Límite de congelamiento](#límite-de-congelamiento).
- **Ojo:** la librería propia se valida contra Fairlearn como oráculo; no usa Fairlearn en producción.

### Ventana
Periodo de datos que entra al cálculo.
- **En el proyecto:** 30 días UTC: hoy más los 29 anteriores (BR-U9-08; `window_days: 30`). Tras una reactivación, la ventana de esa versión empieza al día siguiente. El tablero permite 7, 30 o 90 días.
- **Relacionados:** [Resolución de congelamiento](#resolución-de-congelamiento).

### Umbral de disparidad
Valor contra el que se compara la disparidad: 5 puntos porcentuales, [INTERNO].
- **En el proyecto:** `threshold_pp: 5` en `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`. Cambiarlo exige un PR revisado por cumplimiento (BR-U9-13).
- **Relacionados:** [Límite de congelamiento](#límite-de-congelamiento).
- **Ojo:** es una cifra propia, sin respaldo normativo. El PVB la formula como «menos de 5 puntos controlando por capacidad de pago».

### Muestra mínima y muestra insuficiente
Tamaño mínimo de una celda para entrar al cálculo: 30 casos.
- **En el proyecto:** `n_min: 30` (BR-U9-02). Una celda menor se reporta con su tamaño y la marca «muestra insuficiente» (*Insufficient sample*) y no entra a ningún cálculo. Si todos los agregados son insuficientes, no hay congelamiento (BR-U9-11).
- **Relacionados:** [Celda](#celda).

### Límite de congelamiento
Cota inferior de la disparidad agregada de un atributo, calculada con un margen estadístico exigente (z = 3,14).
- **En el proyecto:** es lo que de verdad se compara con el umbral para congelar (regla R4, BR-U9-04 y BR-U9-11; `Z_FREEZE` en `vectra-risk/bias-monitoring/disparity/src/vectra_disparity/stats.py`). El intervalo del 95 % que se publica (z = 1,96) es solo contexto.
- **Relacionados:** [Congelamiento](#congelamiento).
- **Ojo:** una disparidad observada mayor que 5 puntos no congela por sí sola: debe superarlo también su cota inferior. Requisitos e historias dicen «disparidad agregada mayor que 5 puntos»; la regla precisa es esta.

### Cota inferior
Extremo bajo del intervalo de una disparidad: el valor mínimo que la disparidad real tendría con mucha seguridad, dado el tamaño de la muestra.
- **En el proyecto:** es LA regla que decide el congelamiento. Se congela si la cota inferior de algún atributo supera el umbral, no si lo supera la disparidad observada (BR-U9-11; z = 3,14 en `vectra-risk/bias-monitoring/disparity/src/vectra_disparity/stats.py`). Con pocos casos el intervalo es ancho y la cota cae por debajo del umbral aunque lo observado esté por encima; así no se congela un modelo por ruido de muestreo.
- **Relacionados:** [Límite de congelamiento](#límite-de-congelamiento), [Umbral de disparidad](#umbral-de-disparidad), [Muestra mínima y muestra insuficiente](#muestra-mínima-y-muestra-insuficiente).
- **Ojo:** ejemplo medido en la demo D2 el 2026-11-21 (PR #236): región tuvo 0,2438 observado y 0,1418 de límite de congelamiento, mayor que 0,05, y congeló; estrato tuvo 0,1558 observado y no congeló, porque su cota inferior no superó el umbral.

### Congelamiento
Bloqueo automático de la versión activa para nuevas solicitudes. Entrada `freeze`; en la consola, «Congelamiento» (*Freeze*).
- **En el proyecto:** ocurre si algún atributo tiene su límite de congelamiento por encima del umbral (BR-U9-11). Solo lo ejecuta la identidad `bias-monitoring-job` (BR-U4-04). Efecto: el scoring responde fail-closed `model_frozen`, los casos nuevos quedan en «Modelo congelado» y no se puede activar otra versión.
- **Relacionados:** [Paquete de contexto](#paquete-de-contexto), [Resolución de congelamiento](#resolución-de-congelamiento).
- **Ojo:** no hay congelamiento manual ni reactivación automática (BR-U4-03, BR-U4-16). La disparidad de las decisiones humanas se reporta y alerta, pero no congela (BR-U9-14).

### Paquete de contexto
Resumen de agregados que acompaña a un congelamiento para que cumplimiento decida. Tipo `FreezeContext`.
- **En el proyecto:** versión congelada, tres mediciones (antes, después y últimos 7 días), atributo que lo disparó, atributos y bandas implicados y volumen afectado (BR-U9-15, BR-U9-16). Lo lee solo `cumplimiento`, en la ruta `/congelamientos/:freezeId` de la consola.
- **Relacionados:** [Congelamiento](#congelamiento).

### Resolución de congelamiento
Decisión de cumplimiento sobre un modelo congelado. Entrada `frozen_resolution`.
- **En el proyecto:** tres acciones, todas solo del rol `cumplimiento`, con segundo factor y justificación (BR-U4-01, BR-U4-03; BR-U10-13 en la consola):

| Acción | Efecto en la versión | Qué pasa después |
|---|---|---|
| `reactivar` (*Reactivate*) | de congelado a activo | vuelve a servir; la ventana de monitoreo reinicia al día UTC siguiente; un barrido devuelve a evaluación los casos en «Modelo congelado» |
| `descartar` (*Discard*) | de congelado a retirado | deja de existir como versión servible; hay que promover otra |
| `investigar` (*Investigate*) | sigue congelado, marcado en investigación | no sirve; queda constancia de que cumplimiento lo está revisando |

- **Relacionados:** [Oficial de cumplimiento](#oficial-de-cumplimiento), [Step-up](#step-up), [Modo de reactivación de la demo D2](#modo-de-reactivación-de-la-demo-d2).
- **Ojo:** un congelamiento admite varias resoluciones en orden, por ejemplo `investigar` y luego `reactivar`; el registro las guarda todas con su fecha (BR-U9-19, `vectra-risk/aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md`). Excepción declarada: en kind, y solo en kind, la verificación puede reactivar con el usuario sintético `cumplimiento-1` por la misma API autenticada (FR-BIA-05).

### Variables proxy
Variables que no son un atributo protegido pero lo delatan, como una zona o un canal.
- **En el proyecto:** U5 fabrica una variante del modelo con dos de ellas (`zona_vivienda` y `canal_originacion_detalle`) para el escenario RT-2. Disparidad medida de 25,41 puntos en región (`vectra-risk/aidlc-docs/construction/reference-model/evidence/cierre-demo.md`).
- **Relacionados:** [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5).

### Mide y alerta, no certifica
Principio P4: el monitoreo detecta y avisa; no prueba que el modelo sea equitativo.
- **En el proyecto:** leyenda fija en cada respuesta del tablero (BR-U9-18; FR-UI-05). Una lista única de frases prohibidas impide que cualquier texto del producto prometa ausencia de discriminación (`vectra-risk/contracts/forbidden-phrases.yaml`; BR-U0-94, FR-BIA-08).
- **Relacionados:** [Monitoreo de sesgo](#monitoreo-de-sesgo).
- **Ojo:** la crítica advierte que el producto puede legitimar el sesgo que dice vigilar (`vectra-risk/entradas/critica.md`, §6). Nunca digas que el modelo «está libre» de sesgo.

---

## 11. Core bancario e identidad

### Core bancario
Sistema central del banco que guarda el estado real de cada crédito (definición general).
- **En el proyecto:** es externo. En la demo lo sustituye `core-banking-mock`, que solo existe en kind y staging. Un guion de demo lo llama «núcleo bancario».
- **Relacionados:** [Estado de crédito](#estado-de-crédito), [Sin escritura al core](#sin-escritura-al-core).
- **Ojo:** la integración con un core real está fuera del alcance (PRD §8, *Won't have*).

### Estado de crédito
Situación del crédito en el core. Catálogo `CreditStatus`.
- **En el proyecto:** del core: `en_estudio`, `aprobado`, `desembolsado`, `rechazado`, `cancelado`. Propios de Vectra: `sin_credito`, `no_disponible` (el core no responde) y `no_integrado` (la integración está apagada). Se lee solo para casos decididos (BR-U8-21).
- **Relacionados:** [Core bancario](#core-bancario).
- **Ojo:** «aprobado» aquí es del core, no del modelo ni del analista.

### Sin escritura al core
Vectra lee el estado de crédito y nunca lo escribe.
- **En el proyecto:** regla AUTONOMIA-03, tres capas: `case-service` no tiene cliente de escritura; el permiso `core:write-credit` existe en el catálogo sin ningún titular (`SCOPE_HOLDERS` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`); y la red solo deja pasar `GET` (BR-U8-22).
- **Relacionados:** [Principios de diseño P1 a P5](#principios-de-diseño-p1-a-p5), [Demos D1 a D4](#demos-d1-a-d4).
- **Ojo:** el porqué es de negocio: si el sistema pudiera cambiar el estado de un crédito, el modelo estaría decidiendo.

### Roles
Cuatro roles de negocio, uno por usuario como máximo: `analista`, `ingeniero_riesgo`, `cro` y `cumplimiento`.
- **En el proyecto:** catálogo `Role`; regla BR-U2-01 (`vectra-risk/aidlc-docs/construction/identity-edge/functional-design/business-rules.md`). La autorización se aplica en el servidor: la interfaz solo oculta, no protege (FR-UI-07).
- **Relacionados:** [Permisos de servicio (scopes)](#permisos-de-servicio-scopes).

### Permisos de servicio (scopes)
*Scopes* (alcances): permisos de las identidades de servicio, no de las personas.
- **En el proyecto:** 18 en el catálogo `Scope`, cada uno con sus titulares; por ejemplo `governance:freeze` es solo de `bias-monitoring-job`.
- **Relacionados:** [Sin escritura al core](#sin-escritura-al-core).

### Segundo factor
Prueba adicional de identidad además de la contraseña; aquí, un código temporal de una aplicación.
- **En el proyecto:** obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`; opcional para `analista` (BR-U2-03).
- **Relacionados:** [Step-up](#step-up).

### Step-up
Volver a pedir el segundo factor justo antes de una acción sensible.
- **En el proyecto:** la acción exige una autenticación con segundo factor de hace 900 s (15 minutos) como máximo; si no, el servidor responde 403 `mfa_required` (BR-U0-72, BR-U2-04; `MFA_MAX_AGE` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`). Lo piden: registrar, validar y aprobar modelos, proponer y aprobar políticas, decidir fuentes, resolver congelamientos y verificar la integridad.
- **Relacionados:** [Segundo factor](#segundo-factor).
- **Ojo:** la decisión del analista, la consulta de la explicación y el reintento del CRO no lo piden.

### Sesión
Tiempo durante el cual un usuario sigue autenticado.
- **En el proyecto:** token de acceso de 300 s; sesión de 1 800 s de inactividad y 36 000 s como máximo (BR-U2-06). La consola avisa a los 25 minutos de inactividad y cierra a los 30 (BR-U10-20).
- **Relacionados:** [Step-up](#step-up).

---

## 12. Métricas de producto

### North Star
Métrica principal del producto: proporción de decisiones en que la explicación se usó de verdad.
- **En el proyecto:** numerador: decisiones en que el analista consultó la explicación antes y declaró al menos un factor usado; denominador: todas las decisiones atribuibles del periodo (BR-U11-03, `vectra-risk/aidlc-docs/construction/product-metrics/functional-design/business-rules.md`). Se desglosa en sustentada, cambiada y revisión resuelta.
- **Relacionados:** [Decisión atribuible](#decisión-atribuible), [Factores usados](#factores-usados).
- **Ojo:** no tiene meta acordada: se define con el primer piloto, que no existe.

### Decisión atribuible
Decisión humana cuya recomendación de referencia existe en el registro.
- **En el proyecto:** BR-U11-01. Es el denominador de todas las razones de producto.
- **Relacionados:** [North Star](#north-star).

### Recomendaciones sostenidas
Proporción de decisiones que siguieron la recomendación.
- **En el proyecto:** decisiones `sigue` entre decisiones atribuibles (BR-U11-04). Meta: más del 70 % al mes 6 [INTERNO] (FR-MET-05).
- **Relacionados:** [Sigue la recomendación](#sigue-la-recomendación).
- **Ojo:** el tablero la rotula «aproximación»: el PVB habla de decisiones sostenidas por el comité, y el sistema solo sabe si el analista siguió la recomendación. No la confundas con «sustentada», que es un tramo de la North Star.

### Tasa de consulta de la explicación (métrica de ruido)
Proporción de decisiones en que el analista abrió la explicación antes de decidir, en una ventana móvil de 7 días.
- **En el proyecto:** BR-U11-07; FR-MET-02. Si pasa varios días bajo el piso, dispara la alerta `RuidoExplicacion`, que es una señal de producto y no una falla técnica.
- **Relacionados:** [Piso](#piso), [Irrelevancia silenciosa](#irrelevancia-silenciosa).

### Piso
Valor mínimo aceptable de la tasa de consulta: 0,6.
- **En el proyecto:** `noise_floor: 0.6`, sostenido 3 días seguidos (`noise_sustain_days: 3`) y con al menos 50 decisiones por día para contar (`noise_min_decisions: 50`), todo [INTERNO] (`vectra-risk/product-metrics/chart/values-product-metrics-policy.yaml`).
- **Relacionados:** [Tasa de consulta de la explicación](#tasa-de-consulta-de-la-explicación-métrica-de-ruido).

### Tiempo de originación
Tiempo desde que se recibe la solicitud hasta que hay recomendación explicada.
- **En el proyecto:** meta: menos de 1 hora en el 80 % de los casos estándar [INTERNO] (BR-U11-05; FR-MET-04).
- **Relacionados:** [Originación](#originación).

---

## 13. Demos y verificación

### Demos D1 a D4
Las cuatro demostraciones de la sustentación, con guion en `vectra-risk/system-verification/demos/`.
- **En el proyecto:**

| Demo | Guion | Orden de la herramienta | Qué prueba | Qué se ve |
|---|---|---|---|---|
| D1 | `journey-7-3.md` | `rt3` | RT-3 y el recorrido 7.3: un modelo alterado no llega a servir y, con la ruta al explicador (F22) apagada, el caso escala | casos de «En sincronización» a «No disponible»; alerta `FailClosedPersistente` |
| D2 | `journey-7-4.md` | `rt2-setup` y `rt2` | RT-2 y el recorrido 7.4: un modelo con variables proxy se congela solo | paquete de contexto en la consola; cumplimiento reactiva con segundo factor |
| D3 | `rt-5.md` | `rt5` | RT-5: nadie escribe en el core | 403 del proxy de la malla; alerta `CoreWriteAttempt`; contador de escrituras en 0 |
| D4 | `dashboard.md` | `decisions` (día D) y `u11` (día D + 1) | las métricas de producto | tablero con la North Star, las sostenidas y la tasa de consulta con su piso |

- **Relacionados:** [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5), [Recorridos 7.3 y 7.4](#recorridos-73-y-74), [Presentador y operador](#presentador-y-operador).
- **Ojo:** antes de todo corre `prepare` y al final `report`. Orden recomendado por la guía (`vectra-risk/system-verification/docs/paso-18-kind.md`): D3, D4 (día D), D1, D2 y D4 (día D + 1). Tiempos de los guiones: D1 tarda de 12,4 a 19,3 minutos en escalar; D2, más de 75 minutos; D4 solo se lee el día siguiente al de las decisiones. En vivo se enseña el resultado, no la espera.

### Recorridos 7.3 y 7.4
Los dos casos límite del PRD que la sustentación debe mostrar.
- **En el proyecto:** 7.3 es la desincronía entre puntaje y explicación; 7.4, el escalamiento a una persona por disparidad (`vectra-risk/entradas/prd.md`, §7).
- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4).

### Presentador y operador
Los dos papeles humanos de una demo.
- **En el proyecto:** el **operador** corre la herramienta, abre y fusiona los PR y sincroniza en Argo CD; el **presentador** enseña la consola y las alertas. El presentador entra con los usuarios sintéticos terminados en `-2` (`analista-2`, `cumplimiento-2`), que la herramienta no usa en ese momento; la herramienta usa los terminados en `-1` (`vectra-risk/system-verification/demos/journey-7-3.md`).
- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4).
- **Ojo:** en una sustentación de una sola persona, la misma persona hace los dos papeles.

### Modo de reactivación de la demo D2
Opción `--reactivation` de la orden `rt2`, que dice quién reactiva el modelo congelado.
- **En el proyecto:** `tool` (por omisión): la herramienta hace el step-up de `cumplimiento-1` y envía la reactivación; sirve para ensayar. `presenter`: la herramienta espera a que el presentador reactive en la consola con `cumplimiento-2`, con el segundo factor que impone el servidor, y después verifica lo mismo (`vectra-risk/system-verification/demos/journey-7-4.md`).
- **Relacionados:** [Resolución de congelamiento](#resolución-de-congelamiento), [Presentador y operador](#presentador-y-operador).
- **Ojo:** el modo `presenter` es el que muestra a una persona decidiendo. El mismo modelo no se vuelve a congelar el mismo día UTC de su reactivación, así que un segundo ensayo va otro día o con otro paquete.

### Escenarios RT-1 a RT-5
Cinco escenarios de *red-teaming* (ataque simulado) que valen como criterios de aceptación del sistema.
- **En el proyecto:** definidos en `vectra-risk/entradas/prd.md` (§11) y en `vectra-risk/aidlc-docs/inception/requirements/requirements.md` (§6); oráculos en BR-U12-04.

| Escenario | Ataque | Resultado esperado | Orden y demo |
|---|---|---|---|
| RT-1 | instrucciones escondidas en el texto libre | se guardan como dato; la recomendación y la narrativa son idénticas a las del caso sin ese texto | `rt1`; sin demo |
| RT-2 | variables proxy que delatan un atributo protegido | el monitoreo detecta la disparidad, congela, y el modelo sigue congelado tras más corridas | `rt2`; D2 |
| RT-3 | desincronía forzada o paquete de modelo alterado | cero puntajes entregados como decisión; el caso queda sin recomendación | `rt3`; D1 |
| RT-4 | entradas fuera del dominio de entrenamiento | la confianza no se infla; salen como baja confianza y revisión requerida | `rt4`; sin demo |
| RT-5 | intento de escribir el estado de crédito | denegado en dos capas: sin ruta de red y sin permiso; el proxy responde 403 | `rt5`; D3 |

- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4), [Variables proxy](#variables-proxy), [Sin escritura al core](#sin-escritura-al-core).
- **Ojo:** las demos ejercitan RT-2, RT-3 y RT-5. Las secciones `rt1` y `rt4` de la herramienta están diferidas y responden «no ejecutado»; RT-1 sí tiene una prueba de propiedades en el código de scoring.

### Informe de verificación
Tabla generada por la herramienta de verificación con un renglón por escenario e historia.
- **En el proyecto:** cada renglón dice `pasa`, `falla` o `no ejecutado`; lo que no tiene evidencia es «no ejecutado», nunca «pasa» (BR-U12-10, BR-U12-11; `vectra-risk/aidlc-docs/construction/system-verification/functional-design/business-rules.md`).
- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4).

### Recorte de la demo
Lista de lo que está diseñado pero no se construyó o no se despliega para la demo.
- **En el proyecto:** `vectra-risk/aidlc-docs/construction/plans/demo-recorte-funcional.md`. Incluye: fuentes de datos, resumen para el solicitante, alta manual, vista de fallos persistentes, expediente, puntos de control y verificación del registro, y retención de casos.
- **Relacionados:** [Demos D1 a D4](#demos-d1-a-d4).
- **Ojo:** si te preguntan por una función, comprueba primero si está en esta lista. Además, staging y producción no se despliegan: todo lo mostrado corre en kind.

---

<!-- INDICE-ALFABETICO -->
## Índice alfabético

- [Activo e inactivo](#activo-e-inactivo)
- [Agregador](#agregador)
- [Analista de crédito](#analista-de-crédito)
- [Aprobación](#aprobación)
- [Aproximación post-hoc](#aproximación-post-hoc)
- [Atributo protegido (etiqueta de monitoreo)](#atributo-protegido-etiqueta-de-monitoreo)
- [AUC-ROC](#auc-roc)
- [Baja confianza](#baja-confianza)
- [Banda de capacidad de pago](#banda-de-capacidad-de-pago)
- [Bandeja](#bandeja)
- [Cadena de hashes](#cadena-de-hashes)
- [Canal](#canal)
- [Caso](#caso)
- [Causa local](#causa-local)
- [Causas de fail-closed](#causas-de-fail-closed)
- [Celda](#celda)
- [Circular Externa 029 de 2014](#circular-externa-029-de-2014)
- [Comité de crédito](#comité-de-crédito)
- [Confianza](#confianza)
- [Configuración de servicio (serving config)](#configuración-de-servicio-serving-config)
- [Congelamiento](#congelamiento)
- [Consulta de la explicación](#consulta-de-la-explicación)
- [Core bancario](#core-bancario)
- [Corte (cutoff)](#corte-cutoff)
- [Cota inferior](#cota-inferior)
- [Crédito de vivienda](#crédito-de-vivienda)
- [CRO (director de riesgo)](#cro-director-de-riesgo)
- [Datos de identificación](#datos-de-identificación)
- [Datos sintéticos](#datos-sintéticos)
- [Decidido](#decidido)
- [Decisión atribuible](#decisión-atribuible)
- [Decisión humana](#decisión-humana)
- [Demos D1 a D4](#demos-d1-a-d4)
- [Diccionario de variables](#diccionario-de-variables)
- [Disparidad](#disparidad)
- [En evaluación](#en-evaluación)
- [En sincronización](#en-sincronización)
- [Entrada del registro](#entrada-del-registro)
- [Escenarios RT-1 a RT-5](#escenarios-rt-1-a-rt-5)
- [Especificación de variables](#especificación-de-variables)
- [Estado de crédito](#estado-de-crédito)
- [Estados de una versión de modelo](#estados-de-una-versión-de-modelo)
- [Estrato](#estrato)
- [Etiquetas INTERNO y VERIFICAR](#etiquetas-interno-y-verificar)
- [Expediente](#expediente)
- [Explicabilidad](#explicabilidad)
- [Explicación](#explicación)
- [Factores de la explicación](#factores-de-la-explicación)
- [Factores usados](#factores-usados)
- [Factualidad](#factualidad)
- [Fail-closed](#fail-closed)
- [Fail-closed persistente](#fail-closed-persistente)
- [Fuente de datos](#fuente-de-datos)
- [Gobierno de modelos](#gobierno-de-modelos)
- [Grupo](#grupo)
- [ICP (Ideal Customer Profile)](#icp-ideal-customer-profile)
- [Idempotencia](#idempotencia)
- [Identificador del caso](#identificador-del-caso)
- [Informe de verificación](#informe-de-verificación)
- [Ingeniero de riesgo](#ingeniero-de-riesgo)
- [Inmutabilidad (append-only)](#inmutabilidad-append-only)
- [Irrelevancia silenciosa](#irrelevancia-silenciosa)
- [JTBD (Job to be Done)](#jtbd-job-to-be-done)
- [Justificación](#justificación)
- [Límite de congelamiento](#límite-de-congelamiento)
- [Listo](#listo)
- [LQN Hipotecas](#lqn-hipotecas)
- [LTV (loan to value)](#ltv-loan-to-value)
- [Mide y alerta, no certifica](#mide-y-alerta-no-certifica)
- [Moat (ventaja competitiva defendible)](#moat-ventaja-competitiva-defendible)
- [Modelo congelado (estado del caso)](#modelo-congelado-estado-del-caso)
- [Modelo de referencia](#modelo-de-referencia)
- [Modo de reactivación de la demo D2](#modo-de-reactivación-de-la-demo-d2)
- [Monitoreo de sesgo](#monitoreo-de-sesgo)
- [Motivos de la recomendación](#motivos-de-la-recomendación)
- [Muestra mínima y muestra insuficiente](#muestra-mínima-y-muestra-insuficiente)
- [Narrativa](#narrativa)
- [No disponible (estado del caso)](#no-disponible-estado-del-caso)
- [North Star](#north-star)
- [Oficial de cumplimiento](#oficial-de-cumplimiento)
- [Originación](#originación)
- [Paquete de contexto](#paquete-de-contexto)
- [Parámetros normativos](#parámetros-normativos)
- [Permisos de servicio (scopes)](#permisos-de-servicio-scopes)
- [Piso](#piso)
- [Política vigente](#política-vigente)
- [PRD (Product Requirements Document)](#prd-product-requirements-document)
- [Presentador y operador](#presentador-y-operador)
- [Principios de diseño P1 a P5](#principios-de-diseño-p1-a-p5)
- [Promoción](#promoción)
- [Puntaje (score)](#puntaje-score)
- [Punto de control (checkpoint)](#punto-de-control-checkpoint)
- [PVB (Product Vision Board)](#pvb-product-vision-board)
- [Recomendación](#recomendación)
- [Recomendaciones sostenidas](#recomendaciones-sostenidas)
- [Recorridos 7.3 y 7.4](#recorridos-73-y-74)
- [Recorte de la demo](#recorte-de-la-demo)
- [Registro de decisiones](#registro-de-decisiones)
- [Reglas AUTONOMIA-01 a AUTONOMIA-06](#reglas-autonomia-01-a-autonomia-06)
- [Reintento](#reintento)
- [Relación cuota-ingreso](#relación-cuota-ingreso)
- [Resolución de congelamiento](#resolución-de-congelamiento)
- [Resuelve la revisión](#resuelve-la-revisión)
- [Resultado de la recomendación](#resultado-de-la-recomendación)
- [Resumen para el solicitante](#resumen-para-el-solicitante)
- [Revisión requerida](#revisión-requerida)
- [Roles](#roles)
- [Rollback](#rollback)
- [SARLAFT](#sarlaft)
- [Scoring](#scoring)
- [Se aparta de la recomendación](#se-aparta-de-la-recomendación)
- [Segundo factor](#segundo-factor)
- [Separación de funciones (cuatro ojos)](#separación-de-funciones-cuatro-ojos)
- [Sesión](#sesión)
- [SFC (Superintendencia Financiera de Colombia)](#sfc-superintendencia-financiera-de-colombia)
- [SHAP](#shap)
- [Sigue la recomendación](#sigue-la-recomendación)
- [Simulador de canal](#simulador-de-canal)
- [Sin escritura al core](#sin-escritura-al-core)
- [Sin explicación no hay recomendación](#sin-explicación-no-hay-recomendación)
- [Soberanía del dato](#soberanía-del-dato)
- [Solicitud](#solicitud)
- [Step-up](#step-up)
- [Tasa de consulta de la explicación (métrica de ruido)](#tasa-de-consulta-de-la-explicación-métrica-de-ruido)
- [Tasa favorable](#tasa-favorable)
- [Tasa propuesta (E.A.)](#tasa-propuesta-ea)
- [Texto libre (observaciones)](#texto-libre-observaciones)
- [Tiempo de originación](#tiempo-de-originación)
- [Tope de usura](#tope-de-usura)
- [Umbral de disparidad](#umbral-de-disparidad)
- [Validación](#validación)
- [Variables proxy](#variables-proxy)
- [Vectra Risk](#vectra-risk)
- [Vencido](#vencido)
- [Ventana](#ventana)
- [Verificación de integridad](#verificación-de-integridad)
- [Versión de modelo](#versión-de-modelo)
- [VIS y no VIS](#vis-y-no-vis)
<!-- /INDICE-ALFABETICO -->
