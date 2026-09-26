# Investigación de crítica — Vectra Risk

> **Este es el documento más importante de la carpeta.**
>
> Su propósito no es defender a Vectra Risk: es **atacarlo**. Un análisis que solo
> reúne evidencia favorable no sirve ni para vender ni para decidir.
>
> Toda cifra externa lleva fuente con enlace y fecha, obtenida por búsqueda web el
> 15 de agosto de 2026. Donde la fuente es secundaria (un blog o agregador citando
> a Gartner/McKinsey/BIS sin que yo haya podido confirmar el reporte primario), lo
> digo explícitamente en vez de presentarla como si fuera primaria. Lo que no
> resistió el contraste está en la sección final, con el nombre del error.

---

## TL;DR — por qué Vectra Risk podría fracasar

1. **El diferenciador central ya es tabla estándar del mercado, no una ventaja.**
   Explicabilidad post-hoc (SHAP, LIME) y monitoreo de sesgo (AIF360 de IBM,
   Fairlearn de Microsoft) son librerías gratuitas y maduras. Y a nivel comercial,
   **Zest AI ya está integrado nativamente en Temenos Loan Origination** desde
   abril de 2025 — el mismo core bancario contra el que Vectra Risk pretendía
   integrarse "desde afuera".
2. **El mercado de plataformas de scoring explicable con gobernanza ya es una
   categoría madura y poblada**, no un espacio vacío: FICO Platform, Experian
   Ascend, DataRobot, Provenir, Zest AI, Upstart, H2O.ai compiten hoy mismo por el
   mismo comprador (CRO de banca) con el mismo argumento de venta.
3. **El competidor local más peligroso no vende scoring: ya está originando
   crédito.** LQN Hipotecas tiene 80.000+ operaciones procesadas, 900+ brokers y
   US$12M de capital fresco. No necesita comprarle a Vectra Risk nada — podría
   vender su propia capa de decisión a los bancos que hoy le compiten.
4. **El argumento regulatorio es más débil de lo que el PVB sugiere.** No existe,
   hasta donde pude verificar, una circular vinculante y específica de la
   Superintendencia Financiera de Colombia que exija explicabilidad algorítmica en
   scoring de crédito. Lo que hay son declaraciones públicas del Superintendente y
   una circular general de gestión de riesgos de 2014, no una norma técnica de IA.
5. **El moat propuesto no es transferible entre clientes**: el historial de
   decisiones y desenlaces de un banco no predice nada sobre la cartera de otro
   banco con otra política de originación.
6. **El producto que promete reducir sesgo puede estar legitimando el sesgo que ya
   existe en los datos**, no corrigiéndolo — y las explicaciones post-hoc dan una
   sensación de control que no siempre corresponde a cómo el modelo realmente
   decidió.

---

## 1. Comoditización: ya ocurrió, no está por ocurrir

