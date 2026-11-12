// `AuthProvider` (BR-U10-05): la sesion en memoria, con login por REDIRECCION (decision del usuario, 2026-11-12).
//  - Al cargar en `/callback?...state=...` procesa la respuesta (canje del codigo), limpia la URL y sigue en la misma pagina: los tokens
//    viven en memoria y una recarga completa los perderia.
//  - Al cargar sin sesion en memoria hace UNA redireccion con `prompt=none`; si el emisor responde con un error (`login_required`...) queda
//    `anonymous` y la vista muestra el login interactivo. Nunca encadena redirecciones: despues de un callback no vuelve a redirigir.
//  - El login interactivo es `signinRedirect` en el clic. Ni ventana emergente, ni iframe, ni `signinSilent`.
//  - `get_me` se pide tras cada token nuevo (`userLoaded`: login, refresco, step-up).
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { User } from "oidc-client-ts";
import type { SessionInfo } from "../api/endpoints";

/** Que intento el flujo en curso: viaja en el `state` de la libreria y vuelve con la respuesta, tambien con un error. */
export interface FlowData {
  readonly mode: "silent" | "interactive";
}

export interface SigninArgs {
  readonly prompt?: "none";
  readonly state: FlowData;
  readonly nonce: string;
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
}

export function browserPage(win: Window = window): AuthPage {
  return {
    callbackUrl: () => (win.location.pathname === "/callback" && win.location.search.includes("state=") ? win.location.href : null),
    clean: () => {
      if (win.location.pathname === "/callback") win.history.replaceState(null, "", "/");
    },
  };
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
): Promise<void> {
  try {
    const callback = page.callbackUrl();
    page.clean();
    if (callback !== null) {
      // El canje ya dispara `userLoaded` (-> `accept`). Un error NO redirige otra vez: queda el login interactivo.
      try {
        if ((await manager.signinCallback(callback)) === undefined) setStatus("anonymous");
      } catch (error) {
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
    await manager.signinRedirect({ prompt: "none", state: { mode: "silent" }, nonce: newNonce() });
  } catch {
    setStatus("anonymous");
  }
}

export function AuthProvider({ manager, loadSession, tokens, page, children }: Props) {
  const started = useRef(false);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loginFailed, setLoginFailed] = useState(false);

  const accept = useCallback(
    async (user: User): Promise<void> => {
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
      void start(manager, page ?? browserPage(), accept, setStatus, setLoginFailed);
    }
    return () => {
      manager.events.removeUserLoaded(onLoaded);
    };
  }, [manager, page, accept]);

  const api = useMemo<AuthApi>(
    () => ({
      status,
      session,
      loginFailed,
      login: () => {
        setLoginFailed(false);
        manager.signinRedirect({ state: { mode: "interactive" }, nonce: newNonce() }).catch(() => {
          setLoginFailed(true);
        });
      },
      logout: () => {
        tokens.set(null);
        setSession(null);
        setStatus("anonymous");
        manager.signoutRedirect().catch(() => undefined);
      },
      getToken: () => tokens.get(),
    }),
    [status, session, loginFailed, manager, tokens],
  );

  return <Context.Provider value={api}>{children}</Context.Provider>;
}
