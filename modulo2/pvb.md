# Product Vision Board

**Módulo 2 — AI & Agentic Engineering**

Este es tu primer artefacto de producto. Lo completas como tarea de la sesión 2
(8 de agosto de 2026) y lo traes listo a la sesión 3 (**sábado 15 de agosto de 2026**).

**Ese mismo día entregas también tu `prd.md`**, que se co-crea a partir de este documento.
El PVB va primero: el PRD hereda todo lo que aquí quede flojo.

Las instrucciones de la tarea, las dos investigaciones que debes hacer y el
checklist de entrega están en el [`README.md`](./README.md) de este módulo.

**Al final de este documento hay un ejemplo completo.** Léelo antes de empezar: ese
es el nivel de detalle y de honestidad que espero en el tuyo.

---

## PRODUCTO

**Nombre del producto:**
_______________________________________

**Descripción en una línea (qué hace y para quién):**
_______________________________________

---

## 1. PROBLEMA

Define el problema que resuelves. Debe ser un dolor real, específico, y que persista
incluso cuando los modelos de IA evolucionen.

**Problema que resuelvo:**
_______________________________________
_______________________________________
_______________________________________

**¿Este problema sobrevive a las próximas 2-3 generaciones de modelos foundation?**
[ ] Sí, porque es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT
[ ] No estoy seguro — necesito investigar más
[ ] No — mi problema es de generación/resumen y se commoditiza

**Durability Score (1-5):** ___

---

## 2. SEGMENTO TARGET

**¿Para quién es este producto?**
_______________________________________
_______________________________________

**¿Quién controla el veto de confianza?** (La persona que puede matar la adopción
aunque el usuario final ame el producto: CISO, SRE lead, compliance, CFO, jefe directo)
_______________________________________

---

## 3. VENTAJA COMPETITIVA PRIMARIA

Solo puedes elegir UNA como primaria. Es tu ventaja defensible principal.

**Ventaja competitiva primaria:**
[ ] Data — Generamos data única que competidores no pueden comprar ni copiar
[ ] Distribution — Estamos embebidos en un canal/workflow difícil de replicar
[ ] Trust — Ofrecemos reliability/safety/compliance que otros no pueden igualar

**¿Qué data, distribución o trust única poseemos o podemos construir?**
_______________________________________
_______________________________________
_______________________________________

---

## 4. ARENA COMPETITIVA

**¿En qué arena compites?**
[ ] Pioneer (AI-Native) — Creo un mercado nuevo que no podría existir sin IA
[ ] Disruptor (AI-Disrupted) — Reimagino un workflow existente haciéndolo 10x mejor
[ ] Enhancer (AI-Enhanced) — Uso IA para fortalecer un producto/proceso existente

**¿Cómo sobrevives o complementas a los gigantes (hyperscalers, vendors de plataforma,
proyectos open source del ecosistema CNCF)?**
_______________________________________
_______________________________________

---

## 5. UX PARADIGM

**¿Cómo interactúa el usuario con tu producto?**
[ ] Assistant — El usuario está en control, la IA sugiere
[ ] Agent — La IA ejecuta tareas autónomamente dentro de límites
[ ] Autonomous — La IA corre sin supervisión humana
[ ] Embedded Intelligence — La IA mejora el producto de forma invisible

**¿Por qué este paradigma para tu caso de uso?**
_______________________________________
_______________________________________

---

## 6. AI DECISION TRIANGLE

No puedes maximizar las tres. Elige la prioridad de tu producto.

**Optimizo primariamente para:**
[ ] Cost — Lo más barato posible (tareas de alto volumen)
[ ] Capability — Lo más inteligente/preciso (decisiones de alto riesgo)
[ ] Speed — Lo más rápido posible (experiencias en tiempo real)

**Trade-offs que acepto:**
_______________________________________
_______________________________________

---

## 7. MODELO ECONÓMICO

