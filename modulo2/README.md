# Módulo 2 — AI & Agentic Engineering

**Sesión 2 · sábado 8 de agosto de 2026 · 9:00–12:00**

Este módulo arranca el hilo que atraviesa todo el semestre. A partir de hoy no
estudias Kubernetes en abstracto: eliges **un producto** y lo construyes módulo a
módulo hasta llevarlo a producción en la sesión 14.

---

## El arco completo del curso

```
Módulo 2  →  idea validada       →  Product Vision Board  (pvb.md)
                                 →  requisitos            (prd.md)
Módulos 3-7 →  capacidad técnica →  contenedores, K8s, CKA, CKAD, CKS
Módulo 8  →  producción          →  GitOps, agentes en el clúster, observabilidad
Sesión 16 →  sustentación        →  proyecto final
```

Tu entregable final no es solo el software: es **la fábrica que lo produce** y la
evidencia verificable en cada paso.

---

## Ruta de entrega — resumen

Dos entregables, una semana, cinco pasos. El detalle de cada paso está más abajo.

| # | Paso | Resultado |
|---|---|---|
| 1 | Elegir el producto — corre sobre Kubernetes **y** usa IA de forma defendible | Idea fijada |
| 2 | Dos investigaciones con IA: **validación** y **crítica adversarial** | Research documentado |
| 3 | Documentar todo en Markdown, con fuentes | Insumos del PRD |
| 4 | Completar la plantilla del Product Vision Board | **`modulo2/pvb.md`** |
| 5 | Co-crear el PRD con el Prompt 1, segmento por segmento | **`modulo3/specs/prd.md`** |

### Dónde queda cada archivo

```
modulo2/
└── pvb.md                          ← ENTREGABLE 1

modulo3/
├── docs/                           ← tus insumos (reemplazan el caso de referencia)
│   ├── pvb.md                        copia de tu PVB
│   ├── overview.md                   panorama del dominio
│   ├── mercado.md                    análisis de mercado
│   ├── icp.md                        perfil de cliente ideal
│   ├── critica.md                    investigación adversarial
│   └── ...                           entrevistas, benchmarks, notas
├── specs/
│   └── prd.md                      ← ENTREGABLE 2
└── prompts-para-especificacion.md    el Prompt 1 que produce el PRD
```

### Archivos de este módulo

| Archivo | Qué es |
|---|---|
| `README.md` | Esta guía. Léela primero. |
| **[`INSTRUCCIONES-ENTREGA.md`](./INSTRUCCIONES-ENTREGA.md)** | **Las instrucciones completas de entrega, paso a paso.** Documento autocontenido: si solo vas a leer una cosa antes de entregar, es esta |
| `pvb.md` | Plantilla del **Product Vision Board** + reglas de llenado + un ejemplo completo de referencia al final |

Para el PRD trabajas en la carpeta del módulo 3:
[`../modulo3/prompts-para-especificacion.md`](../modulo3/prompts-para-especificacion.md).

---

## Cómo entregar

> [!IMPORTANT]
> **El mecanismo de entrega se anuncia en la sesión 2.** Anótalo aquí cuando lo tengas.
>
> Este repositorio es material de consulta: las rutas de arriba indican **cómo se llaman
> tus archivos y cómo se organizan**, no que edites este repositorio directamente.
> Trabaja sobre tu propia copia y conserva esa misma estructura de carpetas.

---

## Tu tarea para la sesión 3 (sábado 15 de agosto de 2026)

Llegas con **dos entregables**: `pvb.md` y `prd.md`, más tu investigación documentada.

> **Es una sola semana para ambos.** El PRD no se escribe desde cero: sale del PVB y de
> tu investigación, co-creado con IA segmento por segmento. Si el PVB queda flojo, el PRD
> hereda el problema — por eso el orden importa y no conviene dejarlo para el viernes.

### 1. Elige tu producto

Una idea propia que cumpla **dos condiciones no negociables**:

- **Corre sobre Kubernetes.** No "podría desplegarse en Kubernetes algún día":
  la arquitectura tiene sentido en un clúster.
