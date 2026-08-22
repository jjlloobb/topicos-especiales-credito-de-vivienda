# Reporte crudo + auditoría — Mercado, dominio y tecnología (Vectra Risk)

> **Qué es este documento.** Es el reporte que produjo la primera pasada de
> investigación (búsqueda web, 15 de agosto de 2026) sobre el mercado de crédito de
> vivienda, el ecosistema tecnológico de scoring con IA sobre Kubernetes, y la
> regulación aplicable. Se presenta **tal como salió**, sin corregir, seguido de una
> **auditoría** que contrasta cada afirmación contra la fuente primaria disponible.
>
> `pvb.md`, `mercado.md` y `overview.md` solo usan lo que sobrevivió esta auditoría.
> Lo que no la resistió está documentado aquí, con el nombre del error.

---

## PARTE 1 — Reporte crudo (sin auditar)

### 1.1 Tamaño del mercado

El crédito de vivienda en Colombia mueve una cartera de $153,2 billones de pesos,
con crecimiento de 11,2% anual, y el país tiene margen de profundización frente a
Chile, Costa Rica y Brasil. El mercado global de "AI credit scoring" está valorado
entre USD 1.900M y USD 28.900M dependiendo de la fuente, con tasas de crecimiento
anual de 12% a 26%. **El 73% de los bancos colombianos ya usa algún componente de
IA en su proceso de originación de crédito de vivienda**, y se espera que esa cifra
suba a 90% para 2028.

### 1.2 Regulación

La Superintendencia Financiera de Colombia exige explicabilidad algorítmica en
modelos de scoring de crédito desde 2023, como parte de su marco de supervisión de
IA. El Banco de Pagos Internacionales (BIS) estimó en 2024 que **la adopción
responsable de IA en scoring reduce el riesgo sistémico del sector financiero en
un 15%**, validando la dirección regulatoria de exigir explicabilidad.

### 1.3 Ecosistema tecnológico

KServe, Kubeflow y Seldon Core son proyectos CNCF que cubren el serving de modelos
en Kubernetes. AI Fairness 360 de IBM y Fairlearn de Microsoft son también
proyectos CNCF de gobernanza de fairness. Juntos cubren toda la capa de
infraestructura necesaria para un motor de scoring explicable.

### 1.4 Competencia

Zest AI reporta que sus clientes bancarios aumentan sus tasas de aprobación en 25%
sin incrementar el riesgo de default, gracias a su integración nativa con Temenos
Loan Origination. LQN Hipotecas, la proptech colombiana más grande del sector,
procesa el 60% de las originaciones hipotecarias digitales del país y acaba de
recibir US$12M en capital para expandirse a scoring propio.

### 1.5 Estudios de acuerdo modelo-humano

Estudios de acuerdo entre modelos de IA y analistas de crédito humanos muestran una
concordancia del 82% en decisiones de scoring hipotecario, comparable al acuerdo
inter-analista humano, lo que sugiere que los modelos de IA ya están a la par del
juicio experto en este dominio.

---

## PARTE 2 — Auditoría

Cada afirmación de la Parte 1 se revisó contra búsqueda directa de la fuente
primaria o la fuente más cercana disponible. Resultado, punto por punto:

### 1.1 Tamaño del mercado

- **Cartera de $153,2 billones y crecimiento de 11,2% anual: CONFIRMADO.** Fuente
  primaria trazable: [Valora Analitik, 21 may 2026, citando a Colombia Fintech y
  DANE](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/).
- **Rango USD 1.900M–28.900M para el mercado global de AI credit scoring:
  CONFIRMADO COMO CONTRADICTORIO, no como un rango coherente.** Encontré tres
  reportes de firmas de market research (Intel Market Research, HTF Market
  Intelligence, Technavio) que pretenden medir la misma categoría para períodos
  comparables y se contradicen entre sí por más de 5x, sin metodología pública. El
  reporte crudo presenta esto como si fuera un "rango razonable" cuando en realidad
  es una señal de que **ninguna de estas cifras es confiable individualmente**. Ver
  desarrollo completo en `mercado.md`, sección 1.
