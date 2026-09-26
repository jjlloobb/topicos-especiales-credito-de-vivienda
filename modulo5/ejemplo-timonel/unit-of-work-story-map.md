# Timonel — Mapa de historias a unidades

> **Artefacto de ejemplo.** Tercer archivo que produce la etapa **Units Generation** de
> AI-DLC. Su función es demostrar que **ninguna historia quedó huérfana**.

---

## Cómo se lee

Cada historia está asignada a **exactamente una** unidad. Si una historia aparece en dos
unidades, la frontera entre esas unidades está mal puesta. Si no aparece en ninguna, es una
función que prometiste en el PRD y que nadie va a construir.

La columna **criterio verificable** no la genera el marco por sí sola: la pide este curso,
porque es lo que después permite que un agente revisor compruebe el trabajo en vez de
opinar sobre él. Una historia cuyo criterio no se puede ejecutar produce una tarea que nadie
puede revisar.

---

## Épica 1 — Catálogo e instalación

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-1.1 | Declarar una aplicación en `timonel.yaml` | U1 | `timonel validate ejemplo.yaml` sale con código 0 | Must |
| US-1.2 | Rechazar un catálogo inválido con el campo señalado | U1 | un YAML sin `slo:` falla nombrando ese campo, no genéricamente | Must |
| US-1.3 | Instalar la CLI y comprobar conexión al clúster | U10 | `timonel doctor` lista el contexto y el `ServiceAccount` en uso | Must |

## Épica 2 — Ingesta de telemetría

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-2.1 | Leer métricas de Prometheus y normalizarlas | U4 | una consulta grabada produce N `Senal` con los campos obligatorios | Must |
| US-2.2 | Leer logs y tratarlos como texto no confiable | U4 | un log con marcado de instrucción llega saneado y marcado | Must |
| US-2.3 | Leer eventos de Kubernetes del namespace declarado | U4 | solo aparecen eventos de los namespaces del catálogo | Must |

## Épica 3 — Correlación de incidentes

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-3.1 | Agrupar señales relacionadas en un incidente | U5 | 12 señales de un mismo `Deployment` producen 1 incidente | Must |
| US-3.2 | Deduplicar el mismo incidente repetido | U5 | correr la correlación dos veces no crea un segundo incidente | Must |
| US-3.3 | Filtrar ruido de alertas que no merece diagnóstico | U5 | una alerta que se autorresuelve en 30 s no abre incidente | Must |

## Épica 4 — Diagnóstico con IA

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-4.1 | Diagnosticar un `CrashLoopBackOff` con su causa | U7 | sobre el incidente grabado 001, el diagnóstico nombra la causa esperada | Must |
| US-4.2 | Adjuntar la cadena de evidencia de cada afirmación | U7 | cada afirmación del diagnóstico enlaza a al menos una `Senal` | Must |
| US-4.3 | Escalar a humano cuando la confianza no alcanza | U7 | con confianza por debajo del umbral, el estado es `escalado`, no `diagnosticado` | Must |

## Épica 5 — Corrección y pull request

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-5.1 | Redactar el diff de manifiestos de la corrección | U8 | el diff aplica con `git apply --check` sin conflicto | Must |
| US-5.2 | Empaquetar la evidencia que acompaña al diff | U8 | el paquete contiene el incidente, el diagnóstico y las señales citadas | Must |
| US-5.3 | Redactar el cuerpo del pull request en lenguaje claro | U8 | el cuerpo nombra síntoma, causa, corrección y riesgo de aplicarla | Should |
| US-5.4 | Abrir el pull request con la evidencia adjunta | U9 | el PR existe en el repositorio y su cuerpo enlaza la evidencia | Must |

## Épica 6 — Límite de autonomía

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-6.1 | Operar con un `ServiceAccount` de solo lectura | U6 | `kubectl auth can-i create deployments --as=system:serviceaccount:...` responde `no` | Must |
| US-6.2 | Rechazar cualquier verbo de escritura sobre el clúster | U6 | una llamada a `create`, `patch` o `delete` devuelve error de puerta y queda registrada | Must |
| US-6.3 | No leer secretos, nunca | U6 | `can-i get secrets` responde `no`, y la puerta rechaza la herramienta | Must |
| US-6.4 | No poder ampliar sus propios permisos | U6 | `can-i create clusterrolebindings` responde `no` | Must |
| US-6.5 | No aprobar ni fusionar su propio pull request | U9 | el token del agente no tiene permiso de merge; el intento queda registrado | Must |

