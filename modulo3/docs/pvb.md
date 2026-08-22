# Product Vision Board — Timonel

> **Caso de estudio de referencia.** Versión extendida del ejemplo que aparece en
> [`../modulo2/pvb.md`](../../modulo2/pvb.md), ampliada con la investigación auditada en
> [`research/`](../research/).
>
> **Timonel es una empresa ficticia.** Los hechos externos (proyectos, empresas,
> financiación, cifras de analistas) son reales y verificados. Las cifras internas
> (pricing, márgenes, targets) son **[INTERNO]**: proyecciones inventadas del propio
> caso, y así deben leerse.

---

## PRODUCTO

**Nombre del producto:** Timonel

**Descripción en una línea:** Plataforma que lleva una aplicación de cero a producción
en Kubernetes —infraestructura, despliegue, políticas y observabilidad— y luego la
mantiene ahí con agentes de IA que diagnostican incidentes y **proponen la corrección
como pull request con evidencia**, nunca aplicándola por su cuenta.

**Tagline interno:** *"El agente propone, el humano aprueba, GitOps reconcilia."*

---

## 1. PROBLEMA

Montar y mantener una aplicación en Kubernetes "bien hecha" no es un problema de
conocimiento suelto, es un problema de **integración de doce piezas que nadie integra
por ti**: provisión de infraestructura, construcción de imágenes, manifiestos, GitOps,
políticas de admisión, secretos, NetworkPolicies, métricas, logs, trazas, alertas y
runbooks. Cada pieza tiene un proyecto excelente detrás. Ninguna sabe de las otras.

De ahí salen tres dolores concretos:

- **El diagnóstico cuesta más que la corrección.** Ante un incidente, el tiempo se va en
  correlacionar eventos, logs y métricas. El arreglo, una vez entendido, suele ser corto.
- **El conocimiento operativo no está escrito.** El "por qué está configurado así" vive
  en dos personas y se va cuando rotan.
- **Ya existe el diagnóstico asistido por IA, y aun así el toil no baja.** K8sGPT y
  HolmesGPT diagnostican bien y son gratuitos, pero **devuelven el trabajo de ejecución
  al humano**. El problema se desplaza, no desaparece.

El hueco real no es diagnosticar. Es que **nadie confía en dejar actuar al agente**. Un
agente con permiso de `kubectl apply` en producción es un incidente esperando a ocurrir,
y ningún SRE serio lo autoriza.

**Evidencia de que la tensión es real, no inventada:** los dos actores más serios de la
categoría tomaron esta misma decisión de diseño de forma independiente. **HolmesGPT**
—co-mantenido por Robusta y **Microsoft**— opera de solo lectura *por diseño*, respetando
el RBAC existente. **Humanitec** evita explícitamente ejecutar modelos estocásticos sobre
infraestructura de producción. Cuando dos actores independientes se autolimitan igual,
el límite no es cobardía: es el estado del arte.

### ¿Sobrevive al próximo salto de modelos?

**[X] Sí — es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT.**

Un modelo mejor diagnostica mejor, pero no decide quién aprueba el cambio, cómo queda
auditado, con qué permisos actúa el agente ni cómo se revierte. Eso es gobernanza y
plomería. Cuanto mejores sean los modelos, **más urgente** se vuelve ponerles límites
verificables.

**Durability Score: 5/5**

---

## 2. SEGMENTO TARGET

Detalle completo en [`icp.md`](./icp.md). Resumen:

Equipos de plataforma/SRE de **3 a 15 ingenieros** que **ya operan Kubernetes en
producción** y sirven a 20-200 desarrolladores internos, en fintech, retail digital y
SaaS B2B de Colombia, México y Brasil.

Las tres señales de calificación: ya tienen GitOps; tienen más clústeres que cuidadores;
y **alguien ya probó un agente contra el clúster y no se atrevió a llevarlo a producción**.

**Veto de confianza:** el **SRE Lead / Head of Platform**, y el **CISO** en sectores
regulados. Ambos hacen la misma pregunta: *"¿qué puede hacerle este agente a mi clúster
si se equivoca o si alguien lo manipula?"* Si la respuesta no es **"nada: solo lee, y su
única salida es un pull request"**, no hay conversación.

**Contexto macro que respalda el segmento (Gartner, verificado):** el 80% de las grandes
organizaciones de ingeniería tendrán equipos de platform engineering para 2026 (vs 45% en
2022), y el 60% adoptará equipos de 2-5 personas apoyados en plataformas y agentes para
2029. El comprador existe y está creciendo.

---

## 3. VENTAJA COMPETITIVA PRIMARIA

**[X] Trust**

