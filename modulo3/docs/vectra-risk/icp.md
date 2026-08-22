# Ideal Customer Profile — Vectra Risk

> Perfil de cliente ideal derivado del `pvb.md` y de la investigación de validación y
> crítica documentadas en `critica.md`.
>
> **Vectra Risk es un producto hipotético construido para este curso.** Este ICP es
> una apuesta explícita y falsable sobre el mercado colombiano de crédito de
> vivienda, no un hallazgo de investigación de campo con entrevistas reales. Donde
> se apoya en cifras externas, llevan fuente y fecha; donde es una proyección
> propia, está marcada **[INTERNO]**.

---

## ICP — segmento beachhead

**Empresas:** bancos medianos y cooperativas financieras colombianas que **ya
originan crédito de vivienda** (propio, o recibido vía brokers/proptechs como LQN
Hipotecas) y que **ya operan algo de infraestructura en Kubernetes** para otros
sistemas — banca digital, canales, APIs —, pero cuyo scoring de crédito de vivienda
sigue corriendo en un motor de reglas monolítico o en un modelo que nunca salió del
notebook del área de riesgo.

**Geografía inicial:** Colombia. **[INTERNO]** — no extiendo el beachhead a México
o Brasil todavía: el argumento regulatorio y de mercado que sostiene a Vectra Risk
(Circular Externa 029 de la SFC, cartera hipotecaria colombiana, competidor LQN) es
específico de Colombia y no está validado para otros países. Expandir geografía sin
validar esto sería el mismo tipo de apuesta sin evidencia que `critica.md` advierte
evitar en varios puntos de este proyecto.

**Tamaño de mercado, con cifras verificadas:** la cartera hipotecaria de vivienda en
Colombia cerró el cuarto trimestre de 2025 en $153,2 billones de pesos, creciendo
11,2% anual, pero equivale a solo el 7,4% del PIB frente al 26,3% de Chile (fuente:
[Valora Analitik, 21 may 2026](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/)).
Es un mercado real, en crecimiento, y con espacio de profundización — no un mercado
maduro y saturado.

### Las tres señales de calificación

Una entidad está en el beachhead si cumple las tres. Si falla una, no es el
cliente:

1. **Recibe un volumen creciente de solicitudes de crédito hipotecario originadas
   por canales digitales o brokers externos** (LQN y proptechs similares). Sin ese
   volumen, la presión sobre el área de riesgo para automatizar el scoring no
   existe todavía. **[VERIFICAR con entrevistas directas a un área de riesgo — hoy
   es una inferencia a partir de cifras de mercado, no un hallazgo de campo]**.
2. **Ya opera Kubernetes para algo**, así que Vectra Risk se conecta a un
   ecosistema existente en lugar de justificar un clúster nuevo solo para scoring.
3. **El área de riesgo ya construyó un modelo de scoring propio que nunca llegó a
   producción real**, o corre en paralelo al motor de reglas oficial sin ser la
   fuente de la decisión. Esta es la señal más valiosa: significa que el problema
   ya está diagnosticado internamente (el modelo existe) y que la barrera es de
   **gobernanza y explicabilidad ante el comité de riesgo**, no de capacidad
   técnica. Vectra Risk vende precisamente esa gobernanza — aunque, como señala
   `critica.md` sección 3, esa gobernanza ya no es un espacio vacío en el mercado
   global.

### Fuera del ICP (explícitamente)

- **Bancos que aún evalúan crédito de vivienda de forma completamente manual.** El
  salto que necesitan primero es cultural y de proceso, no un motor de scoring
  explicable — venderles Vectra Risk sería resolver un problema que todavía no
  tienen.
- **Fintechs sin cartera hipotecaria regulada.** No enfrentan la misma presión de
  auditoría ante la Superintendencia Financiera.
- **Entidades sin infraestructura de contenedores.** El costo de entrada de
  Kubernetes no se justifica solo para este producto.
- **Originadores tecnológicos tipo LQN Hipotecas.** No son el comprador: son, según
  `critica.md`, un competidor potencial o un canal — no un cliente al que
  venderle un motor de scoring, porque ya están construyendo el suyo.
- **Bancos grandes con equipo de model risk management maduro** (Bancolombia y
  pares de ese tamaño). **[INTERNO]** — probablemente ya evalúan directamente
  plataformas enterprise como FICO Platform o Zest AI, con ciclos de compra de
  años y equipos internos capaces de construir lo suyo; el mismo patrón que
  y ciclos de compra que un producto nuevo difícilmente gana en el corto plazo.

