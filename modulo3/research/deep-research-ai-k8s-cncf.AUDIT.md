# Auditoría del reporte `deep-research-ai-k8s-cncf.md`

**Qué es este archivo.** El reporte de deep research que lo acompaña es un **insumo**,
no un resultado. Este documento verifica sus afirmaciones contra fuentes primarias
antes de que cualquiera de ellas entre al material del curso.

**Regla que aplica aquí:** ningún dato del reporte se cita en `overview.md`,
`mercado.md`, `icp.md`, `pvb.md` ni `critica.md` sin aparecer abajo con veredicto
CONFIRMADO. Un reporte fluido con URLs reales no es evidencia: los reportes citan
fuentes auténticas y aun así las leen mal.

---

## Hallazgo crítico 1 — Autocitación: la fuente 45 es mi propio archivo de contexto

**Severidad: crítica. Invalida buena parte de la sección 5 del reporte.**

En la bibliografía del reporte, la referencia **45 es literalmente `CONTEXT-ALL.md`** —
el archivo de contexto que se le entregó a Gemini para hacer la investigación. El
modelo citó su propio insumo como si fuera una fuente externa verificada.

Las siguientes afirmaciones del reporte están etiquetadas **[VERIFIED]** con la
referencia 45 y **no fueron verificadas por nadie**: provienen de un documento de
crítica de un caso de estudio anterior y no relacionado (un producto de escrow con
stablecoins), que se incluyó en el bundle solo como **ejemplo de formato**:

| Afirmación del reporte | Origen real |
|---|---|
| Coincidencia LLM-humano en dominios expertos: 60–68% | `CONTEXT-ALL.md` línea 391 |
| Fleiss' Kappa 0.10–0.32 en razonamiento multi-paso | `CONTEXT-ALL.md` línea 393 |
| Fleiss' Kappa ~0.30 en entornos multilingües | `CONTEXT-ALL.md` línea 394 |
| Inyección indirecta de prompts (OWASP LLM01) | `CONTEXT-ALL.md` línea 400 |

**Agravante — transferencia de dominio inventada.** Las cifras originales se referían
a LLM-as-judge en dominios **legal, médico y financiero**. El reporte las reaplica a
*"resolución de fallas de red en service meshes o la depuración de volúmenes en
Kubernetes"* (línea 145 del reporte). **Ningún estudio citado midió eso.** La cifra es
real en su dominio original; el uso que le da el reporte es una inferencia fabricada
presentada como hallazgo verificado.

**Veredicto: NO USAR.** Las fuentes originales (el survey en *Cell*, el benchmark en
OpenReview, OWASP LLM01) son reales y consultables, pero:
1. Deben leerse directamente, no a través del reporte.
2. Solo pueden citarse para lo que realmente midieron.
3. Si se quiere afirmar algo sobre precisión de LLMs en diagnóstico de Kubernetes,
   hace falta un estudio de ese dominio — o decir honestamente que no existe evidencia
   pública.

**Lección de método (esta sí vale para la clase):** al armar un bundle de contexto para
investigación, los archivos de *ejemplo de formato* deben marcarse explícitamente como
no-fuentes, porque el modelo los va a tratar como material citable.

---

## Hallazgo crítico 2 — Cifras de Gartner atribuidas a un agregador bursátil

**Severidad: alta.**

La referencia **37** del reporte es
`stocksreport.ai/products/international-business-machines-corporation-ibm-informe-de-actividad-operativa`
— una página de análisis de acciones de IBM. El reporte la usa como fuente de **tres**
afirmaciones atribuidas a Gartner y etiquetadas [VERIFIED]:

- Gasto mundial en nube pública: $723.000M USD en 2025
- Gasto mundial en IA: $2,5 billones USD en 2026
- \>40% de los proyectos de IA agéntica cancelados para finales de 2027

Un agregador bursátil que reformula un informe de analista **no es fuente primaria**.
Las notas de prensa de Gartner viven en `gartner.com/en/newsroom`. Verificación en curso
(ver tabla de resultados abajo).

---

## Hallazgo crítico 3 — Estado en la CNCF mal reportado: Backstage NO está graduado

