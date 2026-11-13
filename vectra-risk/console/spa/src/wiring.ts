// El cableado real de la SPA: `config.json` -> `UserManager`, cliente de la API, `reporter`, TanStack Query y los entornos de `stepup` e
// `inactivity`. `App` recibe este objeto: las pruebas le pasan uno con dobles.
import type { QueryClient } from "@tanstack/react-query";
import { InMemoryWebStorage, OidcClient, type SigninResponse, User, type UserManager, WebStorageStateStore } from "oidc-client-ts";
import { type ApiClient, createApi } from "./api/client";
import { createQueryClient } from "./api/queryClient";
import { type SessionInfo, getMe } from "./api/endpoints";
import { type AuthManager, type AuthPage, browserPage, createTokenStore, type TokenStore } from "./auth/AuthProvider";
import { createLoginStateStorage } from "./auth/loginStateStorage";
import { createUserManager, SCOPE } from "./auth/manager";
import type { AppConfig } from "./config/load";
import { browserInactivityEnv, type InactivityEnv } from "./inactivity/InactivityProvider";
import { APP_VERSION } from "./reporter/version";
import { Reporter } from "./reporter/reporter";
import { browserTimers } from "./stepup/flow";
import { createOidcBackend, FILTER_PROTOCOL_CLAIMS } from "./stepup/oidc";
import type { StepUpEnv } from "./stepup/StepUpProvider";
import { routeTemplate } from "./views/shared/routes";

export interface Wiring {
  readonly manager: AuthManager;
  readonly authPage: AuthPage;
  readonly tokens: TokenStore;
  readonly queryClient: QueryClient;
  /** El cliente de la API de las vistas: toma el token de la memoria en cada solicitud. */
  readonly api: ApiClient;
  readonly loadSession: (token: string) => Promise<SessionInfo>;
  readonly reporter: Reporter;
  readonly stepUpEnv: StepUpEnv;
  readonly inactivityEnv: InactivityEnv;
}

const STEPUP_WINDOW = "vectra-stepup";

/**
 * Los tokens del step-up reemplazan a los de la sesion en memoria (BR-U10-06). `storeUser` solo guarda: `events.load` ademas rearma los
 * temporizadores de expiracion del refresco automatico y avisa `userLoaded` (que pide `get_me` otra vez, ya con `acr = mfa`).
 */
export async function acceptStepUp(manager: UserManager, response: SigninResponse): Promise<void> {
  const user = new User(response);
  await manager.storeUser(user);
  await manager.events.load(user);
}

export function createWiring(config: AppConfig, win: Window = window): Wiring {
  const origin = win.location.origin;
  const tokens = createTokenStore();
  const manager = createUserManager(config, origin, createLoginStateStorage(win));
  const reporter = new Reporter({
    endpoint: "/api/console/client-errors",
    getToken: () => tokens.get(),
    routeTemplate: () => routeTemplate(win.location.pathname),
    appVersion: APP_VERSION,
  });
  const apiFor = (token: string | null) =>
    createApi({ baseUrl: origin, getToken: () => token, onContractMismatch: () => reporter.report("api_contract_mismatch") });
  // El step-up usa la API de bajo nivel (`OidcClient`) con su propio `stateStore` en memoria (P-U10-07).
  const stepUpStore = new WebStorageStateStore({ store: new InMemoryWebStorage() });
  const stepUpClient = new OidcClient({
    authority: config.oidc.authority,
    client_id: config.oidc.client_id,
    redirect_uri: config.stepup_redirect_uri,
    response_type: "code",
    scope: SCOPE,
    filterProtocolClaims: FILTER_PROTOCOL_CLAIMS,
    stateStore: stepUpStore,
  });
  return {
    manager,
    api: createApi({ baseUrl: origin, getToken: () => tokens.get(), onContractMismatch: () => reporter.report("api_contract_mismatch") }),
    authPage: browserPage(win),
    tokens,
    queryClient: createQueryClient(),
    loadSession: (token) => getMe(apiFor(token), () => reporter.report("api_contract_mismatch")),
    reporter,
    stepUpEnv: {
      ownOrigin: origin,
      stepupRedirectUri: config.stepup_redirect_uri,
      backend: createOidcBackend(stepUpClient, stepUpStore, config.stepup_redirect_uri, (response) => acceptStepUp(manager, response)),
      openWindow: () => win.open("", STEPUP_WINDOW),
      timers: browserTimers,
      reportFailure: () => reporter.report("stepup_failed"),
      now: () => Date.now(),
      messageTarget: win,
    },
    inactivityEnv: browserInactivityEnv,
  };
}