**Modelo de pricing:**
[ ] Hybrid Tiered (tiers con límites crecientes)
[ ] Usage-Based / Per-Token (pago por uso)
[ ] Credit Pools (suscripción + créditos)
[ ] Outcome-Based (pago por resultado)
[ ] Seat-Based + AI Add-On (por usuario + IA premium)
[ ] Freemium / Reverse Trial (gratis → conversión)

**¿El pricing escala si tienes 10x usuarios?**
[ ] Sí   [ ] No   [ ] Necesita ajuste

**Costo estimado por usuario/mes:** $________
**Revenue por usuario/mes:** $________
**Gross margin proyectado:** ________%

---

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario:**
1. _______________________________________
2. _______________________________________

**Métricas específicas de IA:**
1. _______________________________________
2. _______________________________________

---

## 9. RIESGOS CRÍTICOS

Esta es la sección más valiosa del documento. Un PVB sin riesgos reales es un PVB
que no se investigó.

**1. ¿Qué pasa si el problema desaparece en 12 meses por comoditización?**
_______________________________________
_______________________________________

**2. ¿Puede un competidor replicar tu producto con la misma API en menos de 6 semanas?**
_______________________________________
_______________________________________

**3. Si tienes éxito a escala, ¿cuál es la primera forma en que se rompe la confianza?**
_______________________________________
_______________________________________

---

## Checklist de entrega

- [ ] Producto seleccionado (corre sobre Kubernetes, usa IA de forma defendible)
- [ ] Deep research de validación completado y estudiado
- [ ] Deep research de crítica completado y estudiado
- [ ] Investigación documentada en archivos Markdown, con fuentes
- [ ] Product Vision Board completado (este documento)
- [ ] `prd.md` co-creado a partir de este PVB (ver `../modulo3/prompts-para-especificacion.md`)
- [ ] Listo para presentar en la sesión 3 (sábado 15 de agosto de 2026)

---
---

# Ejemplo de referencia: Timonel

> Product Vision Board completado. Úsalo como guía de **profundidad, formato y
> honestidad** — tu PVB debe tener este nivel de detalle.
>
> **Timonel es una empresa ficticia**, creada para este curso. El nombre viene del
> griego *κυβερνήτης* (kybernḗtēs, "timonel"), la misma raíz de Kubernetes.
>
> **Convención de evidencia usada en este ejemplo:**
> - **[INTERNO]** — proyección o supuesto del propio equipo. Inventado por
>   construcción; en tu PVB real serían tus estimaciones, y deben ser defendibles.
> - **[VERIFICAR]** — afirmación sobre el mundo exterior (mercado, competencia,
>   adopción) que **en un PVB real va con enlace y fecha**. Aquí queda marcada a
>   propósito para que veas exactamente dónde debe ir tu evidencia.
>
> Esa convención no es decorativa: si entregas un PVB con cifras de mercado sin
> fuente, te las voy a preguntar una por una en la sustentación.

## PRODUCTO

**Nombre del producto:** Timonel

**Descripción en una línea:** Plataforma que lleva una aplicación de cero a producción
en Kubernetes —infraestructura, despliegue, políticas y observabilidad— y luego la
mantiene ahí con agentes de IA que diagnostican incidentes y **proponen la corrección
como pull request con evidencia**, nunca aplicándola por su cuenta.

**Tagline interno:** *"El agente propone, el humano aprueba, GitOps reconcilia."*

## 1. PROBLEMA

Montar una aplicación en Kubernetes "bien hecha" no es un problema de conocimiento
suelto, es un problema de **integración de doce piezas que nadie integra por ti**:
provisión de infraestructura, construcción de imágenes, manifiestos, GitOps, políticas
de admisión, gestión de secretos, NetworkPolicies, métricas, logs, trazas, alertas y
runbooks. Cada pieza tiene un proyecto excelente y gratuito detrás. Ninguna sabe de
las otras.

El resultado es el patrón que se repite en todo equipo de plataforma:

- La primera aplicación llega a producción en semanas, no en días, y el 80% de ese
  tiempo es plomería, no producto. **[VERIFICAR]**
