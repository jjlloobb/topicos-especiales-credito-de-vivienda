// Los metadatos del emisor OIDC, configurados a mano (U10-T06). La SPA NO pide `.well-known/openid-configuration`: en kind ese documento
// responde 500 (Keycloak 26.8.1, `Duplicate key 2`: defecto conocido de U2) y, con `authority` solo, `oidc-client-ts` lo pide antes de
// redirigir. Con `metadata` la libreria usa estos valores y no hace ninguna peticion de descubrimiento.
//
// Solo lo que la SPA usa de verdad (BR-U10-05 y BR-U10-06): `authorization_endpoint` (login, recarga con `prompt=none` y step-up),
// `token_endpoint` (canje del codigo y refresco), `end_session_endpoint` (logout) e `issuer`. No hay `jwks_uri` (la libreria no valida la firma
// del ID token en el navegador: solo decodifica y comprueba `sub` y `nonce`; la firma y el `iss`/`aud` los valida el BFF sobre el access
// token) ni `userinfo_endpoint` (`loadUserInfo: false`).
import type { OidcMetadata } from "oidc-client-ts";

/**
 * Las rutas de Keycloak para un realm, relativas al emisor (`oidc.authority`, `https://<host>/auth/realms/vectra`). Es el unico sitio donde
 * viven: `tests/unit/auth/issuer-metadata.test.ts` las ata a las rutas de `/auth` de `identity-edge/gateway/routes.yaml`.
 */
export const ENDPOINT_PATHS = {
  authorization: "/protocol/openid-connect/auth",
  token: "/protocol/openid-connect/token",
  endSession: "/protocol/openid-connect/logout",
} as const;

export function issuerMetadata(authority: string): Partial<OidcMetadata> {
  const issuer = authority.replace(/\/+$/, "");
  return {
    issuer,
    authorization_endpoint: `${issuer}${ENDPOINT_PATHS.authorization}`,
    token_endpoint: `${issuer}${ENDPOINT_PATHS.token}`,
    end_session_endpoint: `${issuer}${ENDPOINT_PATHS.endSession}`,
  };
}
