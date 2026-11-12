// @vitest-environment jsdom
// BR-U10-20: `InactivityProvider` e `InactivityDialog`: el aviso a los 25 min con «seguir», el logout a los 30 y la limpieza al desmontar.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ui } from "../../../src/i18n";
import { browserInactivityEnv, type InactivityEnv, InactivityProvider } from "../../../src/inactivity/InactivityProvider";
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
