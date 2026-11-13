// Constantes del codigo, iguales en todos los entornos (domain-entities §4 de U10, segunda tabla).
// Cambiarlas es un cambio de codigo con su PR y sus pruebas; `config.json` no puede traerlas (load.ts).

/** BR-U10-06: vigencia de la ventana de step-up. */
export const STEPUP_TIMEOUT_SECONDS = 300;
/** BR-U10-20: aviso de inactividad. */
export const IDLE_WARNING_SECONDS = 1500;
/** BR-U10-20: cierre por inactividad; igual a `ssoSessionIdleTimeout` de los tres `realm.{env}.yaml` de U2. */
export const IDLE_LOGOUT_SECONDS = 1800;
/** BR-U10-20: difusion de actividad entre pestanas. */
export const ACTIVITY_BROADCAST_SECONDS = 30;
/** BR-U10-21: consulta de `version.json`. */
export const VERSION_POLL_SECONDS = 300;
/** BR-U10-22: limite del `reporter` de errores del cliente. */
export const REPORTER_MAX_PER_MINUTE = 10;
/** P-U10-04: timeout de la API desde la SPA (mayor que los 9 s del presupuesto del BFF). */
export const API_TIMEOUT_SECONDS = 10;
/** BR-U10-10: refresco de la bandeja. */
export const INBOX_REFRESH_SECONDS = 15;
/** BR-U10-10: refresco del caso; empieza en `CASE_REFRESH_SECONDS` y llega a `CASE_REFRESH_MAX_SECONDS`. */
export const CASE_REFRESH_SECONDS = 3;
export const CASE_REFRESH_MAX_SECONDS = 120;

/**
 * BR-U10-06: «MFA reciente» = `auth_time` de hace <= 900 s. Es `MFA_MAX_AGE` de U0 (`vectra_contracts.routes`, BR-U0-72): una prueba
 * (`config.test.ts`) lee ese archivo y la ata. No esta en domain-entities §4 (candidata de diseno) y no es de `TIME_CONSTANTS`.
 */
export const MFA_MAX_AGE_SECONDS = 900;

export const TIME_CONSTANTS = {
  STEPUP_TIMEOUT_SECONDS,
  IDLE_WARNING_SECONDS,
  IDLE_LOGOUT_SECONDS,
  ACTIVITY_BROADCAST_SECONDS,
  VERSION_POLL_SECONDS,
  REPORTER_MAX_PER_MINUTE,
  API_TIMEOUT_SECONDS,
  INBOX_REFRESH_SECONDS,
  CASE_REFRESH_SECONDS,
  CASE_REFRESH_MAX_SECONDS,
} as const;
