// @vitest-environment jsdom
// BR-U10-15; US-304: la tabla de celdas de disparidad. Una celda con «muestra insuficiente» se muestra asi, **nunca** como 0, vacia ni con una tasa;
// su tasa nunca se calcula en el cliente; `before` y `last_7_days` pueden valer `sin_datos`.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ui } from "../../../../src/i18n";
import { AttributeTable, cellText, DisparityWindow } from "../../../../src/views/bias/DisparityTables";
import { CELL_LOW, CELL_OK, disparity } from "../../../support/fixtures";

afterEach(cleanup);

describe("cellText", () => {
  it("una celda insuficiente dice «Muestra insuficiente»: ni 0, ni vacio, ni una tasa (aunque el servidor mandara una)", () => {
    expect(cellText(CELL_LOW)).toBe(ui("cell_insufficient"));
    expect(cellText({ ...CELL_LOW, rate: "0.0000" } as never)).toBe(ui("cell_insufficient")); // jamas el 0 del servidor
    expect(cellText({ ...CELL_LOW, rate: "0.5000" } as never)).not.toContain("0,5");
    expect(cellText(CELL_LOW)).not.toMatch(/^(0|)$/);
  });

  it("una celda suficiente muestra la tasa del servidor con Intl (es-CO); sin tasa dice «Sin tasa», no 0", () => {
    expect(cellText(CELL_OK)).toBe("0,6200");
    expect(cellText({ ...CELL_OK, rate: null })).toBe(ui("cell_no_rate"));
    expect(cellText({ group: "a", band: "gt_30", n: 40, status: "suficiente" } as never)).toBe(ui("cell_no_rate")); // el BFF omite los nulos
  });
});

describe("AttributeTable y DisparityWindow", () => {
  it("la tabla marca la celda insuficiente y deja las demas con su tasa", () => {
    const attribute = disparity().attributes[0] as ReturnType<typeof disparity>["attributes"][number];
    render(<AttributeTable attribute={attribute} />);
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(3); // encabezado + 2 celdas
    expect(within(rows[1] as HTMLElement).getByText("0,6200")).toBeTruthy();
    const low = rows[2] as HTMLElement;
    expect(within(low).getByText(ui("cell_insufficient"))).toBeTruthy();
    expect(low.textContent).not.toMatch(/0,|\b0\b.*\b0\b/); // solo el `n` (4), sin tasa
    expect(screen.getByText(ui("disparity_aggregate", { value: "0,6000" }))).toBeTruthy();
  });

  it("`sin_datos` se dice; una ventana con datos muestra su rango (los dias del servidor, sin correrse de dia)", () => {
    render(<DisparityWindow title="Antes" result="sin_datos" />);
    expect(screen.getByText(ui("freeze_no_data"))).toBeTruthy();
    cleanup();
    render(<DisparityWindow title="Despues" result={disparity() as never} />);
    expect(screen.getByText(ui("freeze_window_range", { from: "13/10/2026", to: "11/11/2026" }))).toBeTruthy();
  });
});
