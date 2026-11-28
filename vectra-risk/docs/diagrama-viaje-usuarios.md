# Diagrama del viaje de los usuarios

Qué hace cada persona en Vectra Risk, por dónde entra y qué puede ver. Los roles y las vistas salen de la tabla de rutas de la consola (`console/spa/src/views/shared/routes.ts`); el recorrido del analista se ejecutó contra `kind-vectra` el 27 de noviembre de 2026.

Diagramas relacionados: [caso completo de crédito de vivienda](diagrama-caso-credito-vivienda.md) y [arquitectura](diagrama-arquitectura.md).

## 1. Quién hace qué a lo largo de un caso

```mermaid
flowchart LR
    subgraph CAN["Canal del banco"]
        C1["Envía la solicitud<br/>de crédito"]
    end

    subgraph ANA["Analista del comité"]
        direction TB
        A1["Entra con contraseña<br/>y segundo factor"]
        A2["Abre el caso<br/>en la bandeja"]
        A3["Lee recomendación,<br/>puntaje y razones"]
        A4["Pide la explicación"]
        A5["Registra su decisión"]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    subgraph CRO["VP de Riesgo (CRO)"]
        direction TB
        R1["Revisa la bandeja<br/>y los casos"]
        R2["Consulta modelos<br/>y congelamientos"]
        R1 --> R2
    end

    subgraph CUM["Oficial de cumplimiento"]
        direction TB
        U1["Recibe el aviso de<br/>un modelo congelado"]
        U2["Abre el congelamiento<br/>y su paquete de evidencia"]
        U3["Resuelve: reactivar o no,<br/>con verificación reforzada"]
        U1 --> U2 --> U3
    end

    subgraph ING["Ingeniero de riesgo"]
        direction TB
        I1["Propone promover<br/>un modelo (promotion-tool)"]
        I2["Consulta las versiones<br/>en la consola"]
        I1 --> I2
    end

    subgraph SIS["Sistema"]
        direction TB
        S1["Puntúa y explica<br/>el caso"]
        S2["Vigila el sesgo<br/>cada 15 min"]
        S3["Congela el modelo<br/>si hay sesgo"]
        S2 --> S3
    end

    C1 --> S1
    S1 --> A2
    A5 --> R1
    S3 --> U1
    U3 -.->|"modelo activo otra vez"| S1
    I1 -.->|"pull request aprobado"| S1
```

### Cómo leerlo

Cada recuadro es una persona (o el sistema) y, dentro, sus pasos en orden. Las flechas entre recuadros muestran cuándo el trabajo de uno desencadena el de otro.

| Quién | Qué busca | Su recorrido |
|---|---|---|
| **Canal del banco** | Que la solicitud se evalúe | Envía la solicitud; no usa la consola |
| **Analista del comité** | Decidir rápido y poder defender la decisión | Entra, abre el caso, lee la recomendación, pide la explicación y registra si la sigue o se aparta |
| **VP de Riesgo (CRO)** | Saber si el modelo sirve y si se puede defender | Mira la bandeja y los casos, las versiones del modelo y los congelamientos |
| **Oficial de cumplimiento** | Que un modelo sesgado no siga decidiendo | Ve el congelamiento con su evidencia y decide si se reactiva, con un segundo factor reciente |
| **Ingeniero de riesgo** | Llevar un modelo nuevo a producción sin saltarse controles | Propone la promoción con `promotion-tool`, que abre un pull request; consulta las versiones en la consola |

El punto central: **el modelo recomienda y una persona decide**. El sistema nunca cierra un caso por su cuenta, y nunca reactiva un modelo congelado sin el oficial de cumplimiento.

## 2. Qué ve cada rol en la consola

```mermaid
flowchart LR
    AN(["Analista"])
    CR(["CRO"])
    CU(["Cumplimiento"])
    IN(["Ingeniero de riesgo"])

    subgraph DISP["Vistas disponibles"]
        direction TB
        V1["Bandeja de casos<br/>y detalle del caso"]
        V2["Modelos<br/>y detalle del modelo"]
        V3["Congelamientos"]
        V4["Contexto del congelamiento<br/>(paquete de evidencia)"]
    end

    subgraph DIF["Vistas diferidas: «no disponible en esta versión»"]
        direction TB
        D1["Alta manual de solicitud"]
        D2["Políticas"]
        D3["Fuentes de datos"]
        D4["Monitoreo de sesgo"]
        D5["Expedientes"]
        D6["Fallos persistentes"]
        D7["Verificación de integridad"]
    end

    AN --> V1
    CR --> V1
    CR --> V2
    CR --> V3
    CU --> V2
    CU --> V3
    CU --> V4
    IN --> V2

    AN -.-> D1
    AN -.-> D2
    CR -.-> D2
    CR -.-> D3
    CR -.-> D4
    CR -.-> D5
    CR -.-> D6
    CR -.-> D7
    CU -.-> D2
    CU -.-> D3
    CU -.-> D4
    CU -.-> D5
    IN -.-> D3
```

### Cómo leerlo

Una flecha continua lleva a una vista que funciona; una punteada, a una vista que aparece en el menú del rol pero muestra el aviso «Esta pantalla no está disponible en esta versión».

| Rol | Pantalla de inicio | Vistas que funcionan | Vistas diferidas en su menú |
|---|---|---|---|
| Analista | Bandeja de casos | Bandeja y detalle del caso | Alta manual de solicitud, Políticas |
| CRO | Bandeja de casos | Bandeja y detalle del caso, Modelos, Congelamientos | Políticas, Fuentes de datos, Monitoreo de sesgo, Expedientes, Fallos persistentes, Verificación de integridad |
| Cumplimiento | Congelamientos | Congelamientos y su contexto, Modelos | Políticas, Fuentes de datos, Monitoreo de sesgo, Expedientes |
| Ingeniero de riesgo | Modelos | Modelos y detalle del modelo | Fuentes de datos |

- **Seis vistas funcionan y siete están diferidas.** Las diferidas son las que no sostenían ninguna de las cuatro demos; quedaron declaradas en el menú por rol.
- **Solo cumplimiento ve el paquete de evidencia** de un congelamiento.
- **El rol de operación no tiene vistas en la consola:** trabaja con Grafana, Argo CD y los runbooks.
- La consola está en español, inglés y portugués de Brasil, con tema claro u oscuro.

## Límites de este diagrama

- Solo el recorrido del analista se ejecutó de punta a punta el 27 de noviembre; los de CRO, cumplimiento e ingeniero se probaron por partes en las demos del 20 al 22 de noviembre.
- Los usuarios son sintéticos: ningún analista real ha usado la consola, así que no hay datos de satisfacción ni de tiempos de uso.
- La reactivación de un modelo desde la consola (el modo «presenter» de la demo D2) no se ejecutó de punta a punta; se probó aparte la verificación reforzada.