- **"El 73% de los bancos colombianos ya usa IA en originación de vivienda, subiendo
  a 90% para 2028": DESCARTADA. No existe fuente.** No encontré ninguna nota de
  prensa, encuesta o reporte que respalde esta cifra específica para Colombia. Es
  el mismo tipo de cifra que suena plausible y que ningún reporte real sostiene —
  el patrón clásico de una estadística inventada por una IA generativa sin
  verificación. **No aparece en ningún documento derivado de este proyecto.**

### 1.2 Regulación

- **"La SFC exige explicabilidad algorítmica en scoring de crédito desde 2023":
  DESCARTADA POR SOBREESTIMACIÓN.** Lo que sí verifiqué: una Circular Básica
  Jurídica general de gestión de riesgos (Circular Externa 029 de 2014, no de
  2023) y declaraciones públicas del Superintendente Financiero en octubre de 2025
  sobre la necesidad de incorporar variables de capacidad de pago
  ([Superintendencia Financiera de Colombia, 14 oct 2025](https://www.superfinanciera.gov.co/publicaciones/10115852/el-papel-de-la-inteligencia-artificial-en-la-transformacion-de-la-supervision-financiera/)).
  No hay una norma técnica vinculante específica de 2023 sobre explicabilidad de
  IA. El reporte crudo inventó tanto la fecha como el carácter vinculante de la
  norma.
- **"El BIS estimó que la IA en scoring reduce el riesgo sistémico en 15%":
  DESCARTADA — DIRECCIÓN INVERTIDA Y CIFRA FABRICADA.** El paper real del BIS
  (Instituto de Estabilidad Financiera, 12 de diciembre de 2024) dice lo contrario
  en espíritu: la IA **exacerba** riesgos existentes (modelo, crédito, privacidad),
  no los reduce, y no cuantifica una reducción del 15% de nada
  ([Global Regulation Tomorrow, 13 dic 2024](https://www.regulationtomorrow.com/2024/12/bis-paper-regulating-ai-in-the-financial-sector-recent-developments-and-main-challenges/);
  confirmado por [International Banker, 30 abr 2025](https://internationalbanker.com/technology/banks-ought-to-be-aware-of-the-risks-arising-from-ai-adoption/)).
  Es un error de **dirección invertida**: el reporte crudo tomó un hallazgo
  cauteloso del BIS y lo convirtió en un número optimista inventado.

### 1.3 Ecosistema tecnológico

- **"KServe, Kubeflow y Seldon Core son proyectos CNCF": PARCIALMENTE FALSA —
  ERROR DE GOBERNANZA.** Solo **KServe** es CNCF Incubating (desde noviembre de
  2025, confirmado por [CNCF](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)).
  **Kubeflow** aplicó a CNCF en 2022 pero no encontré confirmación de que la
  transferencia se completara — sigue asociado a Linux Foundation AI & Data en la
  fuente más reciente que pude verificar. **Seldon Core es un producto open source
  propiedad de la empresa Seldon, sin gobernanza de fundación en absoluto.** Tratar
  a los tres como "proyectos CNCF" homogéneos es un error de gobernanza: la
  popularidad y la madurez formal no son lo mismo, y aquí ni siquiera comparten el
  mismo tipo de gobernanza. Ver tabla corregida en `overview.md`, sección 2.
- **"AIF360 y Fairlearn son proyectos CNCF": FALSA.** AIF360 es de IBM y Fairlearn
  es de Microsoft — ninguno de los dos pasó por el proceso de la CNCF. Son
  proyectos open source patrocinados por una sola empresa, un perfil de riesgo de
  continuidad distinto (no ausente) al de un proyecto con gobernanza multi-
  organización.

### 1.4 Competencia

- **"Zest AI: +25% en aprobaciones sin subir el riesgo": SIN VERIFICAR CONTRA
  FUENTE PRIMARIA — mantenida con máxima cautela.** Encontré esta cifra en un blog
  agregador de la categoría ([neuronimbus.com](https://www.neuronimbus.com/blog/ai-credit-scoring-in-modern-finance)),
  no en un reporte o comunicado de Zest AI. Lo que sí confirmé de forma primaria es
  la integración nativa de Zest AI con Temenos Loan Origination, anunciada el 29 de
  abril de 2025 ([Zest AI / Temenos](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)).
  La cifra de +25% no se usa en ningún documento derivado de este proyecto.
- **"LQN procesa el 60% de las originaciones hipotecarias digitales del país":
  DESCARTADA. No encontré esa cifra en ninguna fuente.** Lo que sí verifiqué:
  80.000+ operaciones hipotecarias procesadas, red de 900+ brokers, y una ronda de
  US$12M cerrada en noviembre de 2025 ([Forbes Colombia, 6 nov 2025](https://forbes.co/2025/11/06/emprendedores/lqn-recibe-us12-millones-para-lanzar-creditos-con-garantia-hipotecaria)).
  El "60% de mercado" es una cifra de participación de mercado que ninguna fuente
  respalda y que el reporte crudo agregó sin base — es el tipo de afirmación de
  cuota de mercado sin fuente que hay que descartar por sistema, sin importar qué
  tan bien argumentado suene el resto del reporte.

### 1.5 Estudios de acuerdo modelo-humano

- **"82% de concordancia entre modelos de IA y analistas humanos en scoring
  hipotecario, comparable al acuerdo inter-analista": DESCARTADA POR TRASLADO DE
  DOMINIO, posiblemente el hallazgo más importante de esta auditoría.** No
  encontré ningún estudio que mida específicamente concordancia modelo-humano en
  scoring de **crédito de vivienda**. Esta cifra, si existe en algún estudio real,
  probablemente mide otro tipo de decisión (crédito de consumo, tarjetas, u otro
  dominio no financiero) y fue trasladada sin declararlo — **es un error clásico
  de traslado de dominio**: cifras de acuerdo LLM-humano en dominios como legal,
  médico o financiero general, tomadas de su contexto original y aplicadas a un
  dominio que ningún estudio citado midió. La cifra de AUC-ROC de 88,29% que sí uso
  en `pvb.md` y `mercado.md` es distinta y sí
  está anclada a un estudio específico sobre datos colombianos
  ([Redalyc](https://www.redalyc.org/journal/5537/553768213005/html/)) — mide
  desempeño del modelo, no acuerdo con un humano, y no debe confundirse con la
  cifra descartada aquí.

---

## Resumen de la auditoría

| Afirmación del reporte crudo | Veredicto |
|---|---|
| Cartera hipotecaria $153,2 billones, +11,2% anual | ✅ Confirmada, fuente primaria trazable |
| Rango de mercado global AI credit scoring USD 1.900M–28.900M | ⚠️ Las fuentes se contradicen entre sí; no usar como cifra única |
| 73% de bancos colombianos ya usa IA en originación de vivienda | ❌ Descartada, sin fuente |
| SFC exige explicabilidad desde 2023 | ❌ Descartada, sobreestimación de una circular general de 2014 |
| BIS: IA en scoring reduce riesgo sistémico 15% | ❌ Descartada, dirección invertida y cifra fabricada |
| KServe, Kubeflow y Seldon Core son proyectos CNCF | ⚠️ Solo KServe lo es; Kubeflow sin confirmar, Seldon no lo es |
| AIF360 y Fairlearn son proyectos CNCF | ❌ Descartada, son proyectos de IBM y Microsoft respectivamente |
| Zest AI +25% aprobaciones sin subir riesgo | ⚠️ Fuente secundaria (blog), no usar sin verificar contra Zest AI directamente |
| LQN procesa 60% de originaciones digitales del país | ❌ Descartada, sin fuente |
| 82% de concordancia modelo-humano en scoring hipotecario | ❌ Descartada, error de traslado de dominio |

> **Nota de método:** si este reporte se hubiera usado sin auditar, `pvb.md` habría afirmado con aire de autoridad que la
> Superintendencia ya exige explicabilidad por norma, que el BIS certificó una
> reducción de riesgo del 15%, y que los modelos de IA ya igualan a los analistas
> humanos en scoring hipotecario. Las tres habrían sido afirmaciones convincentes,
> bien escritas, y falsas.

---

*Material de referencia — Tópicos Especiales en Informática*
