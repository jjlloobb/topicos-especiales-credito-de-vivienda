# Pregunta de aclaración — U8 Infrastructure Design

Viene del hallazgo 1 de la revisión del 2026-10-08.

## Contradicción: el core en producción
INF-U8-02 despliega `core-banking-mock` solo en kind y staging, y P-U8-06 dice «en producción
el core es el del banco». Pero:
- §5 de `component-dependency.md` no tiene ningún egress hacia un core real;
- F17 y X01 describen solo el mock: X01 se apoya en Linkerd (L7), que no aplica a un host fuera de la malla;
- el diagrama de `deployment-architecture.md`, que dice ser la vista de producción, dibuja el mock.

Así, en producción `get_case` llamaría a un destino que no existe, y NFR-U8-25 ya define qué
hacer cuando el core no responde. Hay que decidir si el MVP integra el core real o no.

### Clarification Question 1
¿Qué hace case-service con el core en producción?

A) **Core deshabilitado en producción para el MVP**:
   - el value `core.enabled = false` en producción;
   - `get_case` responde `credit_status = no_disponible` **sin llamar** a nada y sin abrir el circuit breaker (no es una falla, es una configuración); la consola lo muestra como «estado de crédito no integrado»;
   - F17 y X01 quedan definidos solo para kind y staging;
   - la integración con el core real queda como pendiente de Operations, con su propio flujo de egress, su revisión de seguridad y su equivalente de X01 (por ejemplo, un egress gateway que solo admita `GET`).

   (Recomendado: FR-INT-01 y US-603 se demuestran con el mock, y el contrato del core real no está definido)

B) **Agregar ya un flujo de egress hacia el core real**:
   - F17 en producción apunta al core del banco por un flujo nuevo de §5 (host, puerto y TLS del banco **[VERIFICAR]**);
   - X01 en L7 pasa a un egress gateway (Envoy, como el de U2) que solo admite `GET /v1/credits/{id}`, porque Linkerd no aplica fuera de la malla;
   - `CoreWriteAttempt` en producción se alimenta de las denegaciones de ese gateway.

X) Other (please describe after [Answer]: tag below)

[Answer]: A