- Cuando algo se rompe a las 2 a.m., el diagnóstico exige correlacionar eventos del
  clúster, logs y métricas a mano. El tiempo se va en *entender*, no en *arreglar*.
  **[VERIFICAR: MTTR reportado en encuestas de SRE/CNCF]**
- El conocimiento de "por qué esto está configurado así" vive en la cabeza de dos
  personas y se pierde cuando rotan.

Ya existen agentes de IA que diagnostican clústeres. El hueco no es el diagnóstico:
es que **nadie confía en dejarlos actuar**. Un agente con permiso de `kubectl apply`
en producción es un incidente esperando a ocurrir, y ningún SRE serio lo autoriza.

**¿Sobrevive al próximo salto de modelos?**

**[X] Sí — es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT.**

Un modelo más inteligente diagnostica mejor, pero no resuelve quién aprueba el cambio,
cómo queda auditado, con qué permisos actúa el agente, ni cómo se revierte. Eso es
gobernanza y plomería, no inteligencia. Cuanto mejores sean los modelos, **más urgente**
se vuelve el problema de ponerles límites verificables.

**Durability Score: 5/5**

## 2. SEGMENTO TARGET

**Beachhead:** equipos de plataforma / SRE de **3 a 15 ingenieros**, en empresas que
**ya operan Kubernetes en producción** (no en evaluación) y que sirven a entre 20 y
200 desarrolladores internos. Sector: fintech, retail digital y SaaS B2B en Colombia,
México y Brasil.

Tres señales de que una empresa está en el beachhead:
1. Ya tienen GitOps (Argo CD o Flux) andando, aunque sea a medias.
2. Tienen más clústeres que personas dedicadas a cuidarlos.
3. Alguien en el equipo ya probó un agente de IA contra el clúster **en un entorno
   de pruebas** y no se atrevió a llevarlo a producción.

**NO es para:** equipos que aún no tienen Kubernetes en producción (el producto no
tiene dónde engancharse), grandes empresas con plataforma interna propia y madura, ni
startups de menos de 5 ingenieros (el dolor no justifica el costo).

**¿Quién controla el veto de confianza?**

El **SRE lead / Head of Platform**, y en empresas reguladas el **CISO**. Ambos matan
la adopción con la misma pregunta: *"¿qué puede hacer este agente contra mi clúster
si se equivoca o si alguien lo manipula?"*

Si la respuesta no es **"nada: solo lee, y su única salida es un pull request"**, la
conversación se acaba ahí. Por eso la arquitectura de permisos no es un detalle de
implementación — **es el argumento de venta**.

## 3. VENTAJA COMPETITIVA PRIMARIA

**[X] Trust**

Tres capas acumulables:

1. **El agente no tiene permiso de escritura, por diseño.** Su ServiceAccount es de
   solo lectura y su lista de herramientas es un allowlist explícito. La única forma
   en que un cambio llega al clúster es un pull request aprobado por un humano y
   reconciliado por GitOps. No es una promesa de producto: es una propiedad
   verificable con `kubectl auth can-i`.
2. **Evidencia adjunta a cada propuesta.** Cada PR que abre el agente incluye qué
   observó, de qué recursos, en qué momento y por qué concluye lo que concluye. Un
   diagnóstico sin evidencia es una opinión; el registro de esas evidencias es lo que
   convierte al agente en algo auditable.
3. **Historial de aciertos medido en producción.** Cada propuesta aprobada, rechazada
   o revertida alimenta una tasa de acierto por tipo de incidente. Ese historial no se
   compra ni se replica con una API: se acumula operando.

**El moat real no es el agente** (replicable). **Es el registro de evidencia y la tasa
de acierto medida**, más la confianza que el SRE lead ya te dio.

## 4. ARENA COMPETITIVA

**[X] Disruptor (AI-Disrupted)** — El workflow (operar Kubernetes) existe hace una
década. Lo estamos reimaginando, no inventando.

**Cómo sobrevivimos a los gigantes y al open source:**

