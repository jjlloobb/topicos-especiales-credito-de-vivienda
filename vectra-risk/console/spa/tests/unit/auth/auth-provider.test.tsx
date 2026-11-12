// @vitest-environment jsdom
// BR-U10-05: `AuthProvider` con un `AuthManager` falso: callback del login por redireccion, recarga con `prompt=none` (una vez, sin bucle),
// `get_me` tras cada token nuevo, login interactivo y logout.
import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { User } from "oidc-client-ts";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionInfo } from "../../../src/api/endpoints";
import { type AuthManager, AuthProvider, browserPage, createTokenStore, type SigninArgs, useAuth } from "../../../src/auth/AuthProvider";

afterEach(cleanup);

const SESSION: SessionInfo = { role: "analista", mfa: false, auth_time: "2026-11-12T15:00:00Z", locale: "es-CO" };
const user = (token: string): User => ({ access_token: token }) as User;

/** Lo que el emisor devuelve a `/callback` con un error: la forma de `ErrorResponse` de `oidc-client-ts` (`state` = los datos del flujo). */
const errorResponse = (error: string, mode?: "silent" | "interactive") =>
  Object.assign(new Error(error), { error, state: mode === undefined ? undefined : { mode } });

function fakeManager(over: Partial<AuthManager> = {}) {
  const listeners = new Set<(user: User) => void>();
  const manager: AuthManager = {
    getUser: vi.fn(async () => null),
    signinRedirect: vi.fn(async () => undefined),
    signinCallback: vi.fn(async () => undefined),
    signoutRedirect: vi.fn(async () => undefined),
    events: {
      addUserLoaded: (cb) => listeners.add(cb),
      removeUserLoaded: (cb) => listeners.delete(cb),
    },
    ...over,
  };
  return { manager, listeners };
}

const CALLBACK_URL = "http://localhost/callback?code=c&state=s";
/** La pagina del navegador: en `/` o, si se da una URL, en `/callback`. */
function fakePage(callback: string | null = null) {
  return { callbackUrl: vi.fn(() => callback), clean: vi.fn() };
}

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="role">{auth.session?.role ?? "-"}</p>
      <p data-testid="token">{auth.getToken() ?? "-"}</p>
      <p data-testid="failed">{String(auth.loginFailed)}</p>
      <button type="button" onClick={auth.login}>
        entrar
      </button>
      <button type="button" onClick={auth.logout}>
        salir
      </button>
    </div>
  );
}

function mount(manager: AuthManager, loadSession = vi.fn(async (_token: string) => SESSION), page = fakePage()) {
  const tokens = createTokenStore();
  render(
    <AuthProvider manager={manager} loadSession={loadSession} tokens={tokens} page={page}>
      <Probe />
    </AuthProvider>,
  );
  return { tokens, loadSession, page };
}

const text = (id: string) => screen.getByTestId(id).textContent;

