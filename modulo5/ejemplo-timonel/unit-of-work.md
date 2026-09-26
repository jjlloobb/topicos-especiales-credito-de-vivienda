# Timonel — Unidades de trabajo

> **Artefacto de ejemplo.** Esto es lo que produce la etapa **Units Generation** de AI-DLC.
> Timonel es el caso de estudio ficticio del curso (ver [`../../modulo3/docs/pvb.md`](../../modulo3/docs/pvb.md)).
> Úsalo como vara de calidad, no como plantilla para copiar: tus unidades salen de **tu** PRD.

---

## Panorama

Timonel se descompone en **10 unidades de trabajo**. Siete forman la cadena de valor
(telemetría → correlación → diagnóstico → corrección → pull request → portal); tres son
transversales y se construyen como unidades independientes.

Cada unidad mapea a un subdirectorio bajo `internal/`, se despliega como una carga de
trabajo separada en el clúster (salvo las transversales, que son bibliotecas) y se puede
probar sola.

| # | Unidad | Tipo | Se despliega como |
|---|---|---|---|
| U1 | Esquema del catálogo y modelo de dominio | Fundación | biblioteca + CRDs |
| U2 | Saneamiento y registro estructurado | Transversal | biblioteca |
| U3 | Resiliencia y presupuesto de inferencia | Transversal | biblioteca |
| U4 | Ingesta de telemetría | Cadena | `Deployment` |
| U5 | Correlación de señales e incidentes | Cadena | `Deployment` |
| U6 | Puerta de autonomía y RBAC | Cadena | biblioteca + `ClusterRole` |
| U7 | Motor de diagnóstico con IA | Cadena | `Deployment` |
| U8 | Redactor de corrección y evidencia | Cadena | `Deployment` |
| U9 | Integración GitOps y pull request | Cadena | `Deployment` |
| U10 | Portal de operación y CLI | Cadena | `Deployment` + binario |

---

## Definición de cada unidad

### U1: Esquema del catálogo y modelo de dominio
- **Ruta del módulo**: `internal/catalog/`
- **Responsabilidad**: definir y validar el `timonel.yaml` declarativo de una aplicación
  (qué se despliega, qué políticas la gobiernan, qué SLO promete), y los tipos de dominio
  compartidos: `Aplicacion`, `Senal`, `Incidente`, `Diagnostico`, `Correccion`, `Evidencia`.
- **Qué NO hace**: no lee el clúster, no decide nada, no tiene efectos secundarios. Es tipos
  y validación.
- **Historias**: US-1.1, US-1.2, US-9.4
- **Depende de**: ninguna. Es la fundación.
- **Archivos**:
  - `internal/catalog/schema.go` — esquema del `timonel.yaml`
  - `internal/catalog/validate.go` — validador del esquema
  - `internal/catalog/types.go` — tipos de dominio compartidos
  - `internal/catalog/parse.go` — deserialización segura de YAML
  - `config/crd/` — CustomResourceDefinitions de `Aplicacion` e `Incidente`
  - `schemas/timonel.schema.json` — esquema de referencia publicable
  - `test/catalog/` — pruebas unitarias

### U2: Saneamiento y registro estructurado *(transversal)*
- **Ruta del módulo**: `internal/safety/`
- **Responsabilidad**: tratar todo texto de origen externo como dato, nunca como
  instrucción. Saneamiento de logs, eventos y tickets antes de que lleguen al modelo;
  redacción de secretos en cualquier salida; registro estructurado con identificador de
  correlación.
- **Qué NO hace**: no decide si un contenido es malicioso, solo lo neutraliza y lo marca.
- **Historias**: US-8.1, US-8.2, US-8.3
- **Depende de**: ninguna. Transversal.
- **Archivos**:
  - `internal/safety/sanitize.go` — saneamiento de texto no confiable
  - `internal/safety/redact.go` — redacción de secretos y datos personales
  - `internal/safety/logger.go` — registro estructurado + correlación
  - `internal/safety/errors.go` — manejador global de errores
  - `test/safety/` — pruebas unitarias, incluidas las de inyección indirecta

### U3: Resiliencia y presupuesto de inferencia *(transversal)*
- **Ruta del módulo**: `internal/budget/`
- **Responsabilidad**: tiempos de espera en toda llamada externa, degradación elegante
  cuando falta una fuente de telemetría, y el presupuesto de inferencia: límite de tokens y
  de costo por incidente, con corte duro.
- **Qué NO hace**: no elige el modelo. Solo impone el límite y corta.
- **Historias**: US-10.1, US-10.2, US-10.3
- **Depende de**: ninguna. Transversal.
- **Archivos**:
  - `internal/budget/timeout.go` — envoltura de tiempo de espera
  - `internal/budget/degrade.go` — degradación elegante por fuente ausente
  - `internal/budget/tokens.go` — contabilidad y corte de presupuesto
  - `test/budget/` — pruebas unitarias