- **Los hyperscalers** (AWS, GCP, Azure) optimizan para que te quedes en su nube. Su
  tooling de operación asistida no cruza nubes. Timonel es agnóstico y funciona igual
  en un clúster on-premise. **[VERIFICAR: productos concretos de cada hyperscaler]**
- **Los proyectos open source del ecosistema** (K8sGPT, HolmesGPT, kagent) resuelven
  el diagnóstico y lo resuelven bien — y son gratis. **Timonel no compite con ellos:
  los orquesta.** El valor no está en diagnosticar; está en el bucle completo
  detectar → diagnosticar → proponer PR con evidencia → aprobar → reconciliar, y en
  el registro auditable que queda.
- **Las plataformas de developer portal** (Backstage, Humanitec, Port) resuelven el
  *self-service* del desarrollador, no la *operación* del clúster. Son adyacentes:
  candidatos a integración, no a competencia frontal. **[VERIFICAR]**

**Riesgo honesto de esta arena:** si uno de los proyectos open source añade el bucle
GitOps completo con evidencia, buena parte de la diferenciación se evapora. Está
contemplado en la sección 9.

## 5. UX PARADIGM

**[X] Agent** — La IA ejecuta autónomamente **dentro de límites duros**.

**Por qué no Autonomous:** porque la autonomía total es exactamente lo que el
comprador no va a firmar. En operación de infraestructura, "la IA corre sin supervisión"
no es una feature, es el motivo del rechazo. El límite es el producto.

**Qué hace el agente sin preguntar:** observar, correlacionar, diagnosticar, redactar
la corrección, abrir el pull request con su evidencia.

**Qué no hace nunca:** aplicar cambios al clúster, aprobar su propio PR, tocar secretos,
escalar sus propios permisos.

Ese reparto también es la línea de defensa contra manipulación: si un atacante logra
influir en lo que el agente concluye, el peor resultado posible sigue siendo **un pull
request malo que un humano tiene que aprobar**.

## 6. AI DECISION TRIANGLE

**[X] Capability**

**Trade-offs que acepto:**

- **Sacrifico velocidad.** Un diagnóstico correcto en 4 minutos vale más que uno
  dudoso en 20 segundos. El humano que revisa el PR no está esperando con cronómetro;
  está esperando poder confiar.
- **Sacrifico costo.** Uso modelos grandes para el diagnóstico y la redacción del
  cambio. Modelos pequeños solo para clasificar y filtrar ruido de alertas.
- **Sacrifico cobertura al inicio.** Prefiero acertar en 6 tipos de incidente que
  opinar mal sobre 60. La cobertura se gana con historial, no con prompts.

**Razón de fondo:** el costo de un diagnóstico equivocado no es el token desperdiciado
— es la confianza del SRE lead, y esa se pierde una sola vez.

## 7. MODELO ECONÓMICO

**Modelo de pricing:** Hybrid Tiered — suscripción por clúster conectado, con límites
crecientes de incidentes analizados por mes. **[INTERNO]**

- **Team:** $400/mes hasta 3 clústeres y 150 incidentes analizados/mes.
- **Business:** $1.500/mes hasta 15 clústeres, políticas personalizadas, SSO.
- **Enterprise:** a convenir, despliegue self-hosted (el agente corre dentro de la
  infraestructura del cliente; requisito frecuente en banca).

**¿Escala a 10x usuarios?** **[X] Sí, con un ajuste.** El costo marginal principal es
inferencia, que escala con **incidentes**, no con usuarios. Un cliente con un clúster
inestable puede consumir 10x la media: por eso el límite del tier se define en
incidentes analizados y no en asientos.

**Economía por cuenta (tier Business) [INTERNO]:**

| Concepto | Mensual |
|---|---|
| Inferencia (diagnóstico + redacción de PR) | $180 |
| Infraestructura y almacenamiento de evidencia | $45 |
| Soporte prorrateado | $120 |
| **Costo total** | **$345** |
| **Revenue** | **$1.500** |
| **Gross margin** | **77%** |

