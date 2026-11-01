# Rotación del trust anchor de Linkerd (P-U1-03)

## Síntoma
`CertificateExpiringSoon` del ancla, 30 días antes del vencimiento.

## Impacto
Si vence, se pierde el mTLS de toda la malla.

## Diagnóstico
1. `cmctl status certificate linkerd-trust-anchor -n cert-manager`.

## Mitigación
1. Publica los dos anclas en paralelo en el bundle de Linkerd, por PR.
2. Rota el issuer y reinicia los proxies de forma gradual tras la aprobación.
3. Retira el ancla anterior por PR.

## Escalamiento
SEV2: COE en 5 días hábiles.

## Verificación
- `linkerd check --proxy` sin errores.
- `cmctl status certificate linkerd-identity-issuer -n linkerd`.