- **Usa IA de forma defendible.** IA dentro del producto, o agentes operándolo.
  Si al quitar la IA el producto sigue funcionando igual, no cuenta.

Si tu idea no pasa esas dos condiciones, no vas a poder construirla en los módulos
siguientes ni sustentarla en la sesión 16.

### 2. Investiga con IA — dos investigaciones, no una

**Deep research de validación.** ¿El problema existe de verdad? ¿Quién más lo ha
resuelto y cómo? ¿Qué herramientas del ecosistema CNCF ya cubren parte de esto?

**Deep research de crítica (adversarial).** Esta es la que importa y la que casi
nadie hace. Pídele explícitamente a la IA que **ataque tu idea**: por qué fallaría,
quién ya la está comoditizando gratis, qué riesgo técnico la mata. Estúdiala tan en
serio como la de validación.

> **Regla de evidencia:** toda cifra que escribas lleva fuente. Si tu investigación
> dice "el mercado es de $X mil millones", quiero el enlace y la fecha. Una cifra
> sin fuente es una cifra inventada, y en la sustentación se cae sola.

### 3. Documenta todo en Markdown

Transcripciones de entrevistas, notas, análisis, capturas de la investigación.
Este material alimenta directamente el PRD del paso 5.

### 4. Completa `pvb.md`

Llena cada sección con base en tu investigación, no en tu intuición.

### 5. Co-crea tu `prd.md`

Con el PVB listo, conviertes la visión en requisitos.

1. Copia tus documentos (PVB, investigación de validación, investigación de crítica,
   entrevistas) a `modulo3/docs/`, reemplazando los del caso de referencia.
2. Abre [`../modulo3/prompts-para-especificacion.md`](../modulo3/prompts-para-especificacion.md)
   y usa el **Prompt 1**.
3. Adjunta todos tus documentos y trabaja **segmento por segmento**, aprobando cada uno
   antes de avanzar.
4. Guarda el resultado consolidado en `modulo3/specs/prd.md`.

> **La regla del curso, aplicada aquí:** *el agente propone, tú apruebas*. Si dejas que
> la IA escupa el PRD completo y lo apruebas en bloque, perdiste el control del alcance
> — y eso se nota en la sustentación. Es la misma frontera que en el módulo 8 separa a un
> agente que sugiere de uno que rompe producción.

---

## Reglas de llenado

- **Sé específico.** "Empresas" no es un segmento. "Equipos de plataforma de 3 a 15
  ingenieros que ya operan Kubernetes en producción" sí lo es.
- **No escribas "queremos usar IA para X".** Escribe el dolor concreto que resuelves.
- **Si no puedes responder una sección con confianza, no la rellenes con humo** —
  esa es exactamente la señal de que te falta investigación.
- Trae tus dudas a clase.

---

## Checklist antes de la sesión 3 (sábado 15 de agosto de 2026)

- [ ] Producto seleccionado, corre sobre Kubernetes y usa IA de forma defendible
- [ ] Deep research de **validación** completado y estudiado
- [ ] Deep research de **crítica** completado y estudiado
- [ ] Investigación documentada en archivos Markdown, con fuentes
- [ ] Ejemplo de referencia (final de `pvb.md`) leído — ese es el nivel esperado
- [ ] **Entregable 1:** `pvb.md` completado
- [ ] Documentos copiados a `modulo3/docs/`
- [ ] Análisis de conflictos (Paso 0 del Prompt 1) resuelto por ti, no por la IA
- [ ] **Entregable 2:** `modulo3/specs/prd.md` consolidado, segmento por segmento

---

## Cómo se evalúa este entregable

| Criterio | Qué busco |
|---|---|
| Especificidad | Segmento, dolor y métricas concretas, no genéricas |
| Evidencia | Afirmaciones con fuente verificable |
| Honestidad crítica | Que hayas encontrado y aceptado las debilidades reales de tu idea |
| Coherencia técnica | Que Kubernetes e IA sean centrales, no decorativos |
| Viabilidad | Que sea construible en lo que queda del semestre |

La sección más valiosa de tu PVB es la de **riesgos críticos**. Un PVB sin riesgos
reales es un PVB que no se investigó.