El margen se sostiene si el filtrado de ruido funciona. Si el 60% de las alertas que
llegan al agente son basura, el costo de inferencia se dispara y el margen se cae —
por eso la clasificación previa con modelos baratos es una decisión económica, no
técnica.

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario:**
1. **Tasa de PRs propuestos por el agente que se aprueban y mergean sin modificación.**
   Es la métrica que mide si el producto sirve. *Target: >60% al mes 6.* **[INTERNO]**
2. **Reducción de MTTR** en los tipos de incidente cubiertos, medida contra la línea
   base del propio cliente en sus 3 meses previos. *Target: -40%.* **[INTERNO]**

**Métricas específicas de IA:**
1. **Precisión del diagnóstico de causa raíz**, validada contra el post-mortem humano.
   *Target: >85% en los tipos de incidente cubiertos.* **[INTERNO]**
2. **Tasa de propuestas revertidas después de mergear.** Es la métrica de seguridad:
   mide las veces que el agente convenció a un humano de algo equivocado.
   *Target: <2%. Por encima de 5%, el producto se apaga hasta corregirlo.* **[INTERNO]**

**Métrica de salud secundaria:** proporción de alertas descartadas como ruido antes
de llegar al diagnóstico costoso. Sostiene el margen bruto.

## 9. RIESGOS CRÍTICOS

**1. ¿Qué pasa si el problema desaparece en 12 meses por comoditización?**

**Riesgo alto, y es el riesgo principal.** El diagnóstico asistido por IA en Kubernetes
ya es gratis y open source. Si esos proyectos incorporan el bucle GitOps completo con
evidencia auditable, el producto pierde su diferenciador central. **[VERIFICAR: estado
y roadmap actual de esos proyectos]**

*Mitigación:* no apostar al diagnóstico. Apostar al **registro de evidencia y a la
tasa de acierto medida en producción**, que son acumulativos y no se replican con
código. Y construir sobre los proyectos open source en vez de contra ellos: si mejoran,
Timonel mejora.

**2. ¿Puede un competidor replicarlo en menos de 6 semanas?**

**El software sí; la confianza no.** Un equipo competente conecta un LLM al API server
de Kubernetes y abre pull requests en un mes. Lo que no se replica en seis semanas:

- El historial de aciertos por tipo de incidente, que se construye operando meses.
- La biblioteca de correcciones validadas contra clústeres reales, no de laboratorio.
- El ciclo de venta con un SRE lead que ya te dejó entrar a su producción.

**3. Si tienes éxito a escala, ¿cuál es la primera forma en que se rompe la confianza?**

Tres vectores, en orden de probabilidad:

1. **El agente propone un cambio plausible pero equivocado y un humano cansado lo
   aprueba a las 3 a.m.** Es el escenario más probable y el más dañino, porque el
   producto convenció a alguien de romper su propio sistema.
   *Mitigación:* nivel de confianza explícito en cada PR, negativa a proponer cuando
   la evidencia es insuficiente ("no sé" es una respuesta válida y hay que premiarla),
   y bloqueo automático de propuestas sobre recursos marcados como críticos.
2. **Manipulación del agente por contenido que él mismo lee.** Los logs y los eventos
   del clúster son texto que un atacante puede influir. Un agente que lee logs es un
   agente que puede ser instruido por ellos. **[VERIFICAR: literatura de inyección de
   prompts vía datos operativos]**
   *Mitigación:* el agente jamás tiene permiso de escritura, así que el peor caso es
   un PR malicioso que un humano debe aprobar; más el allowlist de herramientas y el
   tratamiento de todo log como dato no confiable.
3. **Fuga de información sensible a través de la evidencia.** Los logs traen datos de
   clientes; la evidencia adjunta al PR los expondría en el repositorio.
   *Mitigación:* redacción automática de datos sensibles antes de adjuntar, y opción
   self-hosted donde nada sale de la infraestructura del cliente.

**Verdad incómoda:** este producto vive o muere por la confianza de una sola persona
por cuenta —el SRE lead— y esa confianza se pierde con un solo incidente atribuible
al agente. Por eso el límite de permisos no se relaja nunca, ni siquiera cuando el
cliente lo pida.
