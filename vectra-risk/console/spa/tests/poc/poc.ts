// PoC del Paso 10 (puerta de los Pasos 11 a 15): el step-up en una ventana emergente con `OidcClient` de bajo nivel, usando el
// mismo `StepUpFlow` que usara la SPA. La pagina deja en `window.__poc` lo que la prueba necesita para afirmar.
import { InMemoryWebStorage, OidcClient, WebStorageStateStore } from "oidc-client-ts";
import { StepUpFlow, browserTimers } from "../../src/stepup/flow";
import { FILTER_PROTOCOL_CLAIMS, createOidcBackend } from "../../src/stepup/oidc";

interface Body {
  readonly justification: string;
}

interface PocWindow extends Window {
  __poc: {
    opens: { inClick: boolean }[];
    result: { acr: unknown; auth_time: unknown } | null;
    sent: Body[];
    messages: { origin: string; fromPopup: boolean }[];
    /** `?probe=open-outside-click`: el `window.open` de la carga de la pagina (sin clic) quedo bloqueado. */
    outsideClickBlocked: boolean | null;
  };
}

const poc: PocWindow["__poc"] = { opens: [], result: null, sent: [], messages: [], outsideClickBlocked: null };
(window as unknown as PocWindow).__poc = poc;

// Instrumento: `window.open` dentro del despacho del clic (entre la captura y la burbuja de `window`) o fuera de el.
let inClick = false;
document.addEventListener("click", () => (inClick = true), true);
window.addEventListener("click", () => (inClick = false));
const nativeOpen = window.open.bind(window);
window.open = (...args: Parameters<typeof window.open>) => {
  poc.opens.push({ inClick });
  return nativeOpen(...args);
};

// P-2: un `window.open` sin clic detras (al cargar la pagina; ninguna evaluacion de la prueba le da activacion de usuario).
if (new URLSearchParams(window.location.search).get("probe") === "open-outside-click") {
  poc.outsideClickBlocked = window.open("about:blank", "fuera-del-clic") === null;
}

const origin = window.location.origin;
const stepupRedirectUri = `${origin}/stepup-callback`;
const store = new WebStorageStateStore({ store: new InMemoryWebStorage() });
const client = new OidcClient({
  authority: `${origin}/auth/realms/vectra`,
  client_id: "vectra-console",
  redirect_uri: stepupRedirectUri,
  response_type: "code",
  scope: "openid",
  filterProtocolClaims: FILTER_PROTOCOL_CLAIMS,
  stateStore: store,
});

const button = document.getElementById("verify") as HTMLButtonElement;
const status = document.getElementById("status") as HTMLElement;

const flow = new StepUpFlow<Body>({
  ownOrigin: origin,
  stepupRedirectUri,
  backend: createOidcBackend(client, store, stepupRedirectUri, (response) => {
    poc.result = { acr: response.profile["acr"], auth_time: response.profile["auth_time"] };
  }),
  openWindow: () => window.open("", "vectra-stepup"),
  send: async (body) => {
    poc.sent.push(body);
    return true;
  },
  timers: browserTimers,
  announce: () => undefined,
  restoreFocus: () => button.focus(),
  reportFailure: () => undefined,
});

flow.subscribe((state) => {
  status.textContent = state.phase === "failed" ? `failed:${state.failure}` : state.phase;
});
window.addEventListener("message", (event) => {
  poc.messages.push({ origin: event.origin, fromPopup: event.source !== null && event.source !== window });
  flow.handleMessage(event);
});
button.addEventListener("click", () => {
  flow.start({ justification: "justificacion de la PoC" });
});
