// «MFA reciente» (BR-U10-06): `mfa` y `auth_time` de hace <= `MFA_MAX_AGE_SECONDS` (900 s, el `MFA_MAX_AGE` de U0), leidos de `SessionInfo`.
import { MFA_MAX_AGE_SECONDS } from "../config/constants";

export interface MfaSession {
  readonly mfa: boolean;
  readonly auth_time: string;
}

export function recentMfa(session: MfaSession, nowMs: number): boolean {
  return session.mfa && (nowMs - Date.parse(session.auth_time)) / 1000 <= MFA_MAX_AGE_SECONDS;
}
