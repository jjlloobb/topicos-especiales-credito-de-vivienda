# Timonel — Unidades y tareas

> **Este es el formato del entregable.** Consolida, en un solo archivo legible, las unidades
> de `unit-of-work.md` y las tareas de cada `*-code-generation-plan.md`.
>
> **No es un resumen para el profesor: es la entrada de un programa.** El orquestador del loop
> de agentes lee este archivo para decidir qué despachar, en qué orden y contra qué criterio
> revisar. Escríbelo pensando en eso.

> [!NOTE]
> Este ejemplo desarrolla **3 de las 10 unidades** de Timonel, para que se vea el formato sin
> convertirse en un libro. **Tu archivo tiene que traer todas las tuyas.**

---

## Orden de ejecución

Del grafo de [`unit-of-work-dependency.md`](./unit-of-work-dependency.md), verificado acíclico:

| Fase | Unidades | En paralelo |
|---|---|---|
| 1 | U1, U2, U3 | 3 |
| 2 | U6, U4 | 2 |
| 3 | U5 | 1 |
| 4 | U7 | 1 |
| 5 | U8 | 1 |
| 6 | U9 | 1 |
| 7 | U10 | 1 |

**Esqueleto ambulante:** una alerta sintética que atraviesa U4 → U5 → U7 → U8 → U9 → U10 con
un solo tipo de incidente. Se construye antes de profundizar en cualquier unidad.

---

## U1 — Catálogo y modelo de dominio

- **Responsabilidad:** definir y validar el `timonel.yaml` y los tipos de dominio compartidos.
- **Qué no hace:** no lee el clúster, no decide, no tiene efectos secundarios.
- **Depende de:** ninguna.
- **Historias que implementa:** US-1.1, US-1.2, US-9.4.
- **Terminada cuando:** `go test ./internal/catalog/... && timonel validate ejemplo.yaml` sale con código 0.

| # | Tarea | Criterio de aceptación (comando) | Historia |
|---|---|---|---|
| U1-T01 | Tipos de dominio en `internal/catalog/types.go` | `go build ./internal/catalog` | US-1.1 |
| U1-T02 | Esquema del `timonel.yaml` en `schema.go` | `go test ./internal/catalog -run TestEsquema` | US-1.1 |
| U1-T03 | Deserialización segura de YAML en `parse.go` | `go test ./internal/catalog -run TestYamlSeguro` rechaza etiquetas peligrosas | US-1.1 |
| U1-T04 | Validador que nombra el campo que falla | `go test ./internal/catalog -run TestErrorNombraCampo` | US-1.2 |
| U1-T05 | Versionado del esquema y mensaje de migración | `go test ./internal/catalog -run TestVersionAntigua` | US-9.4 |
| U1-T06 | CRDs de `Aplicacion` e `Incidente` en `config/crd/` | `kubectl apply --dry-run=server -f config/crd/` | US-1.1 |
| U1-T07 | Pruebas de propiedad: validar es idempotente | `go test ./internal/catalog -run TestIdempotente` | US-1.2 |
| U1-T08 | Resumen de la unidad | el resumen trae la salida real de `timonel validate` | — |

---

## U6 — Puerta de autonomía y RBAC

- **Responsabilidad:** imponer el límite de autonomía de forma verificable. Toda acción del
  agente pasa por aquí.
- **Qué no hace:** nunca aplica un cambio, nunca aprueba un PR, nunca lee secretos, nunca
  amplía sus permisos.
- **Depende de:** U1, U2.
- **Historias que implementa:** US-6.1, US-6.2, US-6.3, US-6.4.
- **Terminada cuando:** los cuatro `kubectl auth can-i` responden lo esperado y
  `go test ./test/gate -run TestEscalada` pasa con sus cinco casos negativos.

| # | Tarea | Criterio de aceptación (comando) | Historia |
|---|---|---|---|
| U6-T01 | Lista blanca de herramientas en `allowlist.go` | `go test ./internal/gate -run TestAllowlistRechazaLoNoListado` | US-6.2 |
| U6-T02 | `CanI` con `SelfSubjectAccessReview` en `rbac.go` | `go test ./internal/gate -run TestCanI` | US-6.1 |
| U6-T03 | Rechazo duro de los cinco verbos de escritura | `go test ./internal/gate -run TestRechazaEscritura` | US-6.2 |
| U6-T04 | Registro de decisiones que solo añade | `go test ./internal/gate -run TestAuditSoloAnade` | US-6.2 |
| U6-T05 | `ServiceAccount` y `ClusterRole` de solo lectura | `kubectl auth can-i get pods --as=system:serviceaccount:timonel:agente` responde `yes` | US-6.1 |
| U6-T06 | Negar `secrets` en el `ClusterRole` | `kubectl auth can-i get secrets --as=system:serviceaccount:timonel:agente` responde `no` | US-6.3 |
| U6-T07 | Negar la creación de bindings | `kubectl auth can-i create clusterrolebindings --as=system:serviceaccount:timonel:agente` responde `no` | US-6.4 |
| U6-T08 | Cablear la puerta en `diagnose/loop.go` (modificar en su sitio) | `grep -rn "kubernetes.NewForConfig" internal/diagnose/` no devuelve nada | US-6.2 |
| U6-T09 | Cinco pruebas negativas de escalada | `go test ./test/gate -run TestEscalada` | US-6.2, US-6.3, US-6.4 |
| U6-T10 | Resumen con la salida real de los cuatro `can-i` | el resumen trae las cuatro salidas pegadas | — |

