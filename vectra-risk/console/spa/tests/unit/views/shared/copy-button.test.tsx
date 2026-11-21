// @vitest-environment jsdom
// «Copiar» (pasada de usabilidad del 2026-11-21): copia dentro del clic, lo confirma con un texto que se anuncia y, si el navegador no deja
// copiar, muestra el valor completo ya seleccionado en vez de fallar en silencio. Y `extractCaseId`, lo que «Ir al caso» acepta.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ui } from "../../../../src/i18n";
import { extractCaseId, shortCaseId } from "../../../../src/views/cases/filters";
import { COPIED_MS, CopyButton } from "../../../../src/views/shared/CopyButton";

const VALUE = "5e492a07-1111-4222-8333-444455556666";

function withClipboard(writeText: unknown): void {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: writeText === undefined ? undefined : { writeText } });
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  Reflect.deleteProperty(navigator, "clipboard");
});

describe("CopyButton", () => {
  it("copia el valor completo en el clic, dice «Copiado» en una region de estado y el aviso se retira solo", async () => {
    vi.useFakeTimers();
    const writeText = vi.fn(async () => undefined);
    withClipboard(writeText);
    render(<CopyButton value={VALUE} label="Copiar el identificador" />);
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("");
    const button = screen.getByRole("button", { name: "Copiar el identificador" });
    expect(button.textContent).toBe(ui("copy_button"));
    fireEvent.click(button);
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(VALUE);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(status.textContent).toBe(ui("copy_done"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(COPIED_MS);
    });
    expect(status.textContent).toBe("");
  });

  it.each([
    ["el navegador rechaza la copia", vi.fn(async () => Promise.reject(new Error("NotAllowedError")))],
    ["no hay API de portapapeles", undefined],
  ])("si %s, muestra el valor completo seleccionado y explica como copiarlo", async (_name, writeText) => {
    withClipboard(writeText);
    render(<CopyButton value={VALUE} label="Copiar" />);
    fireEvent.click(screen.getByRole("button", { name: "Copiar" }));
    expect(await screen.findByText(ui("copy_manual"))).toBeTruthy();
    expect(screen.getByText(VALUE).tagName).toBe("CODE");
    expect(window.getSelection()?.toString()).toBe(VALUE);
    expect(screen.queryByText(ui("copy_done"))).toBeNull();
  });
});

describe("extractCaseId y shortCaseId", () => {
  const ID = "0a1b2c3d-0000-4000-8000-00000000abcd";
  it.each([
    [ID, ID],
    [`  ${ID.toUpperCase()}\n`, ID],
    [`https://vectra.example/casos/${ID}`, ID],
    [`https://vectra.example/casos/${ID}/`, ID],
    [`http://127.0.0.1:5173/casos/${ID.toUpperCase()}?state=listo&page=3#decision`, ID],
    [`/casos/${ID}`, ID],
  ])("%s -> el UUID en minusculas", (text, expected) => {
    expect(extractCaseId(text)).toBe(expected);
  });

  it.each(["", "   ", "Ana Gomez", "no-es-un-uuid", ID.slice(0, 35), `${ID}0`, `https://vectra.example/casos/${ID}0`, `https://vectra.example/modelos/${ID}`, `${ID} ${ID}`, "https://vectra.example/casos/nuevo"])(
    "%s -> null",
    (text) => {
      expect(extractCaseId(text)).toBeNull();
    },
  );

  it("la forma corta son los 8 primeros caracteres y puntos suspensivos", () => {
    expect(shortCaseId(ID)).toBe("0a1b2c3d…");
  });
});