1. **El agente no tiene permiso de escritura, por diseño.** ServiceAccount de solo
   lectura y allowlist explícito de herramientas. La única vía al clúster es un PR
   aprobado por un humano y reconciliado por GitOps. No es una promesa de marketing:
   es verificable con `kubectl auth can-i --as=`.
2. **Evidencia adjunta a cada propuesta.** Qué observó, de qué recursos, cuándo y por
   qué concluye lo que concluye. Un diagnóstico sin evidencia es una opinión.
3. **Historial de aciertos medido en producción.** Cada propuesta aprobada, rechazada o
   revertida alimenta una tasa de acierto por tipo de incidente. No se compra con una
   API: se acumula operando.

**El moat no es el agente** (replicable en un trimestre). **Es el registro de evidencia
y la tasa de acierto medida**, más la confianza ya concedida por el SRE lead.

---

## 4. ARENA COMPETITIVA

**[X] Disruptor (AI-Disrupted)** — operar Kubernetes es un workflow de una década; lo
reimaginamos, no lo inventamos.

Análisis completo en [`mercado.md`](./mercado.md). Lo esencial:

- **Contra la capa gratuita de la CNCF** (K8sGPT, HolmesGPT, kagent, Argo CD, Flux,
  Kyverno, Crossplane): **no competimos, los orquestamos.** El diagnóstico está resuelto
  y es gratis; vender diagnóstico es competir contra cero. Vendemos el bucle completo y
  el registro auditable.
- **Contra los hyperscalers** (Bedrock+EKS, Gemini Cloud Assist en GKE, Azure SRE Agent):
  todos atan el valor a su nube. Timonel es agnóstico y funciona on-premise.
- **Contra las plataformas comerciales** (Port.io con su Serie C de $100M, Humanitec,
  Kubiya): resuelven catálogo, portal y autoservicio del desarrollador — no la
  **operación** del clúster. Son adyacentes: candidatos a integración.

**Riesgo honesto de la arena:** si un proyecto CNCF gratuito añade el bucle GitOps
completo con evidencia auditable, buena parte de la diferenciación se evapora. Está en la
sección 9 y es el riesgo número uno.

---

## 5. UX PARADIGM

**[X] Agent** — ejecuta autónomamente **dentro de límites duros**.

**Por qué no Autonomous:** porque la autonomía total es exactamente lo que el comprador
no firma. En operación de infraestructura, "la IA corre sin supervisión" no es una
feature: es el motivo del rechazo. **El límite es el producto.**

**Sin preguntar:** observar, correlacionar, diagnosticar, redactar la corrección, abrir
el PR con su evidencia.

**Nunca:** aplicar cambios, aprobar su propio PR, tocar secretos, ampliar sus permisos.

Ese reparto también es la defensa contra manipulación: si un atacante logra influir en lo
que el agente concluye —vía logs, que son texto que un atacante puede escribir— el peor
resultado posible sigue siendo **un PR malo que un humano debe aprobar**.

---

## 6. AI DECISION TRIANGLE

**[X] Capability**

- **Sacrifico velocidad.** Un diagnóstico correcto en 4 minutos vale más que uno dudoso
  en 20 segundos. Quien revisa el PR no está cronometrando; está decidiendo si confía.
- **Sacrifico costo.** Modelos grandes para diagnosticar y redactar; modelos pequeños
  solo para clasificar y filtrar ruido de alertas.
- **Sacrifico cobertura inicial.** Prefiero acertar en 6 tipos de incidente que opinar
  mal sobre 60.

**Razón de fondo:** el costo de un diagnóstico equivocado no es el token desperdiciado —
es la confianza del SRE lead, y esa se pierde una sola vez.

---

## 7. MODELO ECONÓMICO

**Todas las cifras de esta sección son [INTERNO].**

**Modelo:** Hybrid Tiered — suscripción por clúster conectado, con límites crecientes de
incidentes analizados al mes.

- **Team:** $400/mes, hasta 3 clústeres y 150 incidentes analizados/mes.
- **Business:** $1.500/mes, hasta 15 clústeres, políticas personalizadas, SSO.
- **Enterprise:** a convenir, con despliegue self-hosted (requisito frecuente en banca).

**¿Escala a 10x?** **[X] Sí, con un ajuste.** El costo marginal es inferencia, que escala
con **incidentes**, no con usuarios. Un cliente con un clúster inestable puede consumir
10x la media: por eso el límite del tier se mide en incidentes, no en asientos.

**Economía por cuenta (tier Business) [INTERNO]:**

| Concepto | Mensual |
|---|---|
| Inferencia (diagnóstico + redacción del PR) | $180 |
| Infraestructura y almacenamiento de evidencia | $45 |
| Soporte prorrateado | $120 |
| **Costo total** | **$345** |
| **Revenue** | **$1.500** |
| **Gross margin** | **77%** |

