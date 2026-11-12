// BR-U10-05: `/callback` entrega la respuesta segun quien abrio la pagina; suelta, limpia la URL.
import { describe, expect, it, vi } from "vitest";
import { handleAuthCallback } from "../../../src/auth/callback";

const manager = () => ({ signinPopupCallback: vi.fn(async () => undefined), signinSilentCallback: vi.fn(async () => undefined) });
const win = (over: Record<string, unknown>) => {
  const self: Record<string, unknown> = { history: { replaceState: vi.fn() }, opener: null, ...over };
  if (!("parent" in over)) self["parent"] = self;
  return self as unknown as Window & { history: { replaceState: ReturnType<typeof vi.fn> } };
};

describe("handleAuthCallback", () => {
  it("abierta como ventana emergente: entrega al opener", async () => {
    const m = manager();
    expect(await handleAuthCallback(m, win({ opener: {} }))).toBe("popup");
    expect(m.signinPopupCallback).toHaveBeenCalledOnce();
    expect(m.signinSilentCallback).not.toHaveBeenCalled();
  });

  it("dentro de un iframe (login silencioso): entrega al padre", async () => {
    const m = manager();
    expect(await handleAuthCallback(m, win({ parent: {} }))).toBe("silent");
    expect(m.signinSilentCallback).toHaveBeenCalledOnce();
  });

  it("suelta: no hay a quien entregar y la URL queda sin code ni state", async () => {
    const m = manager();
    const w = win({});
    expect(await handleAuthCallback(m, w)).toBe("stray");
    expect(w.history.replaceState).toHaveBeenCalledWith(null, "", "/");
    expect(m.signinPopupCallback).not.toHaveBeenCalled();
    expect(m.signinSilentCallback).not.toHaveBeenCalled();
  });
});
