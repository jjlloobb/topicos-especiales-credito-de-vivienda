# Ejemplo de referencia — las unidades y tareas de Timonel

**Módulo 5 · Caso de estudio del curso**

> La vara de calidad de este entregable. Así se ve un juego completo de artefactos de
> **Units Generation** y un plan de tareas por unidad, hechos bien.
>
> **Timonel es el caso de estudio ficticio del curso**, el mismo del módulo 3. Su Product
> Vision Board está en [`../../modulo3/docs/pvb.md`](../../modulo3/docs/pvb.md) y su dominio
> en [`../../modulo3/docs/overview.md`](../../modulo3/docs/overview.md). Aquí se continúa ese
> caso un paso más allá: del PRD a las unidades con sus tareas.

---

## Qué hay aquí

| Archivo | Qué etapa de AI-DLC lo produce | Para qué mirarlo |
|---|---|---|
| [`unit-of-work.md`](./unit-of-work.md) | Units Generation | Cómo se define una unidad y, sobre todo, **qué NO hace** cada una |
| [`unit-of-work-dependency.md`](./unit-of-work-dependency.md) | Units Generation | El grafo, las fases, el camino crítico y el esqueleto ambulante |
| [`unit-of-work-story-map.md`](./unit-of-work-story-map.md) | Units Generation | Que ninguna historia quede huérfana, y criterios verificables |
| [`U06-puerta-autonomia-code-generation-plan.md`](./U06-puerta-autonomia-code-generation-plan.md) | Code Generation, **Parte 1** | Las tareas de una unidad: numeradas, con comando y con trazabilidad |
| [`unidades-y-tareas.md`](./unidades-y-tareas.md) | Consolidación del curso | **El formato de tu entregable** |

Empieza por `unidades-y-tareas.md` si solo vas a mirar uno: es el formato que tienes que
entregar. Los otros cuatro son de dónde sale.

---

## Cómo usarlo

**Como vara de calidad, no como plantilla.** Tus unidades salen de **tu** PRD, no de este.
Copiar la descomposición de Timonel a un producto distinto produce fronteras que no
corresponden a nada, y eso se nota en la sustentación a la primera pregunta.

Lo que sí conviene copiar es el **nivel de exigencia**:

- Cada unidad declara **qué no hace**, no solo qué hace. Es lo que hace que una frontera sea
  una frontera.
- Cada historia tiene un **criterio que se comprueba con un comando**, no con una opinión.
- El grafo se declara y **se verifica acíclico**, no se dibuja y se confía.
- Cada tarea traza a una historia, y cada historia a una unidad. Sin huecos.

---

## Cuatro decisiones de este ejemplo que vale la pena explicar

**1. El límite de autonomía es una unidad, no una promesa.** U6 existe para que la
restricción del PRD sea código con pruebas negativas. Por eso el plan de tareas del ejemplo
es el de U6 y no el de otra: porque es la unidad que vas a enseñar en la sustentación, y
`kubectl auth can-i` sobre su `ServiceAccount` es la mejor diapositiva que vas a tener.

**2. El límite se impone en dos sistemas, no en uno.** Cuatro historias de la épica 6 viven
en U6 (el clúster) y una vive en U9 (el repositorio), porque el permiso de no fusionar su
propio pull request no es del clúster. El mapa de historias lo hace visible en vez de
esconderlo.

**3. Dos capas independientes para la misma restricción.** En el plan de U6, el Paso 3 niega
la escritura en el código y el Paso 5 la niega en el RBAC. Es deliberado: si alguien amplía el
`ClusterRole` por error, el código sigue negándose. Una sola capa es una promesa; dos capas
independientes es un límite.

**4. El camino crítico es honesto, no bonito.** Timonel tiene forma de tubería, así que cinco
de sus siete fases son de una sola unidad y el camino crítico es de profundidad 7. El ejemplo
lo dice en vez de inventar un paralelismo que el grafo no permite. Si tu descomposición sale
así, escríbelo igual: un plan de entrega que promete paralelismo imposible se cae solo.

---

## Un defecto que encontramos en el camino, y por qué te lo contamos

Este ejemplo está construido sobre la estructura de artefactos reales de un proyecto que sí
recorrió AI-DLC de punta a punta. Al revisar ese grafo original antes de adaptarlo,
encontramos un **ciclo**: dos unidades se declaraban dependientes la una de la otra. El
artefacto había pasado por una etapa completa con su compuerta de aprobación, y el ciclo
seguía ahí.

Nadie lo había notado porque un grafo con trece nodos dibujado en Mermaid **se ve bien**. El
ciclo solo aparece si lo buscas.

Por eso la lista de verificación de la guía empieza por «el grafo no tiene ciclos», y por eso
`unit-of-work-dependency.md` de este ejemplo dice explícitamente que se comprobó con un
recorrido en profundidad. **Compruébalo tú también, a mano o con un script de diez líneas.**
Si la unidad A depende de B y B depende de A, ninguna se puede construir primero y el loop de
agentes del módulo siguiente se bloquea sin decirte por qué.

Es el mismo principio que gobierna todo el curso: una compuerta verde no es una prueba.

---

## Procedencia

Los cinco artefactos son **originales de este curso**, escritos en el dominio de Timonel. Lo
que se reutilizó de proyectos reales es la **estructura**: qué campos lleva la definición de
una unidad, cómo se declara la matriz de dependencias, cómo se numeran las tareas con su
trazabilidad. El contenido de dominio, las historias, los criterios y los comandos son de
este ejemplo.

Ningún dato, nombre, producto o cifra de un proyecto real aparece aquí. Timonel es una
empresa ficticia: sus cifras internas son proyecciones inventadas del propio caso y así están
marcadas en su PVB.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