El margen depende del filtrado de ruido. Si el 60% de las alertas que llegan al agente
son basura, el costo de inferencia se dispara. Por eso clasificar barato antes de
diagnosticar caro es una decisión **económica**, no técnica — y responde directamente a
una de las tres razones de cancelación que identifica Gartner.

---

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario**

1. **% de PRs propuestos por el agente que se aprueban y mergean sin modificación.** Es
   la métrica que dice si el producto sirve, y es el ROI demostrable desde el mes 1.
   *Target: >60% al mes 6.* **[INTERNO]**
2. **Reducción de tiempo de diagnóstico** en los tipos de incidente cubiertos, medida
   contra la línea base del propio cliente. *Target: -40%.* **[INTERNO]**

**Métricas de IA**

1. **Precisión del diagnóstico de causa raíz**, validada contra el post-mortem humano.
   *Target: >85% en los tipos cubiertos.* **[INTERNO]**
2. **Tasa de propuestas revertidas después de mergear.** Es la métrica de seguridad: mide
   las veces que el agente convenció a un humano de algo equivocado.
   *Target: <2%. Por encima de 5%, el producto se apaga hasta corregirlo.* **[INTERNO]**

**Salud secundaria:** proporción de alertas descartadas como ruido antes del diagnóstico
costoso. Sostiene el margen.

> **Nota metodológica importante:** no fijamos un target de precisión basándonos en
> benchmarks de LLM de otros dominios. Existen estudios sobre acuerdo LLM-humano en
> dominios legales, médicos y financieros, pero **no miden diagnóstico de Kubernetes** y
> extrapolarlos sería inventar. El target de >85% es **[INTERNO]**: una meta de producto
> a validar midiendo, no un dato de la literatura. (Ver el Hallazgo crítico 1 de la
> auditoría: exactamente ese error apareció en el reporte de investigación.)

---

## 9. RIESGOS CRÍTICOS

### 1. Comoditización por el ecosistema CNCF

**Riesgo alto — es el riesgo principal.** El diagnóstico asistido por IA ya es gratis,
open source y respaldado por Microsoft. Si esos proyectos incorporan el bucle GitOps
completo con evidencia auditable, el diferenciador central desaparece.

*Mitigación:* no apostar al diagnóstico sino al **registro de evidencia y la tasa de
acierto**, que son acumulativos. Y construir **sobre** los proyectos CNCF, no contra
ellos: si mejoran, Timonel mejora.

### 2. Pertenecer al 40% que se cancela

**Gartner (junio de 2025): más del 40% de los proyectos de IA agéntica empresariales
serán cancelados para finales de 2027**, por ROI no demostrable, costos de inferencia y
complejidad de gobernanza.

*Mitigación:* atacar las tres razones por diseño — una métrica de ROI medible desde el
mes 1, filtrado previo del ruido para contener inferencia, y gobernanza que reutiliza el
RBAC y el flujo de PR que el cliente ya tiene.

### 3. ¿Replicable en 6 semanas?

**El software sí; la confianza no.** Un equipo competente conecta un LLM al API server y
abre PRs en un trimestre. No se replica: el historial de aciertos por tipo de incidente,
la biblioteca de correcciones validadas contra clústeres reales, y el ciclo de venta con
un SRE lead que ya te dejó entrar a producción.

### 4. Cómo se rompe la confianza a escala

1. **El agente propone algo plausible pero equivocado y un humano cansado lo aprueba a
   las 3 a.m.** El más probable y el más dañino: el producto convenció a alguien de
   romper su propio sistema.
   *Mitigación:* nivel de confianza explícito, negarse a proponer cuando la evidencia es
   insuficiente (**"no sé" es una respuesta válida y hay que premiarla**), bloqueo sobre
   recursos marcados como críticos.
2. **Manipulación vía lo que el agente lee.** Logs y eventos son texto que un atacante
   puede influir; es el patrón de inyección indirecta de prompts catalogado por OWASP
   para aplicaciones con LLM.
   *Mitigación:* sin permisos de escritura, el peor caso es un PR malicioso que un humano
   debe aprobar; más allowlist de herramientas y tratamiento de todo log como no confiable.
3. **Fuga de datos sensibles en la evidencia.** Los logs traen datos de clientes y la
   evidencia va adjunta al PR, es decir, al repositorio.
   *Mitigación:* redacción automática antes de adjuntar y modalidad self-hosted.

**Verdad incómoda:** este producto vive o muere por la confianza de una sola persona por
cuenta —el SRE lead— y esa confianza se pierde con un solo incidente atribuible al
agente. Por eso el límite de permisos no se relaja nunca, ni siquiera cuando el cliente
lo pida.

---

*Material de referencia — Tópicos Especiales en Informática*
