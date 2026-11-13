// @vitest-environment jsdom
// BR-U10-20: `InactivityProvider` e `InactivityDialog`: el aviso a los 25 min con «seguir», el logout a los 30 y la limpieza al desmontar.
import { QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createQueryClient } from "../../../src/api/queryClient";
import { ui } from "../../../src/i18n";
import { browserInactivityEnv, type InactivityEnv, InactivityProvider, isWarningFocus } from "../../../src/inactivity/InactivityProvider";
import { Bus } from "../../support/bus";

const MIN = 60_000;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function env(bus: Bus, target: EventTarget): InactivityEnv {
  return {
    now: () => Date.now(),
    setTimeout: (handler, ms) => setTimeout(handler, ms),
    clearTimeout: (handle) => {
      clearTimeout(handle as ReturnType<typeof setTimeout>);
    },
    createChannel: () => bus.channel(),
    target,
  };
}

describe("InactivityProvider", () => {
  it("a los 25 min muestra el aviso; «Seguir» lo cierra y reinicia; a los 30 min hace logout", () => {
    const bus = new Bus();
    const target = new EventTarget();
    const onLogout = vi.fn();
    render(
      <InactivityProvider env={env(bus, target)} onLogout={onLogout}>
        <p>contenido</p>
      </InactivityProvider>,
    );
    expect(screen.getByText("contenido")).toBeTruthy();
    expect(screen.queryByRole("alertdialog")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(25 * MIN);
    });
    expect(screen.getByRole("alertdialog").textContent).toContain(ui("idle_body"));
    fireEvent.click(screen.getByRole("button", { name: ui("idle_continue") }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(25 * MIN);
    });
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(onLogout).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(5 * MIN);
    });
    expect(onLogout).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("un evento de actividad de la pagina reinicia el contador", () => {
    const bus = new Bus();
    const target = new EventTarget();
    const onLogout = vi.fn();
    render(
      <InactivityProvider env={env(bus, target)} onLogout={onLogout}>
        <p>contenido</p>
      </InactivityProvider>,
    );
    act(() => {
      vi.advanceTimersByTime(24 * MIN);
      target.dispatchEvent(new Event("wheel"));
      vi.advanceTimersByTime(24 * MIN);
    });
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  // BR-U10-20: el cliente REAL de la SPA (`createQueryClient`) y el `InactivityProvider` REAL, con el `document` de verdad como destino de
  // los eventos de actividad: un refresco automatico (`refetchInterval`) no cuenta como actividad. Un refresco que reinicie el contador
  // (p. ej. un `QueryCache.onSuccess` que dispare `focusin`) deja esta prueba en rojo.
  it("una consulta que se refresca sola cada 15 s no evita el aviso ni el logout", async () => {
    const bus = new Bus();
    const onLogout = vi.fn();
    const client = createQueryClient();
    let fetched = 0;
    function Bandeja() {
      useQuery({
        queryKey: ["bandeja"],
        queryFn: async () => {
          fetched += 1;
          return { n: fetched };
        },
        refetchInterval: 15_000,
      });
      return <p>bandeja</p>;
    }
    render(
      <QueryClientProvider client={client}>
        <InactivityProvider env={env(bus, document)} onLogout={onLogout}>
          <Bandeja />
        </InactivityProvider>
      </QueryClientProvider>,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(24 * MIN);
    });
    expect(fetched).toBeGreaterThan(90); // se refresco sola, sin parar
    expect(screen.queryByRole("alertdialog")).toBeNull();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1 * MIN);
    });
    expect(screen.getByRole("alertdialog")).toBeTruthy(); // y aun asi el aviso sale a los 25 min
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * MIN);
    });
    expect(onLogout).toHaveBeenCalledOnce();
    expect(bus.posted.every((m) => (m as { type: string }).type === "logout")).toBe(true); // ni un solo `activity`
    client.clear();
  });

  it("con el document de verdad: abrir el aviso (que se da el foco) no cuenta como actividad", async () => {
    const bus = new Bus();
    const onLogout = vi.fn();
    render(
      <InactivityProvider env={env(bus, document)} onLogout={onLogout}>
        <p>contenido</p>
      </InactivityProvider>,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(25 * MIN);
    });
    expect(screen.getByRole("alertdialog")).toBeTruthy(); // se queda abierto: su propio `focusin` no lo cierra
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * MIN);
    });
    expect(onLogout).toHaveBeenCalledOnce(); // y a los 30 min cierra la sesion
  });

  it("isWarningFocus: solo el focusin dentro del aviso se ignora", () => {
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "alertdialog");
    const button = document.createElement("button");
    dialog.append(button);
    const outside = document.createElement("button");
    document.body.append(dialog, outside);
    const event = (type: string, target: Element): Event => {
      const e = new Event(type, { bubbles: true });
      target.dispatchEvent(e);
      return e;
    };
    expect(isWarningFocus(event("focusin", button))).toBe(true);
    expect(isWarningFocus(event("keydown", button))).toBe(false);
    expect(isWarningFocus(event("focusin", outside))).toBe(false);
    expect(isWarningFocus(new Event("focusin"))).toBe(false); // sin destino
    dialog.remove();
    outside.remove();
  });

  it("al desmontar suelta los eventos y cierra el canal", () => {
    const bus = new Bus();
    const target = new EventTarget();
    const channels: { closed: boolean }[] = [];
    const base = env(bus, target);
    const { unmount } = render(
      <InactivityProvider
        env={{ ...base, createChannel: () => { const c = bus.channel(); channels.push(c); return c; } }}
        onLogout={() => undefined}
      >
        <p>contenido</p>
      </InactivityProvider>,
    );
    unmount();
    expect(channels.every((c) => c.closed)).toBe(true);
  });

  it("el entorno del navegador usa BroadcastChannel(\"vectra-console\") y el reloj de window", () => {
    expect(browserInactivityEnv.now()).toBe(Date.now());
    const channel = browserInactivityEnv.createChannel();
    expect(channel).toBeInstanceOf(BroadcastChannel);
    channel.close();
    const handle = browserInactivityEnv.setTimeout(() => undefined, 1000);
    browserInactivityEnv.clearTimeout(handle);
    expect(browserInactivityEnv.target).toBe(document);
  });
});
