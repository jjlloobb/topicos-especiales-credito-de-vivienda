// BR-U10-06: `/stepup-callback` no canjea ni guarda nada: solo `postMessage({code, state}, location.origin)` al opener y se cierra.
import { describe, expect, it, vi } from "vitest";
import { runStepUpCallback } from "../../../src/stepup-callback";

function fakeWindow(url: string, opener: { postMessage: ReturnType<typeof vi.fn> } | null) {
  return { location: new URL(url), opener, close: vi.fn() } as unknown as Window & { close: ReturnType<typeof vi.fn> };
}

describe("runStepUpCallback", () => {
  it("entrega code y state al opener, solo a su propio origen, y se cierra", () => {
    const opener = { postMessage: vi.fn() };
    const win = fakeWindow("https://console.test/stepup-callback?code=c&state=s", opener);
    runStepUpCallback(win);
    expect(opener.postMessage).toHaveBeenCalledWith({ code: "c", state: "s" }, "https://console.test");
    expect(win.close).toHaveBeenCalledOnce();
  });

  it("una respuesta de error (sin code) no envia nada y se cierra", () => {
    const opener = { postMessage: vi.fn() };
    const win = fakeWindow("https://console.test/stepup-callback?error=access_denied&state=s", opener);
    runStepUpCallback(win);
    expect(opener.postMessage).not.toHaveBeenCalled();
    expect(win.close).toHaveBeenCalledOnce();
  });

  it("sin ventana de origen (pagina suelta) no hace nada", () => {
    const win = fakeWindow("https://console.test/stepup-callback?code=c&state=s", null);
    runStepUpCallback(win);
    expect(win.close).not.toHaveBeenCalled();
  });
});