### U4: Ingesta de telemetría
- **Ruta del módulo**: `internal/ingest/`
- **Responsabilidad**: leer métricas, logs y eventos del clúster y normalizarlos a la
  `Senal` de U1. Adaptadores para Prometheus, Loki y la API de eventos de Kubernetes.
- **Qué NO hace**: no correlaciona, no interpreta, no llama a ningún modelo.
- **Historias**: US-2.1, US-2.2, US-2.3
- **Depende de**: U1 (tipos), U2 (saneamiento del texto de logs)
- **Archivos**:
  - `internal/ingest/prometheus.go` — adaptador de métricas
  - `internal/ingest/loki.go` — adaptador de logs
  - `internal/ingest/events.go` — adaptador de eventos de Kubernetes
  - `internal/ingest/normalize.go` — normalización a `Senal`
  - `test/ingest/` — pruebas unitarias con respuestas grabadas

### U5: Correlación de señales e incidentes
- **Ruta del módulo**: `internal/correlate/`
- **Responsabilidad**: agrupar señales en un `Incidente`, deduplicar, y filtrar ruido. Es
  la unidad que decide **qué merece un diagnóstico** y qué no.
- **Qué NO hace**: no diagnostica. Decide si hay algo que diagnosticar.
- **Historias**: US-3.1, US-3.2, US-3.3, US-7.2
- **Depende de**: U1 (tipos), U4 (señales normalizadas)
- **Archivos**:
  - `internal/correlate/group.go` — agrupación temporal y topológica
  - `internal/correlate/dedupe.go` — deduplicación de incidentes
  - `internal/correlate/noise.go` — filtro de ruido de alertas
  - `test/correlate/` — pruebas unitarias + propiedades de idempotencia

### U6: Puerta de autonomía y RBAC
- **Ruta del módulo**: `internal/gate/`
- **Responsabilidad**: imponer el límite de autonomía del producto de forma **verificable**.
  Toda acción del agente pasa por aquí. Define la lista blanca de herramientas, el
  `ServiceAccount` de solo lectura con su `ClusterRole`, la comprobación de permisos antes
  de actuar, y el rechazo duro de cualquier intento de escritura en el clúster.
- **Qué NO hace**: **nunca** aplica un cambio, nunca aprueba un pull request, nunca lee
  secretos, nunca amplía sus propios permisos.
- **Historias**: US-6.1, US-6.2, US-6.3, US-6.4
- **Depende de**: U1 (tipos), U2 (registro de cada decisión)
- **Archivos**:
  - `internal/gate/allowlist.go` — lista blanca de herramientas
  - `internal/gate/rbac.go` — comprobación de permisos con `SelfSubjectAccessReview`
  - `internal/gate/refuse.go` — rechazo duro de verbos de escritura
  - `internal/gate/audit.go` — registro inmutable de cada decisión de la puerta
  - `config/rbac/` — `ServiceAccount`, `ClusterRole` y `ClusterRoleBinding` de solo lectura
  - `test/gate/` — pruebas unitarias + pruebas negativas de escalada de privilegios

### U7: Motor de diagnóstico con IA
- **Ruta del módulo**: `internal/diagnose/`
- **Responsabilidad**: el bucle de razonamiento. Recibe un `Incidente`, recoge la evidencia
  que necesita a través de U6, consulta al modelo y produce un `Diagnostico` con su cadena
  de evidencia y su nivel de confianza.
- **Qué NO hace**: no redacta la corrección, no toca Git, no aplica nada.
- **Historias**: US-4.1, US-4.2, US-4.3, US-7.1, US-7.3
- **Depende de**: U1 (tipos), U5 (incidentes), U6 (toda lectura del clúster pasa por la
  puerta), U3 (presupuesto y tiempos de espera)
- **Archivos**:
  - `internal/diagnose/loop.go` — bucle de razonamiento acotado
  - `internal/diagnose/evidence.go` — recolección y encadenamiento de evidencia
  - `internal/diagnose/confidence.go` — cálculo y umbral de confianza
  - `internal/diagnose/escalate.go` — escalamiento a humano cuando no alcanza el umbral
  - `internal/diagnose/prompts/` — plantillas de instrucción versionadas
  - `test/diagnose/` — pruebas con incidentes grabados + conjunto de evaluación

### U8: Redactor de corrección y evidencia
- **Ruta del módulo**: `internal/remediate/`
- **Responsabilidad**: convertir un `Diagnostico` en una `Correccion`: el diff concreto de
  manifiestos y el paquete de evidencia que acompaña al pull request.
