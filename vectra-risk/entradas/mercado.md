# Análisis de mercado — scoring de riesgo con IA para crédito de vivienda

> Documento de contexto para el caso de estudio **Vectra Risk**.
> Toda cifra externa lleva fuente y fecha, obtenida por búsqueda web el 15 de agosto
> de 2026. Donde varias fuentes se contradicen entre sí sin metodología pública, lo
> señalo explícitamente en vez de elegir la que más convenga al caso.

---

## 1. El mercado que se cita cuando se quiere convencer

Estas son las cifras que aparecen en cualquier presentación de la categoría "IA
para scoring de crédito". Hay que leerlas con cuidado antes de repetirlas.

| Cifra | Valor | Fuente |
|---|---|---|
| Mercado global de "AI credit scoring" en 2025 | **USD 1.900M** | [Intel Market Research, 31 may 2026](https://www.intelmarketresearch.com/ai-credit-scoring-market-47029) |
| Mercado global de "AI-Driven Credit Scoring", mismo período | **USD 9.800M** | [HTF Market Intelligence, 10 dic 2025](https://www.htfmarketintelligence.com/report/global-ai-driven-credit-scoring-market) |
| Mercado global de "AI-based Credit Decision Engines" 2025-2030 | crecimiento de **USD 6.960M** | [Technavio, 10 mar 2026](https://www.technavio.com/report/ai-based-credit-decision-engines-market-industry-analysis) |
| Mercado de "AI in Finance" 2024 → 2030 | USD 38.360M → **USD 190.330M** | [Neontri, 26 jun 2026](https://neontri.com/blog/ai-credit-scoring/) |
| Cartera hipotecaria de vivienda en Colombia, Q4 2025 | **$153,2 billones COP**, +11,2% anual | [Valora Analitik, 21 may 2026](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/) |

**Advertencia que hay que poner en la misma diapositiva que la tabla anterior:**
las primeras tres cifras pretenden medir prácticamente lo mismo — el mercado global
de scoring crediticio con IA — para el mismo año, y **varían entre sí por un factor
de más de 5x** (de USD 1.900M a USD 9.800M) sin que ninguna reporte metodología
pública verificable. Son informes de firmas de "market research" que venden el
reporte completo por separado y publican solo el titular en notas de prensa. Esto
no es evidencia de que el mercado sea pequeño o grande: es evidencia de que **estas
cifras específicas no son confiables** y no deberían usarse para dimensionar el
caso de negocio de Vectra Risk. La única cifra de esta tabla con fuente
verificable y metodología pública trazable es la del mercado hipotecario
colombiano.

---

## 2. La cifra que hay que poner al lado, y que sí resistió el contraste

> El 12 de diciembre de 2024, el Instituto de Estabilidad Financiera del Banco de
> Pagos Internacionales (BIS) publicó un documento sobre IA en el sector
> financiero. Su conclusión central: **la IA exacerba riesgos ya existentes —
> riesgo de modelo, riesgo crediticio, privacidad de datos — pero no introduce
> riesgos fundamentalmente nuevos**, salvo los específicos de la IA generativa
> (alucinación, antropomorfismo). Y un punto crítico para el argumento regulatorio
> de Vectra Risk: **la mayoría de las autoridades financieras no ha emitido
> regulación de IA específica para instituciones financieras, porque consideran
> que los marcos existentes ya cubren la mayoría de estos riesgos**
> (fuente: [Global Regulation Tomorrow, resumiendo el paper del BIS, 13 dic 2024](https://www.regulationtomorrow.com/2024/12/bis-paper-regulating-ai-in-the-financial-sector-recent-developments-and-main-challenges/);
> confirmado de forma independiente por [International Banker, 30 abr 2025](https://internationalbanker.com/technology/banks-ought-to-be-aware-of-the-risks-arising-from-ai-adoption/),
> que cita directamente el texto del BIS sobre riesgo de modelo, riesgo crediticio
> y riesgos de conducta/protección al consumidor).

Esto **corrige y refuerza a la vez** un hallazgo de `critica.md`: no es que el
argumento regulatorio de Vectra Risk esté mal encaminado — el BIS confirma que
riesgo de modelo y riesgo crediticio en IA son preocupaciones reales y
documentadas a nivel global. Pero **el mecanismo de presión no es una norma nueva
de IA que obligue a explicar decisiones de crédito**: es la aplicación de marcos de
gestión de riesgo y model risk management que ya existen, y que un banco ya debería
estar cumpliendo con o sin IA de por medio.

**Implicación para Vectra Risk:** el argumento de venta no puede ser "la regulación
de IA lo exige" (no existe esa norma específica, en Colombia ni en la mayoría de
jurisdicciones, según el BIS). El argumento correcto es **"su marco de gestión de
riesgo ya vigente exige esto, y su modelo de scoring actual probablemente no lo
está cumpliendo del todo"** — es un argumento más débil para generar urgencia, pero
más honesto y más difícil de refutar en una reunión con el CRO.

---

## 3. Estructura competitiva

### Capa gratuita (la que define el precio de todo lo demás)

Librerías y proyectos open source que ya cubren buena parte de lo que Vectra Risk
propone como valor:

- **SHAP y LIME** — explicabilidad post-hoc por decisión, documentadas
  extensamente en la literatura académica de scoring de crédito ([arXiv 2103.00949](https://arxiv.org/pdf/2103.00949); [arXiv 2506.19383](https://arxiv.org/pdf/2506.19383)).
- **AI Fairness 360 (IBM)** — más de 70 métricas de sesgo y 9 algoritmos de
  mitigación, con casos de uso documentados específicamente para *credit-worthiness*
  ([AIF360](https://aif360.res.ibm.com/)).
- **Fairlearn (Microsoft)** — toolkit de fairness comparable, referenciado en la
  misma literatura ([arXiv 2205.06922](https://arxiv.org/pdf/2205.06922)).
- **KServe** (CNCF Incubating desde noviembre 2025) y **Seldon Core v2** (con
  drift detection incorporado) — serving y monitoreo de modelos en Kubernetes
  ([CNCF, 11 nov 2025](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)).

> **Este es el hecho competitivo más importante del análisis:** cualquier producto
> comercial de esta categoría tiene que justificar
> por qué alguien pagaría por una orquestación de piezas que, individualmente, ya
> existen gratis y están mantenidas por IBM, Microsoft y la CNCF.

### Capa comercial — más poblada de lo que el PVB original asumía

| Empresa / producto | Posición | Señal verificada |
|---|---|---|
| **Zest AI** | Scoring y underwriting explicable | **Integración nativa con Temenos Loan Origination**, anunciada el 29 de abril de 2025 ([Zest AI / Temenos](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)) |
| **FICO Platform** | Suite enterprise de decisión crediticia | Usada por Nationwide Building Society (~23M clientes, Reino Unido) para implementar estrategias de riesgo 50% más rápido que hace cinco años ([EmpreFinanzas, ago 2026](https://emprefinanzas.com.mx/2026/08/13/la-inteligencia-artificial-en-la-transformacion-bancaria-la-brecha-real-no-es-la-tecnologia-sino-la-confianza-a-gran-escala/)) |
| **Experian Ascend, DataRobot, Provenir, Taktile** | Plataformas de decisión y analítica crediticia | Catalogadas activamente como top-10 del sector a mayo 2026 ([DevOpsSchool](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)) |
| **LQN Hipotecas** | Originador tecnológico colombiano con IA propia | 80.000+ operaciones hipotecarias procesadas, 900+ brokers, US$12M de capital (nov 2025) ([Forbes Colombia](https://forbes.co/2025/11/06/emprendedores/lqn-recibe-us12-millones-para-lanzar-creditos-con-garantia-hipotecaria)) |

**Lectura de esta tabla:** no hay un espacio vacío de "scoring explicable para
crédito" a nivel global — hay un mercado maduro con jugadores de escala (FICO,
Zest AI) ya integrados en los mismos cores bancarios (Temenos) que Vectra Risk
asumía como punto de entrada. El espacio real, si existe, es más estrecho y más
local de lo que sugiere el tamaño del mercado global.

---

## 4. Dónde queda el espacio

Cruzando las capas anteriores, lo que queda como espacio potencialmente defendible
es más angosto que en la primera versión del PVB:

1. **Soberanía del dato dentro de la infraestructura del banco colombiano** —
   ningún vendor global revisado (Zest AI, FICO, Experian) publicita
   explícitamente despliegue self-hosted dentro del clúster del cliente como su
   modelo estándar; suelen operar como servicio gestionado o SaaS.
   **[VERIFICAR: confirmar directamente con cada vendor si ofrecen on-premise real
   para banca latinoamericana, no asumirlo por omisión]**.
2. **Conocimiento normativo y de producto específico del crédito de vivienda
   colombiano** (VIS, subsidios, tasas certificadas por la SFC) — ningún vendor
   global lo trae de fábrica.
3. **El tramo entre el modelo que el área de riesgo ya construyó y su aprobación
   por el comité** — el cliente ya tiene la mitad de la solución (el modelo) y está
   atascado en la gobernanza para llevarlo a producción, no en la falta de
   tecnología.

**Lo que NO es espacio defendible:** la técnica de explicabilidad o de monitoreo de
sesgo en sí misma. Está resuelta, es gratis en su forma de librería, y está
empaquetada comercialmente por jugadores con muchísimo más capital y ya integrada
en el core bancario que muchos clientes potenciales ya usan.

---

## 5. El dolor operativo, con datos que resistieron el contraste

**El mercado de crédito de vivienda colombiano es real y está desatendido en
penetración, no en apetito.**
La cartera hipotecaria equivale a apenas el 7,4% del PIB, frente al 26,3% de Chile,
16% de Costa Rica y 9% de Brasil, y solo el 3,3% de los colombianos tiene un
crédito hipotecario o leasing habitacional activo, aunque el 34,8% ya tiene
vivienda propia totalmente paga (fuente: [Valora Analitik, 21 may 2026](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/)).

**La competencia tecnológica local ya movió la vara de velocidad.**
LQN Hipotecas promete desembolsos completos en 10 días frente a un trámite
tradicional que superaba los 100 días, y afirma haber reducido en 40% los tiempos
de procesamiento con su plataforma ([Portafolio, 4 mar 2025](https://www.portafolio.co/mis-finanzas/creditos/lqn-hipotecas-desembolso-10-000-creditos-superando-los-1-5-billones-625098);
[LatamFintech, 7 nov 2025](https://www.latamfintech.co/articles/fintech-colombiana-lqn-capta-us-12-millones-para-lanzar-creditos-con-garantia-hipotecaria)).

**El desempeño técnico del scoring con IA en Colombia ya está documentado
académicamente, no es una apuesta especulativa.**
Modelos de árboles de decisión, redes neuronales y SVM entrenados sobre datos de
mora de entidades colombianas alcanzan hasta 88,29% de AUC-ROC prediciendo riesgo
de no pago (fuente: [Redalyc](https://www.redalyc.org/journal/5537/553768213005/html/)
— **[VERIFICAR fecha exacta de publicación, no visible en la página]**).

**El riesgo de sesgo algorítmico en crédito digital no es hipotético en la región.**
El patrón de que un modelo entrenado con datos históricos de un sistema excluyente
tiende a replicar esa exclusión está señalado específicamente para crédito digital
en América Latina (fuente: [Despejando Dudas, 27 abr 2026](https://www.despejandodudas.co/index.php/quienes-somos-despejando-dudas/opinion/5167-el-algoritmo-prestamista-como-la-inteligencia-artificial-esta-redefiniendo-el-acceso-al-credito-en-america-latina) —
nota de opinión, tratar con cautela) y el patrón técnico de "redlining digital" vía
variables proxy está documentado de forma más general en la literatura de
auditoría de algoritmos ([Parada Visual, 6 nov 2025](https://www.paradavisual.com/auditoria-algoritmos-ia-eliminar-sesgos-discriminatorios-servicios/)).

### Y el dato incómodo, que es el más importante para Vectra Risk

La explicabilidad post-hoc que Vectra Risk propone como núcleo de su producto
**no es una lectura directa del razonamiento del modelo, es una aproximación con
retos de implementación documentados** en la propia literatura técnica que estudia
SHAP y LIME aplicados a scoring de crédito ([arXiv 2103.00949](https://arxiv.org/pdf/2103.00949)).
Esto no descalifica la técnica —sigue siendo el estándar de la industria—, pero
significa que **"explicable" no es sinónimo de "verificablemente correcto"**, y
venderlo como garantía absoluta ante un comité de riesgo sería una promesa más
fuerte de lo que la técnica puede sostener. Ver el desarrollo completo de este
argumento en `critica.md`, sección 6.

---

## 6. Riesgo geográfico y de segmento

El ICP de Vectra Risk apunta exclusivamente a Colombia, precisamente para evitar
extender el beachhead a mercados sin el mismo respaldo regulatorio y competitivo
verificado. Pero incluso acotado a un solo país, hay un hueco que hay que declarar:

**No encontré datos públicos verificables sobre cuántos bancos medianos o
cooperativas financieras colombianas operan Kubernetes en producción hoy**, ni
sobre qué proporción de ellas ya tiene un modelo de scoring de vivienda construido
internamente sin llegar a producción. Ambos supuestos —pilares de las señales de
calificación del ICP— son inferencias razonables a partir de tendencias generales
de la industria financiera (ver sección 5, McKinsey/EY sobre adopción de IA en
banca), **no hallazgos de campo verificados**. Es exactamente el tipo de hueco que
`icp.md` ya declara explícitamente en su señal de calificación #1, y que aquí se
confirma: no hay cifra pública que lo cierre.

---

## 7. Qué no se pudo verificar

Descartado o degradado del análisis por no resistir el contraste:

- **Las cifras específicas de tamaño del mercado global de "AI credit scoring"**
  (USD 1.900M, 9.800M, 28.900M para períodos similares): se contradicen entre sí
  por un factor de más de 5x sin metodología pública. Ver sección 1.
- **"AI podría ahorrarle a la banca global más de USD 1 billón para 2030" y
  "crecimiento del 67% hasta USD 44.000M para 2028"**: provienen de un blog de un
  proveedor de scoring ([GratifyPay](https://www.gratifypay.com/resources/blog/does-ai-credit-scoring-really-matter-in-2026-here39s-what-the-data-says-15)),
  sin enlace a un reporte primario ni metodología. No las usé como evidencia en
  ningún otro documento de este proyecto.
- **Cifras de mejora de aprobación de crédito citadas por vendors** ("Zest AI
  clientes +25% aprobaciones", "Upstart +44%", "CreditVidya 25M usuarios con 33%
  menos mora"): son cifras de marketing de los propios proveedores, reportadas por
  un blog agregador sin fuente primaria. Quedan fuera del argumento de este
  documento.
- **66% de ejecutivos de banca insatisfechos con su progreso en IA (BCG)**: citada
  en `critica.md` con la salvedad explícita de que la encontré en un blog de
  consultora, no en el reporte original de BCG. La mantengo marcada como fuente
  secundaria en ese documento y no la repito aquí como si fuera confirmada.

---

*Material de referencia — Tópicos Especiales en Informática*
