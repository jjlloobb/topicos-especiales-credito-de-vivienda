# Restore del sitio (NFR-U1-07; RTO ≤ 4 h)

## Síntoma
Pérdida del sitio o simulacro.

## Impacto
Sin ruta de recomendación ni registro hasta restaurar.

## Diagnóstico
1. Comprueba el último backup: `kubectl get backups.postgresql.cnpg.io -n vectra-data`.

## Mitigación
1. Instala en un clúster limpio con `install.md`.
2. Restaura `registry-db` desde el backup base y el WAL.
3. Ejecuta `vectra-registry verify --mode full`.
4. Restaura `case-db` y ejecuta `case-retention` con el rol `case_retention`, antes de abrir tráfico.

## Escalamiento
SEV1: COE en 5 días hábiles.

## Verificación
- `vectra-registry verify --mode full` devuelve `integra`.
- `case-retention --count-expired` devuelve 0.
- `kubectl get pods -A` con los servicios en `Ready`.