**Severidad: alta. Es un error de hecho sobre el ecosistema CNCF, en un curso de
certificaciones CNCF.**

El reporte afirma que **Backstage** está en estado **CNCF Graduated**. Es falso:
Backstage está en **Incubating** (entró a la CNCF el 8 de septiembre de 2020 y pasó a
Incubating el 15 de marzo de 2022).
Fuente primaria: [cncf.io/projects/backstage](https://www.cncf.io/projects/backstage/).

De haberse copiado al material del curso, habría enseñado mal la escala de madurez de
la CNCF, que es justamente contenido evaluable de KCNA.

---

## Corrección a esta misma auditoría — Kyverno (falsa alarma)

En una primera lectura marqué como inconsistencia que el reporte dijera "16 de marzo de
2026" mientras su URL citada era `.../2026/03/24/...`. **La verificación me dio la
contraria y el reporte tenía razón:** el 16 de marzo es la *fecha de graduación* y el
24 de marzo es la *fecha de publicación del anuncio*. Son dos eventos distintos, no una
contradicción.

Queda consignado a propósito: una auditoría también se equivoca, y el registro del error
propio vale más que borrarlo.

---

## Hallazgo crítico 4 — Cifras de GitHub mal leídas (kagent)

El reporte afirma que kagent registra **3.215 colaboradores** y **2.610 estrellas**.
Señalé que era implausible (más colaboradores que estrellas) y la verificación lo
confirma: las cifras reales rondan **~3.158 colaboradores** según LFX y **~3.500
estrellas** en GitHub. El reporte subestimó las estrellas y presentó la relación
invertida.

**Lección:** las métricas de LFX Insights (contribuciones agregadas) y las de GitHub
(estrellas, personas) no son intercambiables, y el reporte las mezcló.

---

## Fuentes de tercera mano usadas como primarias

Toda la sección 3 del reporte (dolor operativo) se apoya en blogs que reformulan
investigación ajena. Se verificó cada estadística contra el PDF original. **Resultado:
de 10 afirmaciones, 4 se sostienen, 3 no tienen fuente localizable y 3 están
tergiversadas.** Detalle en la sección de resultados.

| Afirmación | Fuente que usa el reporte | Problema |
|---|---|---|
| Backstage tiene 89% del mercado de IDPs | `roadie.io` — "Why DIY Is Dead" | Roadie vende Backstage gestionado; conflicto de interés directo sobre esa cifra. El propio paper de Frontiers que el reporte cita en otro lado marca esta cifra como metodológicamente no verificable |
| Crossplane graduado (nov 2025) | `kubezilla.io` | Blog aleatorio en vez de `cncf.io` |
| HolmesGPT en Sandbox (8 oct 2025) | `aurorasre.ai` | Blog comercial; la fuente primaria es el issue de `cncf/sandbox` |
| AIOps 30%→65%, ahorro de 30% en costos | `ijraset.com` | Revista de bajo rigor citando a Gartner |

---

## Resultados de verificación

> Solo lo marcado **CONFIRMADO** puede pasar al material del curso.

### Proyectos y estado en la CNCF

| Afirmación del reporte | Veredicto | Valor correcto / fuente primaria |
|---|---|---|
| kagent en CNCF **Sandbox** desde el 22 de mayo de 2025 | **CONFIRMADO** | [cncf.io/projects/kagent](https://www.cncf.io/projects/kagent/) |
| kagent creado por fundadores de Istio en Solo.io | **CONFIRMADO** | Idit Levine y Lin Sun · [kagent.dev](https://kagent.dev/) |
| kagent: 3.215 colaboradores, 2.610 estrellas | **INCORRECTO** | ~3.158 colaboradores (LFX) y **~3.500 estrellas** en GitHub |
| K8sGPT en CNCF **Sandbox** | **CONFIRMADO** | Aceptado el 19 dic 2023, sigue en Sandbox · [cncf.io/projects/k8sgpt](https://www.cncf.io/projects/k8sgpt/) |
| HolmesGPT en CNCF **Sandbox** desde el 8 de octubre de 2025 | **CONFIRMADO** | [cncf.io/projects/holmesgpt](https://www.cncf.io/projects/holmesgpt/) |
| HolmesGPT co-mantenido por Robusta y Microsoft | **CONFIRMADO** | [github.com/HolmesGPT/holmesgpt](https://github.com/HolmesGPT/holmesgpt) |
| HolmesGPT: 2.780+ estrellas, licencia Apache 2.0 | **CONFIRMADO** | Licencia correcta; estrellas hoy ~3.000 (la cifra del reporte quedó corta, no inflada) |
| **Backstage en CNCF Graduated** | **REFUTADO** | Está en **Incubating** desde el 15 mar 2022 · [cncf.io/projects/backstage](https://www.cncf.io/projects/backstage/) |
| Crossplane graduado en **noviembre de 2025** | **IMPRECISO** | Graduó el **28 de octubre de 2025**; el anuncio se publicó el 6 de noviembre · [anuncio CNCF](https://www.cncf.io/announcements/2025/11/06/cloud-native-computing-foundation-announces-graduation-of-crossplane/) |
| Argo CD y Flux graduados | **CONFIRMADO** | Argo CD: 6 dic 2022 · Flux: 30 nov 2022 |
| Kyverno graduado el 16 de marzo de 2026 | **CONFIRMADO** | Graduación 16 mar 2026; anuncio 24 mar 2026 |
| Kyverno: +3.000M descargas y +9.000 estrellas | **PARCIAL** | Las 9.000+ estrellas están en el anuncio oficial; los 3.000M de descargas **no** aparecen en la fuente primaria de la CNCF — no citar esa cifra |

### Financiación y empresas

| Afirmación del reporte | Veredicto | Fuente primaria | Nota |
|---|---|---|---|
| Port.io: Serie C de $100M (11 dic 2025), General Atlantic + Accel + Bessemer + Team8, valoración $800M, $158M acumulados | **CONFIRMADO** | [port.io/blog/port-100m-series-c](https://www.port.io/blog/port-100m-series-c) | Todos los detalles correctos |
| Kubiya.ai: $12M totales, extensión de $6M (ago 2024) liderada por Heavybit | **CONFIRMADO** | [businesswire, 20 ago 2024](https://www.businesswire.com/news/home/20240820679651/en/) | — |
| StackGen "anteriormente conocida como **AppBlocks**" | **REFUTADO** | [prnewswire, rebrand](https://www.prnewswire.com/news-releases/appcd-closes-12-3m-seed-round-and-rebrands-to-stackgen-302243294.html) | El nombre real es **appCD**, no AppBlocks. Nombre inventado. La adquisición de OpsVerse fue en **agosto de 2025**, no "finales de 2025" |
| Facets.cloud: ingresos ₹10–50 Cr (FY mar 2025); presente en Gartner | **CONFIRMADO (con precisión)** | [Tracxn](https://tracxn.com/d/companies/facets.cloud) · [facets.cloud](https://www.facets.cloud/blog/facets-gartner-market-guide-infrastructure-automation-orchestration) | Cifra exacta: ₹11,4 Cr. Aparece en el *Market Guide for Infrastructure Automation & Orchestration* y en el Hype Cycle de SRE |

### Cifras de Gartner

**Matiz importante:** el reporte citó estas cifras a un agregador bursátil (ver Hallazgo
crítico 2), pero al buscar las fuentes primarias, **la mayoría resultó ser correcta**.
Es el caso didáctico perfecto: *citación mala, dato bueno*. Sigue siendo inaceptable
citarlas como lo hizo el reporte — pero ahora tenemos la fuente real.

| Afirmación | Veredicto | Fuente primaria de Gartner |
|---|---|---|
| 80% de las grandes organizaciones con equipos de platform engineering para 2026 (vs 45% en 2022) | **CONFIRMADO** | [Top Strategic Technology Trends 2026, 20 oct 2025](https://www.gartner.com/en/newsroom/press-releases/2025-10-20-gartner-identifies-the-top-strategic-technology-trends-for-2026) |
| 60% de las organizaciones con equipos de 2-5 personas para 2029 (vs 15% en 2026) | **CONFIRMADO** | [Press release, 7 jul 2026](https://www.gartner.com/en/newsroom/press-releases/2026-07-07-gartner-predicts-60-percent-of-organizations-will-adopt-smaller-software-engineering-teams-by-2029) |
| Gasto mundial en nube pública: $723.000M en 2025 | **CONFIRMADO** | [Forecast, 19 nov 2024](https://www.gartner.com/en/newsroom/press-releases/2024-11-19-gartner-forecasts-worldwide-public-cloud-end-user-spending-to-total-723-billion-dollars-in-2025) |
| Gasto mundial en IA: $2,5 billones en 2026 | **CONFIRMADO (cifra exacta $2,59 billones)** | [Press release, 15 ene 2026](https://www.gartner.com/en/newsroom/press-releases/2026-1-15-gartner-says-worldwide-ai-spending-will-total-2-point-5-trillion-dollars-in-2026) |
| \>40% de los proyectos de IA agéntica cancelados para finales de 2027 | **CONFIRMADO** | [Press release, 25 jun 2025](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) — nota: es de **junio de 2025**, no una "previsión 2026" como dice el reporte |
| Adopción de AIOps: 30% en 2021 → 65% en 2025 | **NO VERIFICABLE** | No existe nota de prensa de Gartner con estas cifras. Las previsiones de Gartner que sí se encuentran hablan de ~30-40% para 2024. **Descartada** |
| La automatización con IA reducirá costos operativos de TI en 30% para 2025 | **REFUTADO / INVERTIDO** | El 30% aparece asociado a otra predicción ([servicio al cliente, 5 mar 2025](https://www.gartner.com/en/newsroom/press-releases/2025-03-05-gartner-predicts-agentic-ai-will-autonomously-resolve-80-percent-of-common-customer-service-issues-without-human-intervention-by-20290)), y **Gartner se retractó de la dirección del ahorro**: en [enero de 2026](https://www.gartner.com/en/newsroom/press-releases/2026-01-26-gartner-predicts-genai-cost-per-resolution-for-customer-service-will-exceed-offshore-human-agent-costs-by-2030) predice que el costo por resolución con GenAI **superará** al del agente humano offshore para 2030. **Descartada** |

> El último caso es exactamente el error de **signo/dirección** contra el que hay que
> blindarse: el reporte presenta como ahorro consolidado algo que el propio analista
> revirtió después. Sirve de ejemplo en clase.

### Estadísticas de dolor operativo (sección 3 del reporte)

Verificadas contra los PDF originales de DORA, Faros AI, Port.io, CNCF y OpsRamp.

| Afirmación del reporte | Veredicto | Qué dice realmente la fuente primaria |
|---|---|---|
| **CNCF: 66% de las organizaciones que alojan modelos de IA generativa usan Kubernetes para inferencia** | **CONFIRMADO** | Textual en el [anuncio de la CNCF del 20 ene 2026](https://www.cncf.io/announcements/2026/01/20/kubernetes-established-as-the-de-facto-operating-system-for-ai-as-production-use-hits-82-in-2025-cncf-annual-cloud-native-survey/). El reporte lo citó vía un blog de Pulumi, pero la cifra coincide exactamente con la fuente primaria |
| **Niveles DORA: Elite 19%, lead time <1 día, CFR 5%, recuperación <1h; Low CFR 40%, recuperación 1 semana-1 mes** | **CONFIRMADO** | Coincide exactamente con el [informe DORA 2024](https://dora.dev/research/2024/dora-report/). Única afirmación con fuente de blog que resistió íntegra |
| **Anomalía: el CFR de los "high performers" (20%) supera al del grupo medio (10%)** | **CIFRAS CONFIRMADAS, CAUSA INVENTADA** | Las cifras son reales y DORA 2024 las destaca explícitamente. Pero DORA **no** las atribuye a la IA. La explicación del reporte ("cambios rápidos sin validación adaptada al volumen de IA") es glosa de comentarista presentada como hallazgo de DORA |
| **Port.io: 70% de los desarrolladores dedican 3-4 horas diarias a tareas no centrales** | **CONFIRMADO (con caveats)** | Textual en el [State of Internal Developer Portals 2024 de Port](https://www.port.io/blog/the-2024-state-of-internal-developer-portal-report). Muestra: **100 líderes de ingeniería**, metodología no divulgada. **Port es vendor del segmento** — el reporte omitió ese conflicto de interés y citó un paper de Frontiers que solo repite la cifra de segunda mano |
| **Faros AI: +441% en tiempo de revisión de PRs** | **CIFRA REAL, NATURALEZA TERGIVERSADA** | El [PDF de Faros](https://pages.faros.ai/hubfs/AI_Engineering_Report_2026_The_Acceleration_Whiplash_Faros.pdf) dice +441,5%, pero es una **comparación transversal entre equipos de baja y alta adopción de IA**, no una variación interanual. El reporte la presenta como "aumento interanual" |
| **Faros AI: la probabilidad de incidente por PR se triplicó** | **CIFRA REAL, MISMA TERGIVERSACIÓN** | Textual en el PDF, pero de nuevo comparando cohortes de baja vs. alta adopción, no dos momentos en el tiempo |
| **Faros AI: hasta 41% de los commits son generados por IA** | **NO EXISTE** | La cifra **no aparece en el PDF primario**. El documento habla de 60% de tasa de aceptación de código generado por IA. El 41% parece importado de otra fuente y soldado a la cita de Faros |
| **DORA: 38% de los equipos que usan IA aumentaron su frecuencia de despliegue con aumento paralelo del CFR** | **NO EXISTE / TERGIVERSADO** | El 38% **no aparece en ningún informe de DORA**. Lo que DORA 2024 sí dice es que la adopción de IA se asocia con una **reducción estimada del 1,5% en throughput y del 7,2% en estabilidad**. DORA 2025 reformula: la IA correlaciona positivamente con throughput pero **sigue correlacionando negativamente con estabilidad** |
| **Elite recupera 6.570 veces más rápido que Low** | **CIFRA REAL, AÑO EQUIVOCADO** | Los 6.570x son del [informe DORA **2021**](https://dora.dev/research/2021/). El informe **2024** —el mismo que el reporte cita para los niveles— da **2.293x**. El reporte usa una cifra tres veces mayor de un informe de hace tres años |
| **OpsRamp: 67% ignora alertas / 85% son falsos positivos** | **NO VERIFICABLE** | No existe ningún informe localizable de OpsRamp con esas cifras. El único "67%" real de OpsRamp responde a otra pregunta (reemplazar herramientas de NPM por observabilidad). Cadena de citas probablemente fabricada |
| **Carga cognitiva reducida 40-50% por platform engineering maduro** | **NO VERIFICABLE** | Afirmación de un post de dev.to sin estudio detrás. No se encontró fuente primaria |

> **El hallazgo más valioso de toda la auditoría está en esta tabla, y va en contra del
> reporte:** DORA no dice que la IA acelere sin costo. Dice que la adopción de IA se
> asocia con **peor estabilidad** (−7,2% en 2024; correlación negativa persistente en
> 2025). El reporte convirtió ese hallazgo incómodo en un "38%" inexistente que suena a
> validación. El dato real es más interesante *y* más útil para el curso.

> **Sobre los multiplicadores de DORA (6.570x, 2.293x):** se derivan de puntos medios de
> rangos auto-reportados en encuestas, no de mediciones directas de tiempo de
> recuperación. Oscilan por factores de 2-3x entre años. Son ilustrativos, no medidas.

---

## Qué sí aporta el reporte

Aun con los problemas anteriores, el reporte es útil como **mapa del territorio**:
identifica correctamente a los actores relevantes (kagent, K8sGPT, HolmesGPT, Backstage,
Crossplane, Argo CD/Flux, Kyverno, Port.io, Kubiya, StackGen, Humanitec) y formula bien
la tensión central de la categoría, que además coincide con la tesis del módulo 8:

> El mercado se parte entre **agentes de solo lectura** que diagnostican pero dejan
> todo el trabajo de ejecución al humano, y **agentes con permiso de mutación** que no
> pueden garantizar de forma determinista el efecto de sus acciones sobre una topología
> distribuida.

Esa formulación está etiquetada **[SPECULATIVE]** en el propio reporte, que es la
etiqueta honesta: es un argumento, no un dato. Como argumento pedagógico, es bueno y
se puede usar **presentándolo como argumento**.