---

## U7 — Motor de diagnóstico con IA

- **Responsabilidad:** el bucle de razonamiento. De un incidente a un diagnóstico con su
  cadena de evidencia y su nivel de confianza.
- **Qué no hace:** no redacta la corrección, no toca Git, no aplica nada.
- **Depende de:** U1, U3, U5, U6.
- **Historias que implementa:** US-4.1, US-4.2, US-4.3, US-7.1, US-7.3.
- **Terminada cuando:** la evaluación corre sobre los 20 incidentes grabados, reporta acierto
  por tipo, y los casos adversariales no cambian la conclusión.

| # | Tarea | Criterio de aceptación (comando) | Historia |
|---|---|---|---|
| U7-T01 | Bucle de razonamiento acotado en `loop.go` | `go test ./internal/diagnose -run TestBucleTermina` con tope de iteraciones | US-4.1 |
| U7-T02 | Toda lectura del clúster vía `gate.Client()` | `go test ./internal/diagnose -run TestUsaPuerta` | US-4.1 |
| U7-T03 | Recolección y encadenamiento de evidencia | `go test ./internal/diagnose -run TestCadaAfirmacionTieneSenal` | US-4.2 |
| U7-T04 | Cálculo de confianza y umbral | `go test ./internal/diagnose -run TestUmbral` | US-4.3 |
| U7-T05 | Escalamiento a humano bajo el umbral | `go test ./internal/diagnose -run TestEscalaBajoUmbral` deja estado `escalado` | US-4.3 |
| U7-T06 | Plantillas de instrucción versionadas en `prompts/` | `go test ./internal/diagnose -run TestPromptVersionado` | US-4.1 |
| U7-T07 | Conjunto de evaluación con 20 incidentes grabados | `go test ./test/diagnose -run TestEvaluacion` reporta acierto por tipo | US-7.1 |
| U7-T08 | Casos adversariales de inyección desde logs | `go test ./test/diagnose -run TestAdversarial` | US-7.3 |
| U7-T09 | Corte por presupuesto de inferencia (usa U3) | `go test ./internal/diagnose -run TestCortePresupuesto` | US-4.3 |
| U7-T10 | Resumen con la tabla de acierto por tipo de incidente | el resumen trae la salida real de la evaluación | — |

---

## Las siete unidades restantes

En tu entregable van desarrolladas igual. Aquí, solo su forma:

| Unidad | Historias | Terminada cuando |
|---|---|---|
| U2 Saneamiento | US-8.1, US-8.2, US-8.3 | los casos de inyección quedan neutralizados y ninguna salida contiene patrones de secreto |
| U3 Resiliencia | US-10.1, US-10.2, US-10.3 | una fuente que no responde corta al límite y el corte por presupuesto queda registrado |
| U4 Ingesta | US-2.1, US-2.2, US-2.3 | las consultas grabadas producen `Senal` válidas de las tres fuentes |
| U5 Correlación | US-3.1, US-3.2, US-3.3, US-7.2 | 12 señales dan 1 incidente y correr dos veces no crea un segundo |
| U8 Redactor | US-5.1, US-5.2, US-5.3 | el diff pasa `git apply --check` y el paquete trae la evidencia citada |
| U9 GitOps y PR | US-5.4, US-6.5, US-9.1, US-9.2 | el PR existe, el token del agente no puede fusionarlo, y el estado solo pasa a `aplicado` cuando el reconciliador confirma |
| U10 Portal y CLI | US-1.3, US-9.3, US-11.1, US-11.2 | el portal lista incidentes y cada afirmación es navegable hasta su señal |

---

## Por qué este archivo sirve como entrada del loop

Tres propiedades, y si tu archivo no las tiene, el loop no funciona:

1. **Cada tarea tiene un comando.** El agente revisor lo ejecuta. Sin comando, el revisor
   opina, y un revisor que opina es un segundo modelo felicitando al primero.
2. **Cada tarea traza a una historia.** El orquestador puede decidir qué no construir todavía
   sin romper la trazabilidad hasta el PRD.
3. **El orden sale del grafo, no de la intuición.** El orquestador despacha la fase 1 en
   paralelo porque el grafo dice que esas tres unidades no se tocan.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
