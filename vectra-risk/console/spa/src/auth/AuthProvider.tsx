// `AuthProvider` (BR-U10-05): la sesion en memoria. Al montar intenta el login silencioso (`prompt=none`); sin sesion queda
// `anonymous` y la vista muestra el boton de login. `get_me` se pide tras cada token nuevo (`userLoaded`: login, refresco, step-up).
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { User } from "oidc-client-ts";
import type { SessionInfo } from "../api/endpoints";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export interface AuthManager {
  getUser(): Promise<User | null>;
  signinSilent(): Promise<User | null>;
  signinPopup(): Promise<User>;
  signoutRedirect(): Promise<void>;
  readonly events: {
    addUserLoaded(callback: (user: User) => void): void;
    removeUserLoaded(callback: (user: User) => void): void;
  };
}

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
  /** El login interactivo fallo (ventana bloqueada o cerrada): la vista muestra `login_failed`. */
  readonly loginFailed: boolean;
  /** Llamar **dentro del manejador del clic**: la ventana emergente se abre en ese clic. */
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
  readonly children: ReactNode;
}

export function AuthProvider({ manager, loadSession, tokens, children }: Props) {
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
    // Recarga o pestana nueva: `prompt=none` contra la sesion del IdP; sin sesion (o con un error) se muestra el login.
    void manager
      .getUser()
      .then((user) => user ?? manager.signinSilent())
      .then(async (user) => (user === null ? setStatus("anonymous") : accept(user)))
      .catch(() => {
        setStatus("anonymous");
      });
    return () => {
      manager.events.removeUserLoaded(onLoaded);
    };
  }, [manager, accept]);

  const api = useMemo<AuthApi>(
    () => ({
      status,
      session,
      loginFailed,
      login: () => {
        setLoginFailed(false);
        manager.signinPopup().catch(() => {
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
