// `UserManager` del login por redireccion (BR-U10-05; decision del usuario, 2026-11-12). Los TOKENS y el usuario viven en memoria
// (`userStore` = `InMemoryWebStorage`): nada de ellos en el almacenamiento del navegador, cookies ni IndexedDB. Lo unico que sobrevive a
// la redireccion completa es el estado transitorio del flujo (`state`, `code_verifier`, `nonce`), que va en `loginStateStorage` y se borra
// al terminar el callback. Login con PKCE (S256, por omision en `oidc-client-ts` v3), refresco rotativo con el refresh token
// (`automaticSilentRenew`) y logout por el `end_session_endpoint`.
//
// `popup_redirect_uri` y `silent_redirect_uri` vacios: no hay ventana emergente ni iframe en el login (el iframe no puede cargar
// `/callback` bajo la CSP de U2). La recarga se resuelve con otra redireccion con `prompt=none` (`AuthProvider`).
import { InMemoryWebStorage, UserManager, type UserManagerSettings, WebStorageStateStore } from "oidc-client-ts";
import type { AppConfig } from "../config/load";
import { FILTER_PROTOCOL_CLAIMS } from "../stepup/oidc";

export const SCOPE = "openid";

/** `navigators` es solo para pruebas: reemplaza los navegadores de redireccion, ventana emergente e iframe de la libreria. */
export function createUserManager(
  config: AppConfig,
  origin: string,
  loginStateStorage: Storage,
  navigators: ConstructorParameters<typeof UserManager> extends [UserManagerSettings, ...infer Rest] ? Rest : never = [],
): UserManager {
  return new UserManager(
    {
      authority: config.oidc.authority,
      client_id: config.oidc.client_id,
      redirect_uri: config.redirect_uri,
      // Vacios a proposito: `oidc-client-ts` los iguala a `redirect_uri` si faltan, y con `""` `signinPopup` y `signinSilent` sin refresh
      // token fallan ("No ... configured") en vez de abrir una ventana o un iframe.
      popup_redirect_uri: "",
      silent_redirect_uri: "",
      post_logout_redirect_uri: `${origin}/`,
      response_type: "code",
      scope: SCOPE,
      userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
      stateStore: new WebStorageStateStore({ store: loginStateStorage }),
      automaticSilentRenew: true,
      filterProtocolClaims: FILTER_PROTOCOL_CLAIMS,
      loadUserInfo: false,
    },
    ...navigators,
  );
}