---

## Buyer personas

### Persona 1 — Vicepresidente de Riesgo / CRO (decisor y veto principal)

**Quién es:** ejecutivo senior con 10-20 años de experiencia en riesgo crediticio,
responsable ante la Junta y ante la Superintendencia Financiera de la calidad de la
cartera. Su prioridad para 2026 incluye explícitamente acelerar la adopción
responsable de IA, según la encuesta anual de EY y el Institute of International
Finance a 101 bancos en 31 países (fuente:
[PQS, 5 jun 2026](https://pqs.pe/actualidad/economia/la-inteligencia-artificial-y-la-gestion-del-riesgo-crediticio-marcan-la-agenda-de-la-banca-en-2026/)).

**Qué evalúa antes de adoptar:**

- ¿Puedo explicarle esta decisión a la Superintendencia y al solicitante sin que
  suene a caja negra?
- ¿Qué modelo de scoring uso hoy, y qué tan defendible es frente a lo que ya ofrece
  Zest AI nativo en mi core Temenos (si lo uso), o frente a plataformas como FICO
  Platform o Experian Ascend?
- ¿El dato del solicitante sale de mi infraestructura en algún momento?
- ¿Cuánto tiempo de originación gano frente a lo que ya promete LQN (desembolsos en
  10 días)?

**Mata la adopción si:** el sistema no puede correr self-hosted dentro de la
infraestructura del banco; la explicación de una decisión no resiste una pregunta
directa del área de cumplimiento; o el banco ya tiene Zest AI integrado en su core
y Vectra Risk no ofrece nada que ese banco no tenga ya.

### Persona 2 — Oficial de cumplimiento / SARLAFT (veto en paralelo)

**Quién es:** responsable de que las decisiones automatizadas de la entidad no
generen un hallazgo regulatorio ni una denuncia por discriminación.

**Qué evalúa:**

- ¿Puede el modelo estar usando una variable proxy (código postal, comportamiento
  digital) como sustituto indirecto de una variable protegida? El patrón de
  "redlining digital" es un riesgo documentado en sistemas de scoring, no
  hipotético (ver `critica.md`, sección 6).
- ¿El monitoreo de sesgo mide disparidad **antes y después** de incorporar cada
  nueva fuente de datos alternativa, o solo el estado agregado?
- ¿Queda traza auditable de cada decisión y de cada explicación asociada?
- ¿Qué pasa si el `explainability-service` se desincroniza del `scoring-service`?
  (riesgo de integridad señalado en `critica.md`, sección 7).

**Mata la adopción si:** el monitoreo de sesgo se presenta como garantía de
ausencia de discriminación en vez de como una métrica más a vigilar; no hay
separación clara entre lo que el modelo decide y lo que la política de negocio
decide; o no hay respuesta clara sobre la sincronía entre score y explicación.

### Persona 3 — Analista de crédito / comité de crédito (usuario, no comprador)

**Quién es:** quien recibe el caso, revisa el score y su explicación, y firma la
recomendación que sube al comité. No compra el producto, pero determina si se sigue
usando de verdad o si se vuelve una casilla de cumplimiento que nadie lee.

**Qué evalúa:** si la explicación que acompaña al score realmente le ayuda a
sustentar la decisión frente al comité, o si es un reporte más que archiva sin leer
porque la decisión ya estaba tomada con las reglas de siempre.

**Mata la adopción, en silencio:** no rechaza el producto abiertamente — deja de
usarlo como insumo real de la decisión. Es exactamente el modo de fallo que
`critica.md` describe en su sección 5 como "irrelevancia silenciosa": el sistema
sigue funcionando, sus métricas de seguridad se ven perfectas, pero nadie lo está
usando para decidir nada.

---

## Pains

**Operativos**

- **El scoring vive en un notebook, no en producción.** El área de riesgo ya
  entrenó un modelo con buena métrica, pero nadie sabe cómo servirlo con la
  disponibilidad y trazabilidad que exige un proceso de originación regulado.
- **Cada canal de originación (sucursal, app, aliado constructor, broker externo)
  aplica reglas de negocio distintas**, y mantenerlas sincronizadas es trabajo
  manual permanente.
- **Explicar un rechazo hoy exige que un analista reconstruya a mano por qué el
  modelo decidió lo que decidió**, porque la explicabilidad no forma parte del
  contrato de la API del modelo.

**Estratégicos**

- **La velocidad de originación de los competidores tecnológicos ya subió la
  vara.** LQN promociona desembolsos en 10 días y una reducción del 40% en tiempos
  de trámite frente al proceso tradicional (fuente: [Portafolio, 4 mar 2025](https://www.portafolio.co/mis-finanzas/creditos/lqn-hipotecas-desembolso-10-000-creditos-superando-los-1-5-billones-625098)).
  Un banco que sigue tardando semanas en decidir pierde el negocio antes de llegar
  al comité.
- **El área de riesgo ya intentó llevar IA a producción y se frenó en la
  gobernanza**, no en la técnica: tienen el modelo, no tienen cómo defenderlo ante
  el CRO y cumplimiento al mismo tiempo.

> Ese último punto es el más importante del ICP: **el cliente ya tiene la mitad de
> la solución (el modelo) y está atascado exactamente donde Vectra Risk entra (la
> gobernanza para llevarlo a producción).**

---

## Deseos

- Que la decisión de crédito quede **explicada y auditable** desde el momento en
  que se toma, no reconstruida después a mano.
- Reducir el tiempo de originación sin ceder el control final de la decisión a un
  modelo que nadie en el comité pueda cuestionar.
- Que el sistema **corra dentro de la infraestructura propia del banco**, sin que
  el dato del solicitante dependa de un tercero no regulado.
- Poder demostrarle a la Superintendencia, con evidencia técnica y no con una
  promesa, que el modelo no discrimina por proxy.

---

## Triggers de compra

1. **Un hallazgo o una pregunta de la Superintendencia Financiera sobre un caso de
   rechazo de crédito** que la entidad no pudo explicar con el detalle suficiente.
2. **La entrada agresiva de un originador tecnológico (tipo LQN) en el territorio
   del banco**, que fuerza a acortar tiempos de originación sin bajar el estándar
   de riesgo.
3. **Un modelo de scoring construido internamente que el comité de riesgo se niega
   a aprobar** por falta de explicabilidad — el freno no es técnico, es de
   confianza del comité.
4. **La salida del analista senior que sabía "leer entre líneas" por qué el modelo
   decidía lo que decidía**, dejando ese conocimiento sin documentar.

---

## Objeciones probables

| Objeción | Respuesta |
|---|---|
| "Ya tenemos Zest AI integrado en nuestro Temenos, ¿para qué necesito esto?" | Si ya lo tiene integrado y aprobado por su comité de riesgo, probablemente no somos su producto — no vendemos contra una integración nativa que ya funciona. Donde sí aportamos es si necesita que el dato nunca salga de su infraestructura, o si su tipo de crédito (VIS, subsidios, tasas certificadas) no está cubierto de forma nativa por esa plataforma. |
| "Esto lo construimos nosotros con SHAP y Fairlearn, que son gratis." | Cierto, y de hecho Vectra Risk se apoya en las mismas librerías. Lo que no resuelve una librería por sí sola es la orquestación de scoring, explicación, monitoreo de sesgo y registro de decisiones como un sistema versionado y auditable en producción — eso es integración y mantenimiento, no una librería suelta. |
| "LQN ya nos trae solicitudes evaluadas, ¿para qué scoring propio?" | Porque el capital que se presta es del banco, no de LQN. Un banco que aprueba crédito con el scoring de un originador externo no regulado como entidad financiera no tiene cómo defender esa decisión ante la Superintendencia si algo sale mal. |
| "No confío en que un modelo de IA no termine discriminando por proxy." | Es un riesgo real y documentado, no lo negamos. Por eso el monitoreo de disparidad corre desde el día uno, no como auditoría trimestral, y se congela el modelo automáticamente si supera el umbral definido — aunque, como reconoce nuestra propia investigación de crítica, ninguna técnica de explicabilidad garantiza ausencia total de sesgo; mide y alerta, no certifica. |
| "El mercado de scoring con IA ya está lleno de jugadores grandes (FICO, Zest AI, Experian)." | Cierto, y es la objeción más fuerte que tenemos, documentada en nuestra propia investigación de crítica. No competimos en capacidad de modelo contra esos jugadores — competimos en que el sistema corre dentro de su infraestructura regulada, con el conocimiento específico del crédito de vivienda colombiano que esas plataformas globales no traen de fábrica. |

> La última fila usa, a propósito, el hallazgo más duro de `critica.md` en contra
> del propio producto. Un ICP que solo reúne objeciones fáciles de responder no
> sirve para vender ni para decidir.

---

*Material de referencia — Tópicos Especiales en Informática*
