# Instrucciones de entrega — `pvb.md` y `prd.md`

**Tópicos Especiales en Informática · Módulo 2**
**Fecha de entrega: sábado 15 de agosto de 2026 (sesión 3)**

Documento autocontenido. Si solo vas a leer una cosa antes de entregar, lee esta.

---

## Lo que entregas

| # | Entregable | Archivo | Qué es |
|---|---|---|---|
| 1 | Product Vision Board | `pvb.md` | La visión del producto: problema, segmento, ventaja, riesgos |
| 2 | Product Requirements Document | `prd.md` | Los requisitos derivados de esa visión |

Ambos el mismo día. **El PVB va primero**: el PRD se construye a partir de él, así que
todo lo que quede flojo en el PVB se hereda.

---

## Estructura de carpetas que debes conservar

```
tu-proyecto/
├── pvb.md                    ← ENTREGABLE 1
├── docs/                     ← tus insumos
│   ├── pvb.md                  copia de tu PVB
│   ├── overview.md             panorama del dominio
│   ├── mercado.md              análisis de mercado y competencia
│   ├── icp.md                  perfil de cliente ideal
│   ├── critica.md              investigación adversarial
│   └── ...                     entrevistas, benchmarks, notas de campo
└── specs/
    └── prd.md                ← ENTREGABLE 2
```

En este repositorio esa estructura vive en `modulo2/` y `modulo3/`, con el caso de
referencia **Timonel** ya completo para que veas el nivel esperado. Tu trabajo es
reproducirla con tu propio producto.

> [!IMPORTANT]
> **El mecanismo de entrega se anuncia en clase.** Este repositorio es material de
> consulta, no el lugar donde editas. Trabaja sobre tu propia copia.

---

## Paso 1 — Elige tu producto

Dos condiciones **no negociables**:

- **Corre sobre Kubernetes.** No "podría desplegarse algún día": la arquitectura tiene
  sentido en un clúster.
- **Usa IA de forma defendible.** IA dentro del producto, o agentes operándolo. **Si al
  quitar la IA el producto sigue funcionando igual, no cuenta.**

Si tu idea no pasa las dos, no vas a poder construirla en los módulos siguientes ni
sustentarla en la sesión 16. Cámbiala ahora, no en octubre.

---

## Paso 2 — Haz dos investigaciones, no una

**Investigación de validación.** ¿El problema existe de verdad? ¿Quién más lo ha resuelto
y cómo? ¿Qué herramientas del ecosistema CNCF ya cubren parte de esto?

**Investigación de crítica (adversarial).** Es la que importa y la que casi nadie hace.
Pídele explícitamente a la IA que **ataque tu idea**: por qué fallaría, quién ya la está
comoditizando gratis, qué riesgo técnico la mata. Estúdiala tan en serio como la otra.

### Regla de evidencia (se evalúa)

- Toda cifra lleva **fuente con enlace y fecha**.
- Marca tus proyecciones propias como **[INTERNO]**.
- Marca lo que no pudiste verificar como **[VERIFICAR]**.
- Si no encuentras evidencia pública, **dilo**. Un "no hay datos verificables sobre esto"
  vale más que una cifra inventada que suena bien.

> Antes de empezar, lee [`../modulo3/research/README.md`](../modulo3/research/README.md).
> Documenta un caso real donde un reporte de deep research generado con IA llegó con
> cifras inventadas, citas a sí mismo y la dirección del dato invertida. Es exactamente
> el error que te va a costar puntos.

---

## Paso 3 — Documenta todo en Markdown

Transcripciones, notas, análisis, capturas de tu investigación. **Markdown, no PDF**:
gastas menos tokens y el modelo lo lee mejor.

Este material es el insumo directo del PRD. Sin él, el paso 5 no funciona.

---

## Paso 4 — Completa tu `pvb.md`

Usa la plantilla de [`pvb.md`](./pvb.md). Al final del archivo está el ejemplo completo
**Timonel**: ese es el nivel de detalle esperado.

**Reglas de llenado:**

- **Sé específico.** "Empresas" no es un segmento. "Equipos de plataforma de 3 a 15
  ingenieros que ya operan Kubernetes en producción" sí lo es.
- **No escribas "queremos usar IA para X".** Escribe el dolor concreto que resuelves.
- **Si no puedes responder una sección con confianza, no la rellenes con humo.** Esa es
  la señal de que te falta investigación.

La sección más valiosa es la de **riesgos críticos**. Un PVB sin riesgos reales es un PVB
que no se investigó.

---

## Paso 5 — Co-crea tu `prd.md`

1. **Copia tus documentos a `docs/`** (PVB, validación, crítica, entrevistas),
   reemplazando los del caso de referencia.
2. **Abre** [`../modulo3/prompts-para-especificacion.md`](../modulo3/prompts-para-especificacion.md)
   y copia el **Prompt 1** completo.
3. **Pégalo en una conversación nueva** con tu LLM y **adjunta todos** los archivos de
   `docs/`.
4. **Resuelve el Paso 0.** La IA empieza con un análisis de conflictos entre tus
   documentos. **Las decisiones las tomas tú**, no ella.
5. **Trabaja segmento por segmento.** Son 13 segmentos. Aprueba cada uno antes de avanzar.
6. **Consolida el resultado** en `specs/prd.md`.

### La regla que se evalúa aquí

> **El agente propone, tú apruebas.**

Si dejas que la IA escupa el PRD completo y lo apruebas en bloque, perdiste el control del
alcance — y se nota en la sustentación. Es la misma frontera que en el módulo 8 separa a
un agente que sugiere de uno que rompe producción.

### Si la IA no respeta el "segmento por segmento"

Es la frustración número uno. Tres salidas, en orden:

1. **Dilo explícito:** "Detente. Vamos segmento por segmento y esperas mi aprobación."
2. **Sube de modelo.** Los más capaces siguen mejor las instrucciones de proceso.
3. **Empieza sesión nueva** con el prompt limpio.

Y si aun así se adelanta: **no apruebes en bloque.** Revisa uno por uno o pídele que
rehaga desde el primero que no revisaste.

---

## Checklist final

- [ ] Producto seleccionado: corre sobre Kubernetes y usa IA de forma defendible
- [ ] Investigación de **validación** completada y estudiada
- [ ] Investigación de **crítica** completada y estudiada
- [ ] Todo documentado en Markdown, con fuentes y etiquetas [INTERNO] / [VERIFICAR]
- [ ] Ejemplo Timonel leído (final de `pvb.md`)
- [ ] **Entregable 1:** `pvb.md` completo
- [ ] Documentos copiados a `docs/`
- [ ] Paso 0 (análisis de conflictos) resuelto **por ti**
- [ ] 13 segmentos aprobados uno por uno
- [ ] **Entregable 2:** `specs/prd.md` consolidado

---

## Cómo se evalúa

| Criterio | Qué busco |
|---|---|
| **Especificidad** | Segmento, dolor y métricas concretas, no genéricas |
| **Evidencia** | Afirmaciones con fuente verificable |
| **Honestidad crítica** | Que hayas encontrado y **aceptado** las debilidades reales de tu idea |
| **Coherencia técnica** | Que Kubernetes e IA sean centrales, no decorativos |
| **Viabilidad** | Que sea construible en lo que queda del semestre |

**Dos formas rápidas de perder puntos:** cifras sin fuente, y un documento de crítica que
no critica nada. Si tu investigación adversarial concluye que tu idea es excelente, no
hiciste investigación adversarial.

---

## Dudas

Tráelas a clase. Una duda resuelta el sábado vale más que una semana de trabajo en la
dirección equivocada.