## Épica 7 — Calidad del diagnóstico

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-7.1 | Evaluar el diagnóstico contra un conjunto de casos | U7 | la evaluación corre sobre los 20 incidentes grabados y reporta acierto por tipo | Must |
| US-7.2 | Detectar el fallo por ruido antes de que el usuario se canse | U5 | si más del umbral de incidentes de una semana se cierran sin acción, la métrica lo marca | Should |
| US-7.3 | Resistir un intento de manipulación desde los logs | U7 | los casos adversariales del conjunto no cambian la conclusión del diagnóstico | Must |

## Épica 8 — Seguridad

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-8.1 | Sanear todo texto externo antes de que llegue al modelo | U2 | los casos de inyección indirecta quedan neutralizados y marcados | Must |
| US-8.2 | Redactar secretos en cualquier salida | U2 | ninguna salida contiene los patrones de secreto del conjunto de prueba | Must |
| US-8.3 | Registro estructurado con identificador de correlación | U2 | toda entrada de registro trae el identificador del incidente | Must |

## Épica 9 — Evidencia y trazabilidad

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-9.1 | Seguir el estado del pull request hasta la reconciliación | U9 | el estado pasa de `abierto` a `aplicado` solo cuando el reconciliador confirma | Must |
| US-9.2 | Registrar quién aprobó y cuándo | U9 | el registro nombra al aprobador humano y la marca de tiempo | Must |
| US-9.3 | Consultar la evidencia de un incidente cerrado | U10 | `timonel show <incidente>` devuelve diagnóstico, evidencia y enlace al PR | Must |
| US-9.4 | Versionar el esquema del catálogo | U1 | un catálogo de versión anterior se rechaza indicando cómo migrarlo | Should |

## Épica 10 — Resiliencia

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-10.1 | Tiempo de espera en toda llamada externa | U3 | una fuente que no responde corta al límite declarado, no cuelga | Must |
| US-10.2 | Degradar en vez de fallar cuando falta una fuente | U3 | sin Loki, el diagnóstico sigue y declara qué evidencia le faltó | Must |
| US-10.3 | Cortar por presupuesto de inferencia | U3 | al superar el presupuesto del incidente, el estado es `escalado` y el corte queda registrado | Must |

## Épica 11 — Operación

| Historia | Título | Unidad | Criterio verificable | MoSCoW |
|---|---|---|---|---|
| US-11.1 | Listar incidentes abiertos con su estado | U10 | el portal lista los incidentes del clúster con estado y antigüedad | Must |
| US-11.2 | Ver la evidencia de un diagnóstico desde el portal | U10 | cada afirmación del diagnóstico es navegable hasta su señal | Should |

---

## Resumen de cobertura

| Unidad | Historias asignadas | Cuántas |
|---|---|---|
| U1: Catálogo | US-1.1, US-1.2, US-9.4 | 3 |
| U2: Saneamiento | US-8.1, US-8.2, US-8.3 | 3 |
| U3: Resiliencia | US-10.1, US-10.2, US-10.3 | 3 |
| U4: Ingesta | US-2.1, US-2.2, US-2.3 | 3 |
| U5: Correlación | US-3.1, US-3.2, US-3.3, US-7.2 | 4 |
| U6: Puerta de autonomía | US-6.1, US-6.2, US-6.3, US-6.4 | 4 |
| U7: Diagnóstico | US-4.1, US-4.2, US-4.3, US-7.1, US-7.3 | 5 |
| U8: Redactor | US-5.1, US-5.2, US-5.3 | 3 |
| U9: GitOps y PR | US-5.4, US-6.5, US-9.1, US-9.2 | 4 |
| U10: Portal y CLI | US-1.3, US-9.3, US-11.1, US-11.2 | 4 |
| | **Total** | **36** |

**Historias sin unidad: 0. Historias en más de una unidad: 0.** Esa es la comprobación que
tiene que pasar tu propio mapa antes de aprobar la etapa.

---

## Dos cosas que mirar en este mapa

**La épica 6 está partida a propósito.** Cuatro de sus cinco historias viven en U6, pero
US-6.5 (no aprobar su propio pull request) vive en U9, porque el permiso que hay que negar es
del repositorio, no del clúster. El límite de autonomía se impone en **dos** sistemas
distintos, y el mapa lo hace visible. Un mapa que hubiera metido las cinco en U6 estaría
escondiendo la mitad del problema.

**Hay una historia que no es una función, es un detector de fallo.** US-7.2 existe para
descubrir que el producto se volvió ruido: si la mayoría de los incidentes se cierran sin
que nadie actúe, el sistema está produciendo trabajo que nadie quiere. El PRD obliga a tener
al menos una métrica así, y aquí es una historia con dueño.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
