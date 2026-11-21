// @vitest-environment jsdom
// Las marcas de agua (pedido del dueno del proyecto, 2026-11-21): ilustraciones propias y DECORATIVAS. No son contenido: `aria-hidden`, sin rol,
// sin nombre accesible, sin texto ni titulo dentro, sin foco y sin relleno. Van en el pie de la pagina de las demos , en
// y en la pantalla de inicio de sesion; nunca dentro de una tabla, un formulario o un dialogo.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ui } from "../../../../src/i18n";
import { type Motif, sectionMotif, Watermark } from "../../../../src/views/shared/illustrations";
import { CASE_ID, detail, model, page, summary } from "../../../support/fixtures";
import { renderApp } from "../../../support/views-world";

afterEach(cleanup);

const MOTIFS: readonly Motif[] = ["skyline"];
const marks = (): SVGElement[] => [...document.querySelectorAll<SVGElement>("svg.watermark")];

describe("Watermark", () => {
  it.each(MOTIFS)("%s es decorativa: aria-hidden, sin rol, sin nombre, sin texto, sin foco, solo trazo", (motif) => {
    const { container } = render(<Watermark motif={motif} place="page" />);
    const svg = container.querySelector("svg") as SVGElement;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("focusable")).toBe("false");
    for (const attribute of ["role", "aria-label", "aria-labelledby", "title", "tabindex"]) expect(svg.hasAttribute(attribute), attribute).toBe(false);
    expect(svg.querySelectorAll("title, desc, text, tspan, a, image, use, script, style, foreignObject")).toHaveLength(0);
    expect(svg.textContent).toBe("");
    expect(svg.getAttribute("fill")).toBe("none");
    expect(svg.getAttribute("stroke")).toBe("currentColor"); // el color lo pone el token del tema (`styles.css`)
    expect(svg.getAttribute("stroke-width")).toBe("2");
    expect(svg.getAttribute("stroke-linecap")).toBe("round");
    const paths = [...svg.querySelectorAll("path")];
    expect(paths.length).toBeGreaterThan(3);
    expect(svg.children).toHaveLength(paths.length); // solo trazos
    for (const path of paths) expect([...path.attributes].map((attribute) => attribute.name)).toEqual(["d"]); // sin relleno, color ni estilo propios
    expect(svg.classList.contains(`watermark-${motif}`)).toBe(true);
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("el horizonte en las tres secciones de las demos (y sus detalles); las demas pantallas, ninguno", () => {
    expect(sectionMotif("/casos")).toBe("skyline");
    expect(sectionMotif(`/casos/${CASE_ID}`)).toBe("skyline");
    expect(sectionMotif("/congelamientos")).toBe("skyline");
    expect(sectionMotif("/congelamientos/freeze-1")).toBe("skyline");
    expect(sectionMotif("/modelos")).toBe("skyline");
    expect(sectionMotif("/modelos/mv-1")).toBe("skyline");
    for (const other of ["/", "/politicas", "/sesgo", "/casosx", "/modelos-viejos", "/callback"]) expect(sectionMotif(other)).toBeNull();
  });
});

describe("donde van en la SPA", () => {
  it("bandeja: una sola, el horizonte del barrio, al final de `main` y fuera de la tabla, de los formularios y de la navegacion", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary()]) } });
    await screen.findByRole("table");
    const [mark, ...rest] = marks();
    expect(rest).toEqual([]);
    expect(mark?.classList.contains("watermark-skyline")).toBe(true);
    expect(mark?.classList.contains("watermark-page")).toBe(true);
    const main = screen.getByRole("main");
    expect(main.lastElementChild).toBe(mark);
    expect(mark?.closest("table, form, nav, header, [role=dialog], [role=region], section")).toBeNull();
  });

  it("detalle del caso (con su formulario de decision): la marca sigue fuera del formulario", async () => {
    renderApp({ role: "analista", path: `/casos/${CASE_ID}`, routes: { "GET /api/console/cases/{id}": detail() } });
    await screen.findByRole("heading", { name: ui("decision_form_title") });
    expect(marks()).toHaveLength(1);
    expect(marks()[0]?.closest("form, section, [role=dialog]")).toBeNull();
  });

  it("modelos: el horizonte; una pantalla sin seccion (politicas): ninguna", async () => {
    renderApp({ role: "cro", path: "/modelos", routes: { "GET /api/console/models": page([model("mv-activo", "activo")]) } });
    await screen.findByRole("table");
    expect(marks().map((mark) => mark.getAttribute("class"))).toEqual(["watermark watermark-page watermark-skyline"]);
    cleanup();
    renderApp({ role: "cro", path: "/politicas" });
    await screen.findByText(ui("not_available_body"));
    expect(marks()).toEqual([]);
  });

  it("congelamientos: el horizonte; «sin acceso» en esa seccion: el mismo, sin nada mas", async () => {
    renderApp({ role: "cro", path: "/congelamientos", routes: { "GET /api/console/freezes": [] } });
    await screen.findByText(ui("freezes_empty"));
    expect(marks().map((mark) => mark.getAttribute("class"))).toEqual(["watermark watermark-page watermark-skyline"]);
    cleanup();
    renderApp({ role: "analista", path: "/congelamientos" });
    await screen.findByRole("heading", { name: ui("no_access_title") });
    expect(marks().map((mark) => mark.getAttribute("class"))).toEqual(["watermark watermark-page watermark-skyline"]);
  });

  it("inicio de sesion: el horizonte al fondo, fuera de la tarjeta; los nombres accesibles de la pantalla no cambian", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([]) } });
    fireEvent.click(await screen.findByRole("button", { name: ui("logout_button") }));
    await screen.findByRole("button", { name: ui("login_button") });
    expect(marks().map((mark) => mark.getAttribute("class"))).toEqual(["watermark watermark-auth watermark-skyline"]);
    expect(marks()[0]?.closest(".auth-card")).toBeNull();
    expect(screen.getAllByRole("heading").map((heading) => heading.textContent)).toEqual([ui("login_title")]);
  });
});