- **Qué NO hace**: no abre el pull request, no aplica el diff.
- **Historias**: US-5.1, US-5.2, US-5.3
- **Depende de**: U1 (tipos), U7 (diagnóstico)
- **Archivos**:
  - `internal/remediate/patch.go` — generación del diff de manifiestos
  - `internal/remediate/bundle.go` — empaquetado de la evidencia
  - `internal/remediate/render.go` — redacción del cuerpo del pull request
  - `test/remediate/` — pruebas de diff + snapshots del cuerpo del PR

### U9: Integración GitOps y pull request
- **Ruta del módulo**: `internal/gitops/`
- **Responsabilidad**: abrir el pull request contra el repositorio de manifiestos, con la
  evidencia adjunta, y seguir su estado hasta que un humano lo aprueba y el reconciliador lo
  aplica.
- **Qué NO hace**: **nunca** hace merge, nunca se auto-aprueba, nunca hace `kubectl apply`.
- **Historias**: US-5.4, US-6.5, US-9.1, US-9.2
- **Depende de**: U8 (la corrección), U6 (la puerta confirma que no hay escritura directa)
- **Archivos**:
  - `internal/gitops/branch.go` — creación de la rama
  - `internal/gitops/pullrequest.go` — apertura del PR y adjuntos
  - `internal/gitops/status.go` — seguimiento de estado y reconciliación
  - `test/gitops/` — pruebas contra un servidor Git local

### U10: Portal de operación y CLI
- **Ruta del módulo**: `internal/portal/` y `cmd/timonel/`
- **Responsabilidad**: el punto de entrada del operador. Lista incidentes, muestra la
  evidencia de cada diagnóstico, enlaza al pull request y expone las mismas operaciones por
  línea de comandos.
- **Qué NO hace**: no diagnostica ni corrige. Solo muestra y enlaza.
- **Historias**: US-1.3, US-9.3, US-11.1, US-11.2
- **Depende de**: U5 (incidentes), U7 (diagnósticos), U9 (estado del PR)
- **Archivos**:
  - `internal/portal/server.go` — servidor HTTP
  - `internal/portal/handlers.go` — manejadores de incidente y evidencia
  - `internal/portal/templates/` — vistas
  - `cmd/timonel/main.go` — punto de entrada de la CLI
  - `cmd/timonel/commands/` — subcomandos
  - `test/portal/` — pruebas de integración

---

## Organización del código

```text
timonel/
├── cmd/
│   └── timonel/             # U10: CLI
│       └── commands/        # U10: subcomandos
├── internal/
│   ├── catalog/             # U1: esquema, tipos de dominio, validación
│   ├── safety/              # U2: saneamiento, redacción, registro
│   ├── budget/              # U3: tiempos de espera, degradación, presupuesto
│   ├── ingest/              # U4: adaptadores de telemetría
│   ├── correlate/           # U5: agrupación, deduplicación, ruido
│   ├── gate/                # U6: lista blanca, RBAC, rechazo
│   ├── diagnose/            # U7: bucle de razonamiento, evidencia, confianza
│   ├── remediate/           # U8: diff de manifiestos, paquete de evidencia
│   ├── gitops/              # U9: rama, pull request, estado
│   └── portal/              # U10: servidor y vistas
├── config/
│   ├── crd/                 # U1: CustomResourceDefinitions
│   └── rbac/                # U6: ServiceAccount, ClusterRole, binding
├── schemas/                 # U1: esquema publicable
├── deploy/                  # manifiestos de despliegue por unidad
└── test/
    ├── catalog/ safety/ budget/ ingest/ correlate/
    ├── gate/                # incluye pruebas negativas de escalada
    ├── diagnose/ remediate/ gitops/ portal/
    └── e2e/                 # el esqueleto ambulante
```

---

## Lo que hace defendible esta descomposición

Cuatro cosas, y cada una responde a un punto de la lista de verificación de la guía:

1. **Ninguna unidad es «el backend».** La frontera de cada una es una responsabilidad
   nombrable y lo que NO hace está escrito. U7 diagnostica y no corrige; U8 corrige y no
   publica; U9 publica y no aprueba.
2. **El límite de autonomía es una unidad, no una promesa.** U6 existe para que la
   restricción del producto sea código con pruebas negativas, no una frase del PRD. En la
   sustentación, `kubectl auth can-i` sobre su `ServiceAccount` es la evidencia.
3. **Cada unidad se prueba sola.** Las de la cadena reciben y devuelven tipos de U1, así que
   se prueban con entradas grabadas sin levantar las demás.
4. **Hay paralelismo real.** Las tres unidades de la primera fase no dependen entre sí, y
   más adelante U4 y U6 tampoco. El grafo completo está en
   [`unit-of-work-dependency.md`](./unit-of-work-dependency.md).

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
