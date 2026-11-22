// `AuthProvider` (BR-U10-05): la sesion en memoria, con login por REDIRECCION (decision del usuario, 2026-11-12).
//  - Al cargar en `/callback?...state=...` procesa la respuesta (canje del codigo), limpia la URL y sigue en la misma pagina: los tokens
//    viven en memoria y una recarga completa los perderia.
//  - Al cargar sin sesion en memoria hace UNA redireccion con `prompt=none`; si el emisor responde con un error (`login_required`...) queda
//    `anonymous` y la vista muestra el login interactivo. Nunca encadena redirecciones: despues de un callback no vuelve a redirigir.
//  - El login interactivo es `signinRedirect` en el clic. Ni ventana emergente, ni iframe, ni `signinSilent`.
//  - `get_me` se pide tras cada token nuevo (`userLoaded`: login, refresco, step-up).
//  - La ruta pedida (ruta + query) viaja en los datos del flujo (`returnTo`) y vuelve con la respuesta, con exito o con error: tras el
//    login la SPA vuelve a ella (`takeReturnTo`, una sola vez) en lugar de caer siempre en el inicio del rol (H-12; `returnTo.ts`).
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { User } from "oidc-client-ts";
import type { SessionInfo } from "../api/endpoints";
import { type LanguageTag, uiLocales } from "../i18n/language";
import { restorablePath } from "./returnTo";

/** Que intento el flujo en curso: viaja en el `state` de la libreria y vuelve con la respuesta, tambien con un error. */
export interface FlowData {
  readonly mode: "silent" | "interactive";
  /** La ruta interna (ruta + query) que se pidio al cargar la pagina; se valida al guardarla y otra vez al leerla (`returnTo.ts`). */
  readonly returnTo?: string;
}

export interface SigninArgs {
  readonly prompt?: "none";
  readonly state: FlowData;
  readonly nonce: string;
  /**
   * El idioma de la consola (`es`, `en` o `pt-BR`, que es como Keycloak nombra el portugues de Brasil; nunca texto libre), como el parametro estandar `ui_locales` de OIDC: el login del emisor sale en
   * el mismo idioma y la persona no lo elige dos veces (enmienda del 2026-11-21). No cambia nada mas del flujo.
   */
  readonly ui_locales: LanguageTag;
}

export interface AuthManager {
  getUser(): Promise<User | null>;
  signinRedirect(args: SigninArgs): Promise<void>;
  signinCallback(url: string): Promise<User | undefined | void>;
  signoutRedirect(): Promise<void>;
  readonly events: {
    addUserLoaded(callback: (user: User) => void): void;
    removeUserLoaded(callback: (user: User) => void): void;
  };
}

/** La pagina donde vive la SPA: de aqui sale la respuesta del callback y aqui se limpia la URL (`code` y `state` no se quedan). */
export interface AuthPage {
  /** La URL completa si la pagina es `/callback` con un `state`; si no, `null`. */
  callbackUrl(): string | null;
  /** Si la pagina es `/callback`, reemplaza la URL por `/` (sin recargar). */
  clean(): void;
  /** La ruta + query de la pagina si es un destino interno al que volver tras el login; si no (`/`, `/callback`, una ruta ajena), `null`. */
  target(): string | null;
}

export function browserPage(win: Window = window): AuthPage {
  return {
    callbackUrl: () => (win.location.pathname === "/callback" && win.location.search.includes("state=") ? win.location.href : null),
    clean: () => {
      if (win.location.pathname === "/callback") win.history.replaceState(null, "", "/");
    },
    target: () => restorablePath(`${win.location.pathname}${win.location.search}`),
  };
}

/** Los datos de un flujo nuevo: `returnTo` solo si hay un destino al que volver. */
function flowData(mode: FlowData["mode"], returnTo: string | null): FlowData {
  return returnTo === null ? { mode } : { mode, returnTo };
}

/** El destino que traen los datos del flujo de una respuesta (un `User` o un `ErrorResponse`), ya validado; `null` si no hay o no vale. */
function returnToOf(carrier: unknown): string | null {
  const state = typeof carrier === "object" && carrier !== null ? (carrier as { state?: unknown }).state : undefined;
  return typeof state === "object" && state !== null ? restorablePath((state as Partial<FlowData>).returnTo) : null;
}

function isSilentError(error: unknown): boolean {
  const state = typeof error === "object" && error !== null ? (error as { state?: unknown }).state : undefined;
  return typeof state === "object" && state !== null && (state as Partial<FlowData>).mode === "silent";
}

const newNonce = (): string => globalThis.crypto.randomUUID();

export type AuthStatus = "loading" | "anonymous" | "authenticated";

/** El access token vive solo aqui, en memoria; lo leen `api` y `reporter` sin pasar por React. */
export interface TokenStore {
  get(): string | null;
  set(token: string | null): void;
}

export function createTokenStore(): TokenStore {
  let current: string | null = null;
  return {
    get: () => current,
    set: (token) => {
      current = token;
    },
  };
}

