# Ideal Customer Profile — Timonel

> Perfil de cliente ideal del caso de estudio. Derivado del PVB y de la investigación
> auditada en [`research/`](../research/).
>
> **Timonel es una empresa ficticia.** El ICP es una hipótesis construida sobre hechos
> verificados del mercado; no es un hallazgo de investigación. Tu ICP tendrá el mismo
> estatus: **una apuesta explícita y falsable**, no una verdad.

---

## ICP — segmento beachhead

**Empresas:** organizaciones que **ya operan Kubernetes en producción** (no en
evaluación ni en piloto), con equipos de plataforma o SRE de **3 a 15 ingenieros**, que
dan servicio a entre 20 y 200 desarrolladores internos.

**Geografía inicial:** Colombia, México y Brasil. Sectores: fintech, retail digital y
SaaS B2B.

### Las tres señales de calificación

Una empresa está en el beachhead si cumple las tres. Si falla una, no es el cliente:

1. **Ya tienen GitOps andando** (Argo CD o Flux), aunque sea parcialmente. Sin GitOps no
   existe el mecanismo por el cual Timonel entrega valor: el pull request reconciliado.
2. **Tienen más clústeres que personas dedicadas a cuidarlos.** Ese desbalance es el
   dolor. Sin él, el equipo absorbe el trabajo manual sin quejarse.
3. **Alguien del equipo ya probó un agente de IA contra el clúster en pruebas y no se
   atrevió a llevarlo a producción.** Esta es la señal más valiosa: significa que el
   problema ya está diagnosticado internamente y que la objeción es de **confianza**,
   no de utilidad. Timonel vende precisamente esa confianza.

### Fuera del ICP (explícitamente)

- **Equipos sin Kubernetes en producción.** No hay dónde engancharse.
- **Grandes empresas con plataforma interna madura y equipo dedicado.** Construyen lo
  suyo; el ciclo de venta es de años.
- **Startups de menos de 5 ingenieros.** El dolor existe pero no justifica el costo.
- **Entornos con prohibición de enviar telemetría a servicios externos**, salvo que
  compren la modalidad self-hosted.

---

## Buyer personas

### Persona 1 — SRE Lead / Head of Platform (decisor y veto)

**Quién es:** ingeniero senior, 8-15 años de experiencia, responsable de la
disponibilidad del sistema. Es quien recibe la llamada a las 3 a.m.

**Qué evalúa antes de adoptar:**

- **¿Qué puede hacerle este agente a mi clúster si se equivoca?** Es la primera pregunta
  y la única que importa al principio.
- ¿Puedo demostrar el límite, no solo confiar en él? (`kubectl auth can-i --as=` sobre el
  ServiceAccount del agente debe devolver `no` para todo lo que sea escritura.)
- ¿Se integra con el GitOps que ya tengo, o me pide cambiar mi flujo?
- ¿Qué pasa cuando el agente no sabe? ¿Dice "no sé" o inventa?

**Mata la adopción si:** el agente pide permisos de escritura sobre el clúster; el
diagnóstico llega sin la evidencia que lo sustenta; la herramienta exige reemplazar Argo
CD o Flux; o descubre un caso en que el agente afirmó con seguridad algo falso.

### Persona 2 — CISO / Seguridad (veto en sectores regulados)

**Quién es:** responsable de riesgo tecnológico. En fintech, tiene poder de veto absoluto.

**Qué evalúa:**

- ¿Qué datos salen de nuestra infraestructura? Los logs llevan datos de clientes.
- ¿Qué pasa si alguien manipula al agente a través de lo que el agente lee? (Un log es
  texto que un atacante puede influir.)
- ¿Queda traza auditable de cada acción y cada recomendación?
- ¿Existe modalidad self-hosted?

**Mata la adopción si:** no hay redacción de datos sensibles antes de enviarlos al
modelo; no hay respuesta clara sobre inyección indirecta de prompts; no hay auditoría.

### Persona 3 — Ingeniero de plataforma (usuario, no comprador)

**Quién es:** quien convive con la herramienta a diario. No firma el contrato, pero lo
cancela si la herramienta le estorba.