describe("AuthProvider", () => {
  it("recarga sin sesion en memoria: UNA redireccion con prompt=none y nonce; mientras tanto sigue `loading`", async () => {
    const { manager } = fakeManager();
    mount(manager);
    await waitFor(() => expect(manager.signinRedirect).toHaveBeenCalledOnce());
    expect(manager.signinRedirect).toHaveBeenCalledWith({ prompt: "none", state: { mode: "silent" }, nonce: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    expect(manager.signinCallback).not.toHaveBeenCalled();
    expect(text("status")).toBe("loading");
  });

  it("un usuario ya en memoria no redirige", async () => {
    const { manager } = fakeManager({ getUser: vi.fn(async () => user("en-memoria")) });
    mount(manager);
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    expect(manager.signinRedirect).not.toHaveBeenCalled();
  });

  it("una redireccion prompt=none que falla al empezar deja `anonymous`", async () => {
    mount(fakeManager({ signinRedirect: vi.fn(async () => Promise.reject(new Error("sin red"))) }).manager);
    await waitFor(() => expect(text("status")).toBe("anonymous"));
  });

  it("vuelta del emisor con codigo: limpia la URL, canjea UNA vez, pide get_me UNA vez y queda `authenticated` en la misma pagina", async () => {
    const { manager, listeners } = fakeManager();
    (manager.signinCallback as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      for (const listener of listeners) listener(user("canjeado")); // `oidc-client-ts` avisa `userLoaded` al terminar el canje
      return user("canjeado");
    });
    const { tokens, loadSession, page } = mount(manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    expect(page.clean).toHaveBeenCalledOnce();
    expect(page.clean.mock.invocationCallOrder[0]).toBeLessThan((manager.signinCallback as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0] as number);
    expect(manager.signinCallback).toHaveBeenCalledExactlyOnceWith(CALLBACK_URL);
    expect(loadSession).toHaveBeenCalledExactlyOnceWith("canjeado");
    expect(tokens.get()).toBe("canjeado");
    expect(manager.signinRedirect).not.toHaveBeenCalled(); // despues del callback no se redirige otra vez
  });

  it("StrictMode monta dos veces y el codigo se canjea una sola vez", async () => {
    const { manager } = fakeManager();
    render(
      <StrictMode>
        <AuthProvider manager={manager} loadSession={async () => SESSION} tokens={createTokenStore()} page={fakePage(CALLBACK_URL)}>
          <Probe />
        </AuthProvider>
      </StrictMode>,
    );
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(manager.signinCallback).toHaveBeenCalledOnce();
  });

  it("sin bucle: el callback de un prompt=none con login_required muestra el login interactivo, sin aviso y sin redirigir", async () => {
    const { manager } = fakeManager({ signinCallback: vi.fn(async () => Promise.reject(errorResponse("login_required", "silent"))) });
    mount(manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(text("failed")).toBe("false");
    expect(manager.signinRedirect).not.toHaveBeenCalled();
  });

  it("cualquier error de prompt=none (no solo login_required) tambien deja el login, sin redirigir", async () => {
    const { manager } = fakeManager({ signinCallback: vi.fn(async () => Promise.reject(errorResponse("interaction_required", "silent"))) });
    mount(manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(text("failed")).toBe("false");
    expect(manager.signinRedirect).not.toHaveBeenCalled();
  });

  it("un error del login interactivo (access_denied) o un canje roto muestra `loginFailed` y no redirige", async () => {
    for (const error of [errorResponse("access_denied", "interactive"), new Error("No matching state found in storage")]) {
      const { manager } = fakeManager({ signinCallback: vi.fn(async () => Promise.reject(error)) });
      mount(manager, undefined, fakePage(CALLBACK_URL));
      await waitFor(() => expect(text("failed")).toBe("true"));
      expect(text("status")).toBe("anonymous");
      expect(manager.signinRedirect).not.toHaveBeenCalled();
      cleanup();
    }
  });

  it("un callback que no entrega usuario (otro tipo de flujo) deja `anonymous`", async () => {
    mount(fakeManager({ signinCallback: vi.fn(async () => undefined) }).manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
  });

  it("get_me que falla: sin sesion utilizable, sin token", async () => {
    const { manager } = fakeManager({ getUser: vi.fn(async () => user("t")) });
    const { tokens } = mount(manager, vi.fn(async () => Promise.reject(new Error("503"))));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(tokens.get()).toBeNull();
  });

  it("cada token nuevo (refresco, step-up) pide get_me otra vez", async () => {
    const { manager, listeners } = fakeManager({ signinCallback: vi.fn(async () => Promise.reject(errorResponse("login_required", "silent"))) });
    const { loadSession } = mount(manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    await act(async () => {
      for (const listener of listeners) listener(user("nuevo"));
    });
    await waitFor(() => expect(loadSession).toHaveBeenCalledWith("nuevo"));
    expect(text("token")).toBe("nuevo");
  });

  it("login interactivo: signinRedirect se llama en el clic, en modo interactivo y con nonce; si falla `loginFailed`", async () => {
    const signinRedirect = vi.fn(async (_args: SigninArgs): Promise<void> => undefined);
    const { manager } = fakeManager({ signinCallback: vi.fn(async () => Promise.reject(errorResponse("login_required", "silent"))), signinRedirect });
    mount(manager, undefined, fakePage(CALLBACK_URL));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    signinRedirect.mockRejectedValueOnce(new Error("emisor caido"));
    fireEvent.click(screen.getByText("entrar"));
    expect(signinRedirect).toHaveBeenCalledOnce(); // sincrono, dentro del clic
    expect(signinRedirect).toHaveBeenCalledWith({ state: { mode: "interactive" }, nonce: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    await waitFor(() => expect(text("failed")).toBe("true"));
    fireEvent.click(screen.getByText("entrar"));
    await waitFor(() => expect(text("failed")).toBe("false"));
  });

  it("logout: borra el token y la sesion y va al end_session_endpoint", async () => {
    const signoutRedirect = vi.fn(async () => undefined);
    const { manager } = fakeManager({ getUser: vi.fn(async () => user("t")), signoutRedirect });
    const { tokens } = mount(manager);
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    fireEvent.click(screen.getByText("salir"));
    expect(signoutRedirect).toHaveBeenCalledOnce();
    expect(tokens.get()).toBeNull();
    expect(text("status")).toBe("anonymous");
    expect(text("role")).toBe("-");
  });

  it("un logout cuyo end_session falla no lanza", async () => {
    const { manager } = fakeManager({ signoutRedirect: vi.fn(async () => Promise.reject(new Error("red"))), signinRedirect: vi.fn(async () => Promise.reject(new Error("x"))) });
    mount(manager);
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    fireEvent.click(screen.getByText("salir"));
    await Promise.resolve();
    expect(text("status")).toBe("anonymous");
  });

  it("suelta el oyente de usuario al desmontar y useAuth fuera del proveedor falla", () => {
    const { manager, listeners } = fakeManager();
    const tokens = createTokenStore();
    const { unmount } = render(
      <AuthProvider manager={manager} loadSession={async () => SESSION} tokens={tokens} page={fakePage()}>
        <p>x</p>
      </AuthProvider>,
    );
    expect(listeners.size).toBe(1);
    unmount();
    expect(listeners.size).toBe(0);
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow("useAuth fuera de AuthProvider");
    quiet.mockRestore();
  });

  it("el almacen de tokens guarda y suelta el token solo en memoria", () => {
    const store = createTokenStore();
    expect(store.get()).toBeNull();
    store.set("a");
    expect(store.get()).toBe("a");
    store.set(null);
    expect(store.get()).toBeNull();
  });
});

describe("browserPage", () => {
  const win = (pathname: string, search: string) => {
    const replaceState = vi.fn();
    const self = { location: { pathname, search, href: `http://localhost${pathname}${search}` }, history: { replaceState } };
    return { self: self as unknown as Window, replaceState };
  };

  it("en /callback con state entrega la URL y la deja limpia (sin code ni state)", () => {
    const { self, replaceState } = win("/callback", "?code=c&state=s");
    const page = browserPage(self);
    expect(page.callbackUrl()).toBe("http://localhost/callback?code=c&state=s");
    page.clean();
    expect(replaceState).toHaveBeenCalledWith(null, "", "/");
  });

  it("/callback sin state, o cualquier otra ruta, no es un retorno del emisor; solo /callback se limpia", () => {
    for (const [path, search] of [["/callback", ""], ["/casos", "?state=x"]] as const) {
      const { self, replaceState } = win(path, search);
      expect(browserPage(self).callbackUrl()).toBeNull();
      browserPage(self).clean();
      expect(replaceState).toHaveBeenCalledTimes(path === "/callback" ? 1 : 0);
    }
  });
});
