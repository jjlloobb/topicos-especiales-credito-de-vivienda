# Preguntas de seguimiento — Resiliency Baseline

Activaste la extensión *Resiliency Baseline* (respuesta A). Sus reglas dicen que algunas
decisiones las toma el usuario y no el modelo, y que deben quedar registradas antes de
cerrar los requisitos. En estas preguntas, "región" y "zona" se refieren a la
infraestructura **del banco** (centros de datos y zonas de fallo del clúster
on-premises), no a una nube pública, porque el Principio 2 exige self-hosted.

Recuerda que durante CONSTRUCTION se trabaja en un clúster local (kind/k3d, Q18=A). Estas
preguntas definen el objetivo de **despliegue en el banco** que la especificación debe
soportar.

Escribe la letra de tu elección después de cada `[Answer]:`.

---

## Question R1 — RTO/RPO y estrategia de recuperación ante desastres (RESILIENCY-02)
¿Qué objetivos de recuperación (RTO/RPO) tiene la carga? Considera que, gracias al
fail-closed, si Vectra Risk no está disponible el banco sigue originando crédito por su
proceso manual actual: se pierde velocidad, pero no se toman decisiones erróneas. En
cambio, el Decision Registry es evidencia regulatoria y **no puede perder registros**.

A) RPO/RTO: horas — Backup & Restore. Costo más bajo. Adecuado si el proceso manual del banco cubre la indisponibilidad

B) RPO/RTO: decenas de minutos — Pilot Light

C) RPO/RTO: minutos — Warm Standby

D) RPO/RTO: casi tiempo real — Multi-site Active/Active

E) N/A — un solo centro de datos es aceptable; se tolera la caída de una zona, no de un sitio completo

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question R2 — RPO específico del Decision Registry
Independientemente de R1, ¿cuánta pérdida de registros de decisión es aceptable?

A) Cero: la escritura en el Decision Registry es síncrona y replicada antes de confirmar la decisión (si no puede persistirse, la recomendación no se entrega — fail-closed)

B) Igual al RPO elegido en R1

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question R3 — Gestión de cambios (RESILIENCY-03)
¿Cómo se gobiernan los cambios a producción?

A) Usar el proceso de gestión de cambios existente del banco (CAB / herramienta interna). La especificación solo lo referencia y entrega artefactos compatibles (PR + evidencia + registro de cambio)

B) No hay un proceso que se pueda referenciar (caso académico). AI-DLC propone uno ligero: PR con evidencia + aprobación humana + nota de rollback, alineado con AUTONOMIA-01 y con la aprobación del CRO para las versiones de modelo

C) N/A — carga exenta (documentar por qué)

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R4 — Herramienta de CI (RESILIENCY-04)
Ya elegiste Argo CD con sync manual para el despliegue (Q19). ¿Qué herramienta usa el
pipeline de CI (build, pruebas, escaneo, SBOM)?

A) GitHub Actions (el repositorio ya está en GitHub)

B) GitLab CI

C) Otro pipeline existente del banco

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R5 — Mecanismo de rollback (RESILIENCY-04)
¿Cómo se revierte un despliegue fallido?

A) Redeploy de la versión anterior pinneada (revert del commit en Git + sync manual de Argo CD / rollback de Helm, con aprobación)

B) Blue/green: volver al entorno anterior

C) Canary con rollback automático ante regresión de salud o métricas

D) Rollback que incluye la base de datos (reversión de migraciones de esquema); requiere diseño explícito

E) Usar el procedimiento de rollback existente del banco (indicar referencia)

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R6 — Estilo de despliegue (RESILIENCY-04)
¿Qué estrategia de despliegue es aceptable? Nota: las versiones del **modelo** ya pasan por
staging, sesgo inicial y aprobación del CRO (journey 7.2). Esta pregunta es sobre los
**servicios**.

A) Directo / in-place

B) Rolling (reemplazo gradual de pods), que es el comportamiento por defecto de un Deployment de Kubernetes

C) Blue/green

D) Canary (KServe permite canary de modelos de forma nativa)

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R7 — Topología (RESILIENCY-08)
¿Qué tolerancia a fallos debe soportar el despliegue en el banco?

A) Un solo sitio, varias zonas: nodos del clúster y réplicas de PostgreSQL repartidos en al menos 2 zonas de fallo (racks/zonas del centro de datos). Tolera la caída de una zona, no la de un sitio

B) Multi-sitio activo-pasivo: sobrevive a la caída de un sitio mediante failover

C) Multi-sitio activo-activo

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R8 — Autoscaling (RESILIENCY-09 frente a PRD §8)
RESILIENCY-09 exige autoscaling con límites mínimo y máximo. El PRD pone en *Won't have*
"autoscaling y pruebas de carga a escala real", pero el Módulo 8 incluye "autoscaling
básico bajo carga simulada". ¿Cómo se resuelve?

A) Autoscaling básico: HPA con mínimo y máximo definidos para cada servicio y escalado de KServe para el modelo, validado con carga **simulada**. Las pruebas de carga a escala real siguen en *Won't have* (recomendado, coherente con el Módulo 8)

B) Réplicas fijas, sin autoscaling, y excepción documentada a RESILIENCY-09 por ser MVP académico

X) Other (describe after [Answer]: tag below)

[Answer]: 

## Question R9 — Respuesta a incidentes (RESILIENCY-15)
¿Cómo se atienden los incidentes de producción, entre ellos el fail-closed persistente
(Q12) y el congelamiento del modelo?

A) Usar el proceso de respuesta a incidentes existente del banco (indicar referencia). Alertmanager se integra a él

B) No hay un proceso que se pueda referenciar. AI-DLC propone uno ligero: severidades, runbooks por alerta, rutas de Alertmanager y post-mortem (COE) con seguimiento de acciones correctivas

X) Other (describe after [Answer]: tag below)

[Answer]: 