| Capacidad que Vectra Risk vende como diferenciador | Quién ya la cubre | Costo |
|---|---|---|
| Explicabilidad post-hoc por decisión (SHAP, LIME) | Librerías open source ampliamente documentadas y usadas en la literatura académica de crédito ([arXiv 2103.00949](https://arxiv.org/pdf/2103.00949); [arXiv 2506.19383](https://arxiv.org/pdf/2506.19383)) | $0 |
| Monitoreo de sesgo y fairness entre grupos protegidos | AI Fairness 360 de IBM, con más de 70 métricas de sesgo y 9 algoritmos de mitigación ([AIF360](https://aif360.res.ibm.com/); [GitHub Trusted-AI/AIF360](https://github.com/Trusted-AI/AIF360)); Fairlearn de Microsoft (referenciado en el mismo estudio comparativo, [arXiv 2205.06922](https://arxiv.org/pdf/2205.06922)) | $0 |
| Serving de modelos en Kubernetes con versionado y autoscaling | KServe, CNCF Incubating desde noviembre 2025 ([CNCF, 11 nov 2025](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)); Seldon Core v2 con drift detection incorporado | $0 |
| Motor de scoring explicable integrado nativamente al core bancario | **Zest AI integrado de forma nativa en Temenos Loan Origination**, anunciado el 29 de abril de 2025, ya vendido a "muchas cooperativas de crédito y bancos comunitarios" en Norteamérica ([Zest AI / Temenos, 29 abr 2025](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)) | Licencia comercial ya existente, sin que el banco tenga que integrar un producto nuevo |
| Plataformas enterprise de decisión crediticia con explicabilidad y auditoría como requisito de entrada, no como feature premium | FICO Platform, Experian Ascend, DataRobot, Provenir, Taktile — un mercado catalogado con al menos 10 jugadores activos a mayo de 2026 ([DevOpsSchool, 27 may 2026](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)) | Licencia comercial |

La pregunta incómoda: **¿qué le queda a Vectra Risk que un banco no pueda obtener
comprando Zest AI (ya integrado a su Temenos, si lo usa) o contratando a cualquiera
de las plataformas de la lista de arriba?**

La respuesta del PVB es "opera dentro de la infraestructura regulada del propio
banco, self-hosted, con conocimiento del crédito de vivienda colombiano
específico". Puede ser cierto. Pero es un diferenciador **de nicho geográfico y de
despliegue**, no de capacidad — y cualquiera de esos vendors con más capital puede
ofrecer despliegue on-premise si un cliente grande se lo exige.

**Contraargumento honesto de Vectra Risk:** ninguno de esos vendors está construido
específicamente para el crédito de vivienda VIS/no VIS colombiano, sus subsidios y
sus tasas certificadas por la Superintendencia. Ese conocimiento de dominio local sí
tarda en replicarse.

**Réplica:** ese conocimiento de dominio es exactamente lo que una integración
local o un partner de implementación regional puede vender **encima** de Zest AI o
FICO Platform, sin que el banco tenga que confiar en un motor de scoring nuevo y no
probado. Vectra Risk no solo compite contra el modelo — compite contra la inercia
de "ya tengo esto integrado".

---

## 2. El riesgo base de la categoría

No encontré una cifra de tasa de fracaso específica para proyectos de scoring de
crédito con IA en banca. **Lo digo explícitamente en vez de forzar una cifra que no
apliqué al dominio correcto** — usar la cifra de "40% de proyectos de IA agéntica
cancelados para 2027" (Gartner, junio de 2025) aquí sería un error de traslado de
dominio: Vectra Risk no es un agente autónomo, es un sistema de scoring con humano
en el loop, y esa cifra mide una categoría distinta.

Lo que sí encontré, con matices de fuente:

- La encuesta anual de EY y el Institute of International Finance (101 bancos, 31
  países) identifica el riesgo crediticio como una de las principales prioridades
  de los CRO para 2026, junto con "acelerar la adopción responsable de la IA"
  (fuente: [PQS, 5 jun 2026, reportando la encuesta EY/IIF](https://pqs.pe/actualidad/economia/la-inteligencia-artificial-y-la-gestion-del-riesgo-crediticio-marcan-la-agenda-de-la-banca-en-2026/)).
  Esto valida que el problema le importa al comprador — pero también significa que
  **todos los vendors de la sección 1 están empujando en la misma ventana de
  atención del CRO al mismo tiempo**.
- Un artículo que cita a BCG (sin que yo haya verificado el reporte primario de
  BCG) afirma que el 66% de los ejecutivos de banca están ambivalentes o
  insatisfechos con su progreso en IA, por falta de talento, prioridades de
  inversión poco claras y ausencia de estrategia de IA responsable; y que Gartner
  atribuye el fracaso de pilotos a arquitectura, gobernanza de datos y modelo
  operativo mal definidos (fuente: [Delto, 9 feb 2026](https://www.delto.com/blog/como-elegir-la-mejor-empresa-para-implementar-ia-generativa-en-tu-banco) —
  **[VERIFICAR contra el reporte primario de BCG/Gartner antes de usar esta cifra
  en el PRD]**).

Si esa cifra del 66% resiste una verificación directa, es una exposición real para
Vectra Risk: gobernanza de datos y modelo operativo mal definidos son precisamente
los puntos donde un producto nuevo, vendido por un equipo pequeño a un banco
mediano, tiende a fallar en el paso de piloto a producción.

---

## 3. La explicabilidad y el monitoreo de sesgo no son un diferenciador

El PVB de Vectra Risk vende "cada decisión sale con su explicación" y "monitoreo de
sesgo como servicio de primera clase" como su ventaja de Trust. El problema: **es
lo que ya vende, de forma nativa y ya integrada, buena parte del mercado
establecido de crédito digital.**

- Zest AI se posiciona explícitamente como fuerte en "explainable AI underwriting"
  y ya está integrado en el core Temenos que muchos bancos medianos usan (sección
  1).
- La lista de las diez plataformas líderes de scoring con IA incluye
  explicabilidad, auditoría y "adverse action support" (la obligación de explicar
  un rechazo al solicitante) como **requisitos de entrada para el segmento
  enterprise**, no como diferenciador de un jugador (fuente: [DevOpsSchool, 27 may 2026](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)).

Cuando explicabilidad y monitoreo de sesgo son el precio de entrada de toda una
categoría de mercado madura, venderlos como el argumento principal de un producto
nuevo es débil ante un comprador informado.

**Lo que sí podría diferenciar** no es *que* Vectra Risk explique sus decisiones,
sino **el grado de soberanía del dato** (self-hosted dentro del propio banco, sin
que el score ni el dato del solicitante salgan de su infraestructura) combinado con
**el conocimiento normativo local específico** (VIS, subsidios, tasas certificadas
por la SFC). Pero eso hay que decirlo así — es un diferenciador estrecho de
despliegue y dominio, no de tecnología de IA.

---

## 4. El moat, examinado en frío

**Afirmación del PVB:** el moat es el registro de explicaciones, el historial de
sesgo monitoreado y la correlación score-desenlace acumulada.

**Tres preguntas que lo debilitan:**

1. **¿Es transferible entre clientes?** El historial de decisiones y su desenlace
   se construye sobre la cartera y la política de originación de un banco
   específico. Que Vectra Risk acierte prediciendo mora en el Banco A no predice
   nada sobre el Banco B, con otra mezcla de clientes, otra política de riesgo y
   otra exposición geográfica. **Si el aprendizaje no se transfiere, no es un moat,
   es onboarding repetido con cada cliente nuevo.**
2. **¿Le importa al comprador día a día?** El CRO firma el contrato pensando en
   reducción de mora y velocidad de originación. El "registro auditable de
   explicaciones" le importa sobre todo al oficial de cumplimiento y al auditor
   externo, que revisan trimestral o anualmente — no a quien usa el producto todos
   los días. Existe el riesgo de que el valor percibido a diario sea menor que el
   valor que Vectra Risk cree estar vendiendo.
3. **¿Sobrevive al cambio de proveedor de core bancario?** Si un banco cliente
   decide migrar o ya usa Temenos con Zest AI nativo, Vectra Risk no compite contra
   un producto inferior: compite contra **la inercia de no tener que integrar nada
   nuevo**. Eso no es un problema técnico de Vectra Risk, es un problema de
   distribución que el PVB no aborda.

---

## 5. El fracaso más probable no es un error de modelo: es la irrelevancia
   silenciosa

El escenario de muerte más probable no es "el modelo discriminó y hubo un escándalo
público" (aunque ese riesgo existe y se trata en la sección 6). Es más aburrido:
**el sistema entrega su explicación y su reporte de sesgo puntualmente, el comité
de crédito los archiva sin leerlos porque de todas formas la decisión ya estaba
tomada con las reglas de siempre, y el contrato se renueva por inercia de
cumplimiento hasta que alguien pregunta si vale lo que cuesta.**

Ese fallo tiene una propiedad desagradable: **las métricas de seguridad se ven
perfectas mientras ocurre.** Cero hallazgos de sesgo, cero
incidentes regulatorios — porque nadie está usando la explicación para nada más que
justificar decisiones ya tomadas por otras razones.

**Implicación de diseño:** la sección 8 del PVB no tiene ninguna métrica que mida
si la explicación **cambia** una decisión o solo la **justifica después**. Sin esa
métrica, Vectra Risk no puede distinguir entre "el comité usa el score" y "el
comité ignora el score y usa el sistema como sello de cumplimiento".

---

## 6. El producto puede legitimar el sesgo que dice vigilar

Este es el argumento más incómodo del documento.

Un modelo entrenado con datos históricos de un sistema de crédito excluyente tiende
a replicar esa exclusión, ahora con mayor velocidad y menor margen de rendición de
cuentas — el patrón está documentado específicamente para crédito digital en
América Latina (fuente:
[Despejando Dudas, 27 abr 2026](https://www.despejandodudas.co/index.php/quienes-somos-despejando-dudas/opinion/5167-el-algoritmo-prestamista-como-la-inteligencia-artificial-esta-redefiniendo-el-acceso-al-credito-en-america-latina) —
nota de opinión, no un estudio primario; tratar con cautela). El patrón general de
que los algoritmos de crédito pueden perpetuar sesgos socioeconómicos preexistentes
está documentado en la literatura académica sobre sesgo algorítmico desde al menos
2016 (O'Neil, referenciado en [LATAM Digital](https://revistalatam.digital/article/22tr02/)).

Vectra Risk propone resolver esto con explicabilidad (SHAP/LIME) y monitoreo de
sesgo (AIF360/Fairlearn). El problema: **la propia literatura de explicabilidad
documenta que estas técnicas son aproximaciones post-hoc, no una lectura directa
del razonamiento del modelo**, y que su implementación práctica trae retos
metodológicos no triviales (fuente: [arXiv 2103.00949](https://arxiv.org/pdf/2103.00949),
que dedica una sección completa a "practical challenges" de implementar SHAP y LIME
en scoring de crédito real). Esto no invalida la técnica, pero sí invalida
venderla como una garantía de transparencia total: **una explicación post-hoc
puede sonar razonable y seguir describiendo mal por qué el modelo decidió lo que
decidió.**

Dos consecuencias que el PVB no aborda:

1. **El dashboard de sesgo puede dar una falsa sensación de control.** Publicar
   una métrica de disparidad <5 puntos porcentuales entre grupos no prueba
   ausencia de discriminación por proxy si las variables alternativas (comportamiento
   transaccional, datos no estructurados) codifican el mismo sesgo de otra forma.
2. **"Usar más datos alternativos" — que el propio PVB cita como buena práctica
   recomendada por Uniandes — puede introducir más proxies de variables protegidas,
   no menos**, si esos datos alternativos (ubicación, patrones de gasto,
   comportamiento digital) correlacionan con las mismas variables socioeconómicas
   que el modelo dice no usar directamente.

**Lo que salvaría el argumento:** que Vectra Risk mida explícitamente la tasa de
aprobación por grupo protegido **antes y después** de incorporar cada nueva fuente
de datos alternativa, no solo el estado agregado del modelo en producción. Si el
PVB no lo hace, el "monitoreo de sesgo" queda como una casilla más de cumplimiento,
no como una defensa real.

> Nota de método: el hallazgo de sesgo algorítmico en crédito es ampliamente
> documentado desde 2016 y no es exclusivo de este producto — es un riesgo
> estructural de cualquier scoring basado en datos históricos, con o sin Vectra
> Risk. La crítica no es "el producto causa el sesgo": es que **vender monitoreo de
> sesgo como si fuera prueba de ausencia de sesgo** es una promesa más fuerte de lo
> que la técnica puede sostener.

---

## 7. Riesgo de seguridad e integridad que el propio diseño no elimina

La arquitectura de microservicios separa `scoring-service` de
`explainability-service` (ver anexo del PVB) precisamente para poder escalarlos y
versionarlos de forma independiente. Esa misma separación abre un hueco de
integridad que el PVB no discute: **si el servicio de explicación se desincroniza
del servicio de scoring** — por una versión de modelo distinta, un despliegue
parcial o un fallo silencioso — el sistema puede seguir entregando una explicación
plausible que ya no corresponde a la decisión real que tomó el score.

Esto es distinto del riesgo típico de inyección de prompts que aplica a agentes que
leen texto no confiable: aquí el riesgo es de **integridad entre dos
microservicios que deberían estar sincronizados y pueden no estarlo**, y nadie
lo notaría porque ambos siguen respondiendo con HTTP 200.

Adicionalmente, exponer valores SHAP detallados por decisión es en sí mismo una
superficie de información: los valores de explicación pueden revelar más sobre la
composición del modelo o de los datos de entrenamiento de lo que el diseño de
privacidad asume — es un área activa de investigación en explicabilidad (fuente
general: los mismos estudios de la sección 6 sobre XAI en crédito discuten esta
tensión entre transparencia y exposición de información). **No encontré un estudio
específico que cuantifique este riesgo para scoring hipotecario; lo señalo como
área a validar con el equipo de seguridad antes de exponer explicaciones
detalladas vía API, no como un hallazgo cerrado.**

---

## 8. Qué cambiaría del PVB

1. **Dejar de vender "explicabilidad + monitoreo de sesgo" como diferenciador
   aislado.** Es tabla estándar del mercado de risk-tech (sección 1 y 3).
2. **Reformular el moat hacia soberanía del dato y conocimiento normativo local
   específico** (VIS, subsidios, tasas certificadas), no hacia la técnica de IA en
   sí — eso es lo que un vendor extranjero como Zest AI o FICO no replica rápido
   entrando a Colombia.
3. **Añadir una métrica de adopción real de la explicación** (¿cambia decisiones o
   solo las justifica después?), no solo de disparidad de sesgo. Sin ella, no se
   puede distinguir el escenario de la sección 5.
4. **Bajar la fuerza del argumento regulatorio.** El PVB actual da a entender que
   hay presión normativa específica sobre explicabilidad de IA en crédito. Lo que
   existe verificablemente son declaraciones del Superintendente y una circular
   general de gestión de riesgos de 2014 (Circular Externa 029), no una norma
   técnica de IA vinculante (ver sección 10).
5. **Decidir explícitamente si el comprador es el banco o el originador tipo LQN.**
   El PVB asume que LQN es solo un canal que trae solicitudes a los bancos, pero la
   investigación muestra que LQN está pasando a originar crédito propio — podría
   ser cliente, competidor o ambos, y el PVB no resuelve esa ambigüedad.
6. **Verificar con datos primarios, no con blogs de vendors, las cifras de mejora
   de aprobación que suelen usarse para justificar este tipo de producto** (ver
   sección 10) antes de citarlas en el PRD.

---

## 9. Veredicto

**Riesgo: alto.** No por debilidad técnica — la arquitectura de microservicios
sobre Kubernetes es razonable y coincide con patrones ya usados en la industria de
MLOps — sino por **estrechez del espacio comercial**: el diferenciador central que
el PVB propone (explicabilidad + monitoreo de sesgo) ya es tabla estándar de un
mercado global maduro, y el competidor local más concreto (LQN) no necesita
comprarle nada a Vectra Risk porque ya tiene datos, capital y una vía directa a
convertirse en originador de crédito.

**Como producto comercial:** necesita reposicionar su moat lejos de la técnica de
IA (que es commodity) y hacia la soberanía del dato y el conocimiento regulatorio
local, y necesita resolver si LQN es aliado o competidor antes de construir nada.

**Como proyecto del curso:** sigue siendo sólido — obliga a tocar microservicios,
Kubernetes, MLOps (KServe/Seldon), explicabilidad, gobernanza de datos y seguridad
de un sistema de decisión regulado, que es exactamente el tipo de arco técnico que
el módulo busca cubrir.

> **La lección que me llevo de esta investigación:** el argumento de "Trust" de un
> producto de IA no es defendible solo porque la explicabilidad y el monitoreo de
> sesgo sean buenas prácticas — lo es solo si **nadie más las está ofreciendo ya
> integradas**. En este mercado, ya lo están.

---

## 10. Afirmaciones descartadas o degradadas por el contraste de fuentes

Registrado a propósito:

| Afirmación de la versión anterior del PVB | Qué encontré al contrastarla |
|---|---|
| "El regulador colombiano ya exige explicabilidad en modelos de riesgo" (implícito en la sección 3 del PVB) | **Sobreestimado.** Lo que verifiqué son declaraciones públicas del Superintendente Financiero (oct 2025) y una circular general de gestión de riesgos de 2014 (Circular Externa 029), no una norma técnica vinculante específica sobre explicabilidad de IA en scoring. La dirección es correcta —el regulador está mirando el tema— pero no es una obligación normativa hoy, como el PVB anterior daba a entender |
| "El AUC-ROC de referencia (>85%) valida que el mercado está listo para modelos de IA en crédito" | **Cierto pero insuficiente.** La cifra del 88,29% (Redalyc) mide desempeño técnico del modelo, no adopción de mercado ni disposición de un banco a comprar un producto externo. Un buen AUC no predice una venta |
| Cifras de mejora de aprobación citadas en blogs de la categoría ("Zest AI +25% aprobaciones", "Upstart +44%", "CreditVidya 25M usuarios con 33% menos mora") | **No las usé como evidencia en este documento.** Provienen de un blog agregador ([neuronimbus.com](https://www.neuronimbus.com/blog/ai-credit-scoring-in-modern-finance)) que cita cifras de marketing de los propios vendors, sin enlace a reporte primario. Quedan fuera del argumento hasta verificarlas contra fuente primaria |
| "40% de proyectos de IA cancelados para 2027" (Gartner, junio 2025) | **Descartada por traslado de dominio.** Esa cifra mide proyectos de **IA agéntica empresarial**, no sistemas de scoring supervisado con humano en el loop. Aplicarla a Vectra Risk habría sido un error de autocitación fuera de dominio |
| "66% de ejecutivos de banca insatisfechos con su progreso en IA" (BCG, citada en sección 2) | **No descartada, pero degradada a fuente secundaria.** La encontré citada en un blog de una consultora ([Delto](https://www.delto.com/blog/como-elegir-la-mejor-empresa-para-implementar-ia-generativa-en-tu-banco)), no en el reporte original de BCG. La uso con esa salvedad explícita, no como dato confirmado |

---

*Material de referencia — Tópicos Especiales en Informática*