export interface AuthApi {
  readonly status: AuthStatus;
  readonly session: SessionInfo | null;
  /** El login interactivo fallo (el emisor o el canje dieron error): la vista muestra `login_failed`. */
  readonly loginFailed: boolean;
  /** Redirige al emisor (`signinRedirect`). */
  readonly login: () => void;
  readonly logout: () => void;
  readonly getToken: () => string | null;
  /** El destino pedido antes del login, si lo hubo: se entrega UNA vez (despues, `null`). Quien lo usa comprueba el rol. */
  readonly takeReturnTo: () => string | null;
}

const Context = createContext<AuthApi | null>(null);

export function useAuth(): AuthApi {
  const api = useContext(Context);
  if (api === null) throw new Error("useAuth fuera de AuthProvider");
  return api;
}

interface Props {
  readonly manager: AuthManager;
  /** `get_me` con el token dado. */
  readonly loadSession: (token: string) => Promise<SessionInfo>;
  readonly tokens: TokenStore;
  /** Por omision, la pagina del navegador. */
  readonly page?: AuthPage;
  readonly children: ReactNode;
}

async function start(
  manager: AuthManager,
  page: AuthPage,
  accept: (user: User) => Promise<void>,
  setStatus: (status: AuthStatus) => void,
  setLoginFailed: (failed: boolean) => void,
  keepReturnTo: (target: string | null) => void,
  expectCallbackUser: () => void,
): Promise<void> {
  try {
    const callback = page.callbackUrl();
    page.clean();
    if (callback !== null) {
      // El canje ya dispara `userLoaded` (-> `accept`). Un error NO redirige otra vez: queda el login interactivo.
      try {
        expectCallbackUser();
        if ((await manager.signinCallback(callback)) === undefined) setStatus("anonymous");
      } catch (error) {
        // El `prompt=none` no entro: el destino pedido se conserva en memoria para el login interactivo que sigue.
        keepReturnTo(returnToOf(error));
        setLoginFailed(!isSilentError(error));
        setStatus("anonymous");
      }
      return;
    }
    const user = await manager.getUser();
    if (user !== null) {
      await accept(user);
      return;
    }
    // Recarga o pestana nueva: `prompt=none` contra la sesion del emisor (una redireccion completa; sin iframe).
    await manager.signinRedirect({ prompt: "none", state: flowData("silent", page.target()), nonce: newNonce(), ui_locales: uiLocales() });
  } catch {
    setStatus("anonymous");
  }
}

export function AuthProvider({ manager, loadSession, tokens, page, children }: Props) {
  const started = useRef(false);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loginFailed, setLoginFailed] = useState(false);
  // El destino pedido antes del login: llega con la respuesta del emisor y se entrega una vez (`takeReturnTo`). Solo en memoria.
  const returnTo = useRef<string | null>(null);
  const fromCallback = useRef(false);
  const currentPage = useMemo(() => page ?? browserPage(), [page]);

  const accept = useCallback(
    async (user: User): Promise<void> => {
      // Solo el usuario que sale del callback del login trae un destino (un refresco o un step-up nunca lo cambian), y se lee antes de
      // pedir `get_me`: cuando la sesion quede lista, el enrutador ya lo encuentra.
      if (fromCallback.current) {
        fromCallback.current = false;
        returnTo.current = returnToOf(user);
      }
      tokens.set(user.access_token);
      try {
        setSession(await loadSession(user.access_token));
        setStatus("authenticated");
      } catch {
        tokens.set(null); // sin `get_me` no hay sesion utilizable
        setStatus("anonymous");
      }
    },
    [loadSession, tokens],
  );

  useEffect(() => {
    const onLoaded = (user: User): void => {
      void accept(user);
    };
    manager.events.addUserLoaded(onLoaded);
    // Una sola vez por carga de pagina (el codigo del callback se canjea una vez; StrictMode monta dos veces).
    if (!started.current) {
      started.current = true;
      void start(
        manager,
        currentPage,
        accept,
        setStatus,
        setLoginFailed,
        (target) => {
          fromCallback.current = false;
          returnTo.current = target;
        },
        () => {
          fromCallback.current = true;
        },
      );
    }
    return () => {
      manager.events.removeUserLoaded(onLoaded);
    };
  }, [manager, currentPage, accept]);

  const api = useMemo<AuthApi>(
    () => ({
      status,
      session,
      loginFailed,
      login: () => {
        setLoginFailed(false);
        // El destino: el que quedo de un `prompt=none` fallido (la URL ya esta limpia) o, si no, la pagina actual.
        manager.signinRedirect({ state: flowData("interactive", returnTo.current ?? currentPage.target()), nonce: newNonce(), ui_locales: uiLocales() }).catch(() => {
          setLoginFailed(true);
        });
      },
      logout: () => {
        returnTo.current = null;
        tokens.set(null);
        setSession(null);
        setStatus("anonymous");
        manager.signoutRedirect().catch(() => undefined);
      },
      getToken: () => tokens.get(),
      takeReturnTo: () => {
        const target = returnTo.current;
        returnTo.current = null;
        return target;
      },
    }),
    [status, session, loginFailed, manager, tokens, currentPage],
  );

  return <Context.Provider value={api}>{children}</Context.Provider>;
}
