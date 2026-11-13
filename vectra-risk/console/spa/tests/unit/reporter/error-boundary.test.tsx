// @vitest-environment jsdom
// BR-U10-22: el `ErrorBoundary` reporta `render_error` y muestra el catalogo, nunca el error.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ui } from "../../../src/i18n";
import { ErrorBoundary } from "../../../src/reporter/ErrorBoundary";

afterEach(cleanup);

function Boom(): never {
  throw new Error("detalle interno con datos de la solicitud");
}

describe("ErrorBoundary", () => {
  it("sin error muestra a sus hijos", () => {
    render(
      <ErrorBoundary onError={() => undefined}>
        <p>todo bien</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("todo bien")).toBeTruthy();
  });

  it("ante un error de renderizado reporta una vez y muestra el texto del catalogo, no el error", () => {
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledOnce();
    expect(screen.getByRole("alert").textContent).toContain(ui("error_boundary_title"));
    expect(document.body.textContent).not.toContain("datos de la solicitud");
    quiet.mockRestore();
  });
});
