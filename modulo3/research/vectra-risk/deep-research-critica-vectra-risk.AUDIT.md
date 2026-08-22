# Reporte crudo + auditoría — Crítica adversarial (Vectra Risk)

> **Qué es este documento.** Es el reporte que produjo la investigación adversarial
> (búsqueda web, 15 de agosto de 2026), instruida explícitamente para **atacar**
> el caso de Vectra Risk: buscar por qué fallaría, quién lo está comoditizando
> gratis, y qué riesgo lo mata. Se presenta tal como salió, sin corregir, seguido
> de la auditoría que contrasta cada afirmación contra fuente primaria.
>
> `critica.md` solo usa lo que sobrevivió esta auditoría. Lo que no la resistió
> está documentado aquí, con el nombre del error.

---

## PARTE 1 — Reporte crudo (sin auditar)

### 1.1 Comoditización

Explicabilidad y monitoreo de sesgo en scoring de crédito ya son commodity: SHAP,
LIME, AIF360 y Fairlearn son gratuitos, y Zest AI ya integra explicabilidad de
forma nativa en Temenos Loan Origination desde abril de 2025. El mercado de
plataformas de decisión crediticia con IA tiene al menos diez jugadores activos
(FICO, Zest AI, Experian Ascend, DataRobot, Provenir, entre otros).

### 1.2 Riesgo base de la categoría

**Más del 40% de los proyectos de IA agéntica empresariales serán cancelados para
finales de 2027** (Gartner, junio de 2025), por ROI no demostrable, costos de
inferencia y complejidad de gobernanza. Vectra Risk, como todo proyecto de IA
empresarial, está expuesto a esta tasa de cancelación.

### 1.3 Competencia local

LQN Hipotecas es una amenaza directa: plataforma con IA, 80.000+ operaciones
procesadas, 900+ brokers, capital reciente de US$12M. **Estudios muestran que el
55% de los modelos de scoring con IA construidos internamente en bancos
latinoamericanos nunca llegan a producción**, lo que sugiere que Vectra Risk
compite en un mercado donde la ejecución, no la idea, es la barrera real.

### 1.4 Insatisfacción con la IA en banca

Según BCG, el 66% de los ejecutivos de banca están ambivalentes o insatisfechos con
su progreso en IA, por falta de talento, prioridades de inversión poco claras y
ausencia de estrategia de IA responsable. Gartner atribuye el fracaso de pilotos a
mala definición de arquitectura, gobernanza de datos y modelo operativo.

### 1.5 Riesgo regulatorio

**La Superintendencia Financiera de Colombia ya ha sancionado a al menos dos
entidades financieras por sesgo algorítmico en modelos de scoring, con multas
promedio de $2,3 millones de dólares.** Esto demuestra que el riesgo de
cumplimiento que Vectra Risk mitiga es real y ya se materializó en el mercado
colombiano.

### 1.6 El moat no es defendible

El historial de decisiones y desenlaces que Vectra Risk propone como moat no es
transferible entre bancos clientes, porque cada cartera tiene su propia política de
originación y mezcla de riesgo.

---

## PARTE 2 — Auditoría

### 1.1 Comoditización

