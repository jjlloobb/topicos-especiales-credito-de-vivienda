// @vitest-environment jsdom
// BR-U10-05: `AuthProvider` con un `AuthManager` falso: login silencioso al montar, `get_me` tras cada token nuevo, login interactivo y logout.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { User } from "oidc-client-ts";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionInfo } from "../../../src/api/endpoints";
import { type AuthManager, AuthProvider, createTokenStore, useAuth } from "../../../src/auth/AuthProvider";

afterEach(cleanup);

const SESSION: SessionInfo = { role: "analista", mfa: false, auth_time: "2026-11-12T15:00:00Z", locale: "es-CO" };
const user = (token: string): User => ({ access_token: token }) as User;

function fakeManager(over: Partial<AuthManager> = {}) {
  const listeners = new Set<(user: User) => void>();
  const manager: AuthManager = {
    getUser: vi.fn(async () => null),
    signinSilent: vi.fn(async () => null),
    signinPopup: vi.fn(async () => user("popup")),
    signoutRedirect: vi.fn(async () => undefined),
    events: {
      addUserLoaded: (cb) => listeners.add(cb),
      removeUserLoaded: (cb) => listeners.delete(cb),
    },
    ...over,
  };
  return { manager, listeners };
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

function mount(manager: AuthManager, loadSession = vi.fn(async (_token: string) => SESSION)) {
  const tokens = createTokenStore();
  render(
    <AuthProvider manager={manager} loadSession={loadSession} tokens={tokens}>
      <Probe />
    </AuthProvider>,
  );
  return { tokens, loadSession };
}

const text = (id: string) => screen.getByTestId(id).textContent;

describe("AuthProvider", () => {
  it("sin sesion en el IdP: el login silencioso no da usuario y queda `anonymous`", async () => {
    mount(fakeManager().manager);
    expect(text("status")).toBe("loading");
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(text("token")).toBe("-");
  });

  it("con sesion en el IdP: el login silencioso da usuario, se pide get_me y queda `authenticated` con el token en memoria", async () => {
    const { manager } = fakeManager({ signinSilent: vi.fn(async () => user("silencioso")) });
    const { tokens, loadSession } = mount(manager);
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    expect(loadSession).toHaveBeenCalledWith("silencioso");
    expect(text("role")).toBe("analista");
    expect(tokens.get()).toBe("silencioso");
  });

  it("un usuario ya en memoria no pide el login silencioso", async () => {
    const signinSilent = vi.fn(async () => null);
    const { manager } = fakeManager({ getUser: vi.fn(async () => user("en-memoria")), signinSilent });
    mount(manager);
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    expect(signinSilent).not.toHaveBeenCalled();
  });

  it("un error del login silencioso (login_required) deja `anonymous`", async () => {
    mount(fakeManager({ signinSilent: vi.fn(async () => Promise.reject(new Error("login_required"))) }).manager);
    await waitFor(() => expect(text("status")).toBe("anonymous"));
  });

  it("get_me que falla: sin sesion utilizable, sin token", async () => {
    const { manager } = fakeManager({ signinSilent: vi.fn(async () => user("t")) });
    const { tokens } = mount(manager, vi.fn(async () => Promise.reject(new Error("503"))));
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    expect(tokens.get()).toBeNull();
  });

  it("cada token nuevo (refresco, step-up) pide get_me otra vez", async () => {
    const { manager, listeners } = fakeManager();
    const { loadSession } = mount(manager);
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    await act(async () => {
      for (const listener of listeners) listener(user("nuevo"));
    });
    await waitFor(() => expect(loadSession).toHaveBeenCalledWith("nuevo"));
    expect(text("token")).toBe("nuevo");
  });

  it("login interactivo: signinPopup se llama en el clic; si falla (bloqueada o cerrada) `loginFailed`", async () => {
    const signinPopup = vi.fn(async (): Promise<User> => Promise.reject(new Error("Popup blocked")));
    mount(fakeManager({ signinPopup }).manager);
    await waitFor(() => expect(text("status")).toBe("anonymous"));
    fireEvent.click(screen.getByText("entrar"));
    expect(signinPopup).toHaveBeenCalledOnce(); // sincrono: dentro del clic
    await waitFor(() => expect(text("failed")).toBe("true"));
    (signinPopup as ReturnType<typeof vi.fn>).mockResolvedValueOnce(user("ok"));
    fireEvent.click(screen.getByText("entrar"));
    await waitFor(() => expect(text("failed")).toBe("false"));
  });

  it("logout: borra el token y la sesion y va al end_session_endpoint", async () => {
    const signoutRedirect = vi.fn(async () => undefined);
    const { manager } = fakeManager({ signinSilent: vi.fn(async () => user("t")), signoutRedirect });
    const { tokens } = mount(manager);
    await waitFor(() => expect(text("status")).toBe("authenticated"));
    fireEvent.click(screen.getByText("salir"));
    expect(signoutRedirect).toHaveBeenCalledOnce();
    expect(tokens.get()).toBeNull();
    expect(text("status")).toBe("anonymous");
    expect(text("role")).toBe("-");
  });

  it("un logout cuyo end_session falla no lanza", async () => {
    const { manager } = fakeManager({ signoutRedirect: vi.fn(async () => Promise.reject(new Error("red"))) });
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
      <AuthProvider manager={manager} loadSession={async () => SESSION} tokens={tokens}>
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
