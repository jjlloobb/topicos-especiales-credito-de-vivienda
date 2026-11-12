// `StepUpBackend` sobre la API de bajo nivel de `oidc-client-ts` (P-U10-07): `OidcClient` con su propio `stateStore` en memoria.
// `signinPopup` no se usa: abre la ventana por su cuenta y procesa la respuesta dentro de ella (BR-U10-06).
import type { OidcClient, SigninResponse, StateStore } from "oidc-client-ts";
import type { StepUpBackend } from "./flow";

export const STEPUP_ACR = "mfa";

/**
 * `oidc-client-ts` quita de `profile` los claims de protocolo `nbf, jti, auth_time, nonce, acr, amr, azp, at_hash`. Aqui hacen falta
 * `acr` (comprobar el MFA) y `auth_time` (la frescura de la sesion): se filtran solo los demas. Lo usan el `OidcClient` del step-up
 * y el `UserManager` de `auth`.
 */
export const FILTER_PROTOCOL_CLAIMS: string[] = ["nbf", "jti", "nonce", "amr", "azp", "at_hash"];

export function createOidcBackend(
  client: OidcClient,
  store: StateStore,
  stepupRedirectUri: string,
  accept: (response: SigninResponse) => void,
): StepUpBackend {
  return {
    async createRequest() {
      const request = await client.createSigninRequest({
        redirect_uri: stepupRedirectUri,
        prompt: "login",
        max_age: 0,
        acr_values: STEPUP_ACR,
        // el `nonce` en memoria: el ID token del canje tiene que traerlo de vuelta (la libreria no lo genera en el flujo de codigo)
        nonce: crypto.randomUUID(),
      });
      return { url: request.url, id: request.state.id };
    },
    async exchange(callbackUrl) {
      try {
        const response = await client.processSigninResponse(callbackUrl);
        if (response.profile["acr"] !== STEPUP_ACR) return "no_mfa";
        accept(response);
        return "ok";
      } catch {
        return "failed";
      }
    },
    async removeState(id) {
      await store.remove(id);
    },
  };
}
