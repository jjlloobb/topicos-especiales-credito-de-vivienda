# CompensationEventPending

Alerta `CompensationEventPending` (SEV2) de `governance/observability/governance-rules.yaml`: `max(vectra_governance_compensation_events_pending) > 0` durante 1 minuto (BR-U4-17; P-3 de `demo-recorte-funcional.md`).

## Síntoma

La métrica `vectra_governance_compensation_events_pending` es mayor que 0: hay una compensación `transicion_descartada` en `transitions` con `kind = 'compensacion'` y `status = 'pendiente_registro'` que todavía no se escribió en el registro de decisiones (U3).

## Impacto

Una transición se descartó (el estado cambió, la unidad quedó incompleta o se abandonó) pero su evento ya estaba escrito en la cadena sin efecto; la compensación es lo que lo marca así. Mientras esté pendiente, la cadena no dice que ese evento no tuvo efecto y el modelo afectado no admite `frozen_resolution` (409 `transition_pending`). Una compensación nunca pasa a `abandonada`: sigue pendiente hasta que se escribe.

## Diagnóstico

1. ¿El registro responde? `kubectl --context kind-vectra -n vectra-app get deploy decision-registry-service` y su `/readyz` (puerto 8081). Si cayó, es la causa: sigue `decision-registry/runbooks/` y `platform/runbooks/registry-db-writes-blocked.md`.
2. Qué compensaciones faltan:

```bash
kubectl --context kind-vectra -n vectra-data exec governance-db-1 -c postgres -- psql -d governance -c \
  "SELECT transition_id, entity_id, created_at, event_payload->'entry'->'payload'->'details'->>'reason' AS motivo FROM transitions WHERE kind = 'compensacion' AND status = 'pendiente_registro' ORDER BY created_at"
```

3. ¿El reconciliador corre? El gauge `vectra_governance_compensation_events_pending` se publica en cada réplica (se agrega con `max`); si falta, mira los logs: `kubectl --context kind-vectra -n vectra-app logs deploy/governance-service | grep reconcil`.
4. Un 409 del registro (la misma llave con otro contenido, BR-U3-06) deja la compensación pendiente sin reintento útil: búscalo en los logs del registro.

## Mitigación

1. Restablece el registro (causa más común). El reconciliador reintenta con la misma `idempotency_key`; el reintento devuelve el ack original y no duplica el evento.
2. No edites `transitions` a mano ni marques la compensación como `confirmada`: la evidencia debe salir del registro.
3. Si el registro responde y la compensación no avanza tras unos minutos, reinicia las réplicas de a una: `kubectl --context kind-vectra -n vectra-app rollout restart deploy/governance-service` (el PDB deja una en pie).

## Escalamiento

Si pasa de 1 hora o hay un 409 persistente, escala al responsable de U3 (el registro) y a `cumplimiento`: la cadena de evidencia de un modelo quedó incompleta. Registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# El gauge vuelve a 0 (desde un pod con curl, a 8081 de una réplica):
kubectl --context kind-vectra -n vectra-app exec deploy/governance-service -- python -c "import urllib.request;print([l for l in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if l.startswith('vectra_governance_compensation_events_pending')])"
# Ninguna compensación pendiente en la base:
kubectl --context kind-vectra -n vectra-data exec governance-db-1 -c postgres -- psql -d governance -tAc "SELECT count(*) FROM transitions WHERE kind = 'compensacion' AND status = 'pendiente_registro'"
```

Esperado: el gauge en `0.0` y el conteo en `0`.
