// `UserManager` con todo en memoria (BR-U10-05): `userStore` y `stateStore` son `InMemoryWebStorage`; nada en `localStorage`,
// `sessionStorage`, cookies ni IndexedDB. Login con PKCE (S256, por omision en `oidc-client-ts` v3), refresco rotativo con el refresh
// token (`automaticSilentRenew`), login silencioso con `prompt=none` y logout por el `end_session_endpoint`.
//
// Por que el login interactivo es una ventana emergente y no una redireccion: `state` y `code_verifier` viven en memoria y una
// redireccion completa recarga la pagina y los borra. La ventana emergente (abierta en el clic de «Iniciar sesion») los conserva en la
// ventana principal, que ademas nunca cambia de URL (queda sin `code` ni `state`).
import { InMemoryWebStorage, UserManager, type UserManagerSettings, WebStorageStateStore } from "oidc-client-ts";
import type { AppConfig } from "../config/load";
import { FILTER_PROTOCOL_CLAIMS } from "../stepup/oidc";

export const SCOPE = "openid";

/** `navigators` es solo para pruebas: reemplaza los navegadores de redireccion, ventana emergente e iframe de la libreria. */
export function createUserManager(
  config: AppConfig,
  origin: string,
  navigators: ConstructorParameters<typeof UserManager> extends [UserManagerSettings, ...infer Rest] ? Rest : never = [],
): UserManager {
  const memory = (): WebStorageStateStore => new WebStorageStateStore({ store: new InMemoryWebStorage() });
  return new UserManager(
    {
    authority: config.oidc.authority,
    client_id: config.oidc.client_id,
    redirect_uri: config.redirect_uri,
    popup_redirect_uri: config.redirect_uri,
    silent_redirect_uri: config.redirect_uri,
    post_logout_redirect_uri: `${origin}/`,
    response_type: "code",
    scope: SCOPE,
    userStore: memory(),
    stateStore: memory(),
    automaticSilentRenew: true,
    filterProtocolClaims: FILTER_PROTOCOL_CLAIMS,
    loadUserInfo: false,
    },
    ...navigators,
  );
}