- **CONFIRMADA en su totalidad.** SHAP, LIME, AIF360 (IBM) y Fairlearn (Microsoft)
  son efectivamente gratuitos y están documentados en la literatura académica de
  scoring de crédito ([arXiv 2103.00949](https://arxiv.org/pdf/2103.00949);
  [AIF360](https://aif360.res.ibm.com/); [arXiv 2205.06922](https://arxiv.org/pdf/2205.06922)).
  La integración de Zest AI con Temenos Loan Origination está confirmada con fecha
  exacta ([Zest AI / Temenos, 29 abr 2025](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)).
  El listado de al menos diez jugadores en la categoría también está confirmado
  ([DevOpsSchool, 27 may 2026](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)).
  Esta sección pasa la auditoría sin cambios y sostiene la sección 1 de `critica.md`.

### 1.2 Riesgo base de la categoría

- **LA CIFRA ES REAL, PERO SU APLICACIÓN AQUÍ ES UN ERROR DE TRASLADO DE DOMINIO —
  DESCARTADA PARA VECTRA RISK.** La cifra del 40% de cancelación de proyectos de
  IA agéntica sí es de Gartner (junio de 2025). El error es aplicarla sin más a
  Vectra Risk: **Vectra Risk no es un agente autónomo de IA agéntica — es un
  sistema de scoring supervisado con humano en el loop**, una categoría distinta a
  la que Gartner midió. Es un error clásico de traslado de dominio. **Esta cifra
  no se usa en
  `critica.md`** — la sección 2 de ese documento declara explícitamente que
  reutilizarla habría sido este mismo error, y en su lugar usa la encuesta EY/IIF
  de 2026 sobre prioridades de CRO como evidencia más relevante para esta
  categoría específica.

### 1.3 Competencia local

- **LQN Hipotecas: CONFIRMADA** con los datos ya verificados en otros documentos
  (80.000+ operaciones, 900+ brokers, US$12M en noviembre de 2025).
- **"55% de los modelos de scoring con IA construidos internamente en bancos
  latinoamericanos nunca llegan a producción": DESCARTADA. No existe fuente.** No
  encontré ningún estudio, encuesta o reporte que respalde esta cifra específica
  para LatAm. Es una cifra que suena plausible en el contexto de la conversación
  sobre "pilotitis" en banca (McKinsey sí usa ese término de forma cualitativa,
  [EbankingNews, jul 2026](https://www.ebankingnews.com/2026/07/20/de-asistentes-a-operadores-autonomos-mckinsey-revela-el-salto-definitivo-de-la-inteligencia-artificial-en-el-sector-bancario/)),
  pero el 55% específico no aparece en ninguna fuente que pude localizar. **No se
  usa en ningún documento derivado.**

### 1.4 Insatisfacción con la IA en banca

- **CIERTA PERO DEGRADADA A FUENTE SECUNDARIA — no descartada, tratada con
  cautela.** Encontré esta cifra citada en un blog de una consultora
  ([Delto, 9 feb 2026](https://www.delto.com/blog/como-elegir-la-mejor-empresa-para-implementar-ia-generativa-en-tu-banco))
  que a su vez la atribuye a BCG, sin que yo haya podido acceder al reporte
  primario de BCG para confirmarla directamente. Es distinto de una cifra
  descartada: no encontré evidencia de que sea falsa, solo no pude verificarla
  contra la fuente original. `critica.md`, sección 2, la usa exactamente con esta
  salvedad — como una exposición a validar, no como un hecho confirmado.

### 1.5 Riesgo regulatorio

- **DESCARTADA POR COMPLETO — CIFRA FABRICADA, la más grave de este reporte.** No
  encontré ninguna nota de prensa, comunicado de la Superintendencia Financiera de
  Colombia, ni cobertura de medios sobre sanciones específicas por sesgo
  algorítmico en scoring de crédito, y mucho menos una cifra de multa promedio de
  $2,3 millones de dólares. Esta afirmación tiene la forma exacta de una cifra
  inventada que "suena a validación": específica, con decimales, con apariencia de
  estar sacada de un comunicado oficial, y sin ninguna fuente real detrás. **Usar
  esta cifra habría
  sido el error más grave de todo el proyecto: habría afirmado con aire de
  autoridad que el regulador colombiano ya sancionó por este motivo exacto, cuando
  no encontré ninguna evidencia de que eso haya ocurrido.** No aparece en ningún
  documento derivado de este proyecto.

### 1.6 El moat no es defendible

- **CONFIRMADA como argumento, con el mismo razonamiento aplicado
  independientemente a Vectra Risk.** El razonamiento de que el historial de
  decisiones no transfiere entre clientes con distintas políticas de originación
  es lógicamente sólido, aunque no depende de una cifra externa verificable — es un
  argumento estructural, no una estadística. Se mantiene en `critica.md`, sección
  4, presentado como argumento, no como dato.

---

## Resumen de la auditoría

| Afirmación del reporte crudo | Veredicto |
|---|---|
| Explicabilidad y monitoreo de sesgo ya son commodity (SHAP/LIME/AIF360/Fairlearn/Zest AI-Temenos) | ✅ Confirmada, múltiples fuentes primarias |
| 40% de proyectos de IA agéntica cancelados para 2027 aplica a Vectra Risk | ❌ Cifra real, pero traslado de dominio incorrecto — no aplica a scoring supervisado |
| LQN Hipotecas como amenaza competitiva | ✅ Confirmada |
| 55% de modelos de scoring en LatAm nunca llegan a producción | ❌ Descartada, sin fuente |
| 66% de ejecutivos de banca insatisfechos con su progreso en IA (BCG) | ⚠️ Fuente secundaria, no descartada pero sin confirmar contra reporte primario |
| SFC sancionó bancos por sesgo algorítmico, multa promedio $2,3M USD | ❌ Descartada — cifra fabricada, sin ninguna fuente localizable |
| El moat de historial de decisiones no es transferible entre clientes | ✅ Confirmada como argumento estructural |

> **Nota de método:** dos de las siete afirmaciones de este reporte crudo eran
> cifras inventadas con apariencia de solidez (la tasa de fracaso de modelos en
> LatAm y, sobre todo, la sanción regulatoria con multa promedio). Si se hubieran
> usado sin auditar, `critica.md` habría presentado como hecho consumado que el
> regulador colombiano ya castigó a bancos por este motivo exacto — el tipo de
> afirmación que más credibilidad falsa le da a un documento de crítica, porque
> parece la evidencia más contundente posible. Es precisamente la que había que
> verificar con más cuidado, no con menos.

---

*Material de referencia — Tópicos Especiales en Informática*
