# Personas — Vectra Risk

Basadas en PRD §3.4 (buyer personas), §5 (casos de uso) y §7 (journeys). Las personas
son arquetipos, no individuos reales. El ICP en que se apoyan es una **hipótesis
falsable** (PRD §3.1): dos de sus tres señales de calificación están marcadas
**[VERIFICAR con entrevistas]**.

---

## P1 — Analista de crédito

| Atributo | Descripción |
|---|---|
| **Tipo** | Usuario operativo principal (no comprador) |
| **Rol en Keycloak** | `analista` — MFA disponible, no obligatorio |
| **Contexto** | Revisa a diario solicitudes de crédito de vivienda que llegan por canales propios y de brokers. Prepara la recomendación que el comité firma |
| **Objetivos** | Abrir un caso y encontrar el score y su explicación ya calculados; sustentar ante el comité una recomendación que resista preguntas; no reconstruir a mano por qué el modelo decidió algo |
| **Frustraciones** | Los modelos "de notebook" no le dicen nada. Las explicaciones con jerga técnica no le sirven ante el comité. Las herramientas lentas frenan la originación cuando LQN promete 10 días |
| **Cómo abandona el sistema** | En silencio: deja de abrir la explicación y la archiva sin usarla ("irrelevancia silenciosa", PRD §3.4). Por eso la North Star y la métrica de ruido miden su comportamiento |
| **Qué no puede hacer** | Aprobar modelos o políticas. Reactivar modelos. Ver scores sin explicación sincronizada |

## P2 — Ingeniero de riesgo

| Atributo | Descripción |
|---|---|
| **Tipo** | Usuario técnico del área de riesgo |
| **Rol en Keycloak** | `ingeniero_riesgo` — MFA obligatorio |
| **Contexto** | Entrenó el modelo propio del banco, que nunca llegó a producción (señal #3 del ICP). Entrena fuera de Vectra Risk |
| **Objetivos** | Empaquetar una versión de modelo y su explicador, validarla en staging (AUC-ROC, sesgo inicial, sincronía) y llevarla al CRO con evidencia |
| **Frustraciones** | Le bloquean en gobernanza, no en capacidad técnica. Los despliegues manuales no son trazables |
| **Cómo abandona el sistema** | Si registrar un modelo exige reescribirlo o no acepta formatos tabulares estándar |
| **Qué no puede hacer** | Promover a producción sin aprobación del CRO. Cambiar la política de negocio. Reactivar modelos congelados |

## P3 — VP de Riesgo / CRO

| Atributo | Descripción |
|---|---|
| **Tipo** | Decisor de compra y veto principal |
| **Rol en Keycloak** | `cro` — MFA obligatorio |
| **Contexto** | 10–20 años de experiencia. Entre sus prioridades para 2026 está "acelerar la adopción responsable de IA" |
| **Pregunta que guía su juicio** | *"¿Puedo explicarle esta decisión a la Superintendencia sin que suene a caja negra?"* |
| **Objetivos** | Aprobar de forma explícita y trazable cada versión de modelo y de política. Enterarse a tiempo de los incidentes de fail-closed persistente. Defender un rechazo con un expediente completo |
| **Veta la adopción si** | No corre self-hosted. La explicación no resiste una pregunta de cumplimiento. Ya tiene Zest AI y no gana nada adicional |
| **Qué no puede hacer** | Reactivar un modelo congelado (eso es de cumplimiento). Cambiar el estado de un crédito desde Vectra Risk |

## P4 — Oficial de cumplimiento / SARLAFT

| Atributo | Descripción |
|---|---|
| **Tipo** | Veto en paralelo al CRO |
| **Rol en Keycloak** | `cumplimiento` — MFA obligatorio |
| **Pregunta que guía su juicio** | *"¿Puede el modelo estar discriminando por proxy sin que nadie lo note?"* |
| **Objetivos** | Ser alertado con contexto completo cuando la disparidad supera el umbral. Decidir descartar, ajustar el umbral, investigar o reactivar. Aprobar o rechazar nuevas fuentes de datos con medición antes/después |
| **Veta la adopción si** | El monitoreo de sesgo se presenta como garantía absoluta. No hay separación clara entre modelo y política. No hay respuesta sobre la sincronía score–explicación |
| **Qué no puede hacer** | Aprobar versiones de modelo o de política (eso es del CRO) |

## P5 — Comité de crédito

| Atributo | Descripción |
|---|---|
| **Tipo** | Consumidor de la evidencia; no opera la UI |
| **Contexto** | Firma la decisión final con base en la recomendación del analista |
| **Objetivos** | Recibir una recomendación con explicación comprensible, versión de modelo y de política, y ver cuándo el analista se apartó del score y por qué |
| **Riesgo que representa** | Aceptar el score sin análisis ("automatización de confianza ciega", PRD §12 #8) o ignorar la explicación. Ambos patrones los expone la North Star |

## P6 — Auditor / supervisor externo (Superintendencia Financiera)

| Atributo | Descripción |
|---|---|
| **Tipo** | No usuario; destinatario de la evidencia |
| **Contexto** | Hace preguntas formales sobre una decisión concreta. No existe una circular específica de IA; aplica el marco de gestión de riesgo vigente (PVB §9.2) |
| **Objetivos** | Obtener, para una decisión dada, el expediente completo e íntegro: datos usados, versión de modelo y política, explicación tal como se mostró, decisión humana y responsable |
| **Qué exige del sistema** | Registros inmutables y verificables (cadena de hashes), y ninguna afirmación de "ausencia de sesgo" |

---

## Mapa persona → épicas

| Persona | E1 Originación | E2 Gobierno | E3 Sesgo | E4 Registro | E5 Adopción | E6 Plataforma |
|---|---|---|---|---|---|---|
| P1 Analista | ●●● | | | ● | ●● | ● |
| P2 Ingeniero de riesgo | | ●●● | ● | | | ●● |
| P3 CRO | ● | ●●● | | ●● | ●● | ●● |
| P4 Cumplimiento | | ● | ●●● | ● | | ●● |
| P5 Comité | ● | | | | ●● | |
| P6 Supervisor | | | | ●●● | | |

(●●● = beneficiario principal · ● = beneficiario secundario)