**Qué evalúa:** si los pull requests que abre el agente le ahorran trabajo o le
**generan** trabajo de revisión. Un agente que abre 40 PRs mediocres al día es peor que
no tener agente.

**Mata la adopción si:** la tasa de propuestas útiles es baja. Aquí el producto muere de
ruido, no de error.

---

## Pains

**Operativos**

- **El diagnóstico consume más tiempo que la corrección.** Ante un incidente, el trabajo
  se va en correlacionar eventos del clúster, logs y métricas — no en aplicar el arreglo,
  que suele ser corto.
- **El conocimiento operativo no está escrito.** El "por qué está configurado así" vive
  en dos personas y se va cuando rotan.
- **Las alertas perdieron significado.** Cuando el volumen supera la capacidad de
  atención, se empiezan a ignorar por defecto, y ahí se cuela el incidente real.

**Estratégicos**

- **El equipo de plataforma es el cuello de botella de todos los demás equipos.** Cada
  despliegue no estándar pasa por ellos.
- **Ya intentaron automatizar con IA y no pudieron cerrar el círculo.** Tienen el
  diagnóstico (K8sGPT, HolmesGPT son gratis y funcionan) pero no pueden dar el paso a la
  ejecución sin asumir un riesgo que nadie firma.

> Ese último punto es el más importante del ICP: **el cliente ideal ya tiene la mitad
> de la solución y está atascado exactamente donde Timonel entra.**

---

## Deseos

- Que el conocimiento operativo quede **escrito y auditable**, no en la cabeza de dos personas.
- Reducir el tiempo de diagnóstico sin ceder el control de la ejecución.
- Que la herramienta **respete el flujo GitOps existente** en vez de reemplazarlo.
- Poder demostrarle al CISO, con evidencia técnica, que el agente no puede hacer daño.

---

## Triggers de compra

1. **Un incidente costoso cuyo diagnóstico tomó horas** y cuya corrección tomó minutos.
   Es el momento en que el dolor se vuelve cuantificable ante la dirección.
2. **La salida del ingeniero que sabía todo.** El riesgo de concentración de conocimiento
   se materializa.
3. **Una auditoría de seguridad o un requisito de cumplimiento** que exige traza de quién
   cambió qué y por qué.
4. **Un intento fallido de automatizar con un agente autónomo.** Después del susto, la
   propuesta "el agente solo propone" se vuelve atractiva en vez de tímida.

---

## Objeciones probables

| Objeción | Respuesta |
|---|---|
| "K8sGPT y HolmesGPT son gratis y hacen esto." | Hacen el diagnóstico, y lo hacen bien — de hecho Timonel se apoya en ellos. Lo que no hacen es cerrar el bucle hasta un cambio aprobado y reconciliado, ni acumular historial de aciertos. Si el diagnóstico les basta, no somos su producto. |
| "Podemos construirlo nosotros en un trimestre." | Probablemente sí. La pregunta es si mantenerlo es su negocio: cada versión de Kubernetes, cada cambio de modelo y cada tipo de incidente nuevo exige recalibrar. |
| "No dejo que una IA toque mi producción." | Correcto, y por eso no la toca. El ServiceAccount es de solo lectura y se puede verificar. La única vía al clúster es un PR que **usted** aprueba. |
| "¿Y si el agente me convence de aprobar algo equivocado?" | Es el riesgo real y no lo negamos. Por eso cada propuesta lleva nivel de confianza, el agente puede responder "no sé", y medimos públicamente la tasa de propuestas revertidas. |
| "Gartner dice que la mayoría de los proyectos de IA agéntica se cancelan." | Cierto: más del 40% para finales de 2027, por ROI no demostrable y complejidad de gobernanza. Nuestra respuesta es medir el ROI desde el primer mes en una sola métrica: PRs aprobados sin modificación. |

> La última objeción usa un dato verificado **en contra** del propio producto. Un ICP que
> solo recopila munición a favor no sirve para vender ni para decidir.

---

*Material de referencia — Tópicos Especiales en Informática*
