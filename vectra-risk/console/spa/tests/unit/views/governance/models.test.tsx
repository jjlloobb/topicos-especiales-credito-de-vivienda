// @vitest-environment jsdom
// BR-U10-12; P-1 (a); US-602: `Models` y `ModelDetail` de LECTURA (sin registro, aprobacion ni retiro), con el informe de validacion que trae `get_model`.
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { label, ui } from "../../../../src/i18n";
import { CELL_LOW, CELL_OK, disparity, model, modelDetail, page } from "../../../support/fixtures";
import { problem, renderApp } from "../../../support/views-world";

afterEach(cleanup);

describe("Models", () => {
  it("lista las versiones con su estado (texto) y enlaza al detalle; es de lectura: ningun boton de accion", async () => {
    renderApp({ role: "cro", path: "/modelos", routes: { "GET /api/console/models": page([model("mv-activo", "activo"), model("mv-congelado", "congelado")]) } });
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "mv-activo" }).getAttribute("href")).toBe("/modelos/mv-activo");
    expect(within(table).getByText(label("MODEL_STATES", "congelado"))).toBeTruthy();
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([ui("logout_button")]);
  });

  it("vacia, y con un error del catalogo", async () => {
    renderApp({ role: "ingeniero_riesgo", path: "/modelos", routes: { "GET /api/console/models": page([]) } });
    expect(await screen.findByText(ui("models_empty"))).toBeTruthy();
    cleanup();
    renderApp({ role: "ingeniero_riesgo", path: "/modelos", routes: { "GET /api/console/models": () => problem(503, "dependency_unavailable") } });
    expect((await screen.findByRole("alert")).textContent).toContain("Un servicio necesario no está disponible");
  });
});

describe("ModelDetail", () => {
  const GET = "GET /api/console/models/{id}";

  it("muestra el informe de validacion: AUC contra la meta, el conjunto de datos, el aviso y la disparidad inicial con su celda insuficiente", async () => {
    const report = {
      auc_roc: "0.8120",
      auc_target: "0.7500",
      auc_meets_target: true,
      dataset_ref: "dataset-2026-q3",
      disclaimer: "mide y alerta, no certifica",
      sync_check: { passed: true, predictor_version: "p1", explainer_version: "e1", samples_checked: 50, failure_reason: null },
      initial_disparity: { attributes: disparity().attributes, model_aggregate: null, n_min: null, rule_met: null, threshold_pp: null, trigger_attribute: null },
    };
    renderApp({ role: "cumplimiento", path: "/modelos/mv-activo", routes: { [GET]: modelDetail({ validation_report: report }) } });
    expect(await screen.findByRole("heading", { name: ui("validation_title") })).toBeTruthy();
    expect(screen.getByText(ui("validation_auc", { value: "0,8120", target: "0,7500" }))).toBeTruthy();
    expect(screen.getByText(ui("validation_auc_met"))).toBeTruthy();
    expect(screen.getByText(ui("validation_dataset", { ref: "dataset-2026-q3" }))).toBeTruthy();
    expect(screen.getByText(ui("validation_disclaimer", { text: "mide y alerta, no certifica" }))).toBeTruthy();
    expect(screen.getByText(ui("cell_insufficient"))).toBeTruthy();
    expect(screen.getByText(ui("model_state", { state: label("MODEL_STATES", "activo") }))).toBeTruthy();
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([ui("logout_button")]);
  });

  it("sin informe lo dice; con la meta de AUC sin cumplir tambien; en investigacion se marca", async () => {
    renderApp({ role: "cro", path: "/modelos/mv-activo", routes: { [GET]: modelDetail({ investigation: true }) } });
    expect(await screen.findByText(ui("validation_none"))).toBeTruthy();
    expect(screen.getByText(ui("model_investigation"))).toBeTruthy();
    cleanup();
    const report = { auc_roc: "0.6000", auc_target: "0.7500", auc_meets_target: false, dataset_ref: "d", disclaimer: "x", sync_check: { passed: true, predictor_version: "p", explainer_version: "e", samples_checked: 1, failure_reason: null }, initial_disparity: { attributes: [], model_aggregate: null, n_min: null, rule_met: null, threshold_pp: null, trigger_attribute: null } };
    renderApp({ role: "cro", path: "/modelos/mv-activo", routes: { [GET]: modelDetail({ validation_report: report }) } });
    expect(await screen.findByText(ui("validation_auc_unmet"))).toBeTruthy();
  });

  it("un modelo que no existe: el mensaje del catalogo", async () => {
    renderApp({ role: "cro", path: "/modelos/mv-xx", routes: { [GET]: () => problem(404, "not_found") } });
    expect((await screen.findByRole("alert")).textContent).toContain("No se encontró lo que buscas.");
  });
});

describe("la celda `muestra_insuficiente` en el informe: nunca 0, vacia ni una tasa", () => {
  it("el fixture trae la celda insuficiente sin tasa", () => {
    expect([CELL_OK.status, CELL_LOW.status, CELL_LOW.rate]).toEqual(["suficiente", "muestra_insuficiente", null]);
  });
});
