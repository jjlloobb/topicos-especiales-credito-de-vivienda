// @vitest-environment jsdom
// El selector de idioma en la SPA montada (enmienda del 2026-11-21 a NFR-U10-53): esta en la cabecera y en la pantalla de inicio de sesion,
// tiene nombre accesible en los dos idiomas, cambia TODA la pantalla sin desmontarla (el estado de un formulario a medio llenar, sus errores y
// la sesion se conservan), guarda la eleccion, y la sesion (`get_me`) solo decide el idioma si la persona no ha elegido.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { label, ui } from "../../../../src/i18n";
import { browserLanguageEnv, chooseLanguage, getLanguage, initLanguage } from "../../../../src/i18n/language";
import { createLanguageStorage, LANGUAGE_KEY } from "../../../../src/preferences/storage";
import labelsEn from "../../../../src/i18n/labels.en.json";
import labelsEs from "../../../../src/i18n/labels.es.json";
import labelsPt from "../../../../src/i18n/labels.pt.json";
import messagesEn from "../../../../src/i18n/messages.en.json";
import messagesEs from "../../../../src/i18n/messages.es.json";
import messagesPt from "../../../../src/i18n/messages.pt.json";
import { CASE_ID, detail, page, summary } from "../../../support/fixtures";
import { problem, renderApp } from "../../../support/views-world";

const GET_CASE = "GET /api/console/cases/{id}";
const DECISION = "POST /api/console/cases/{id}/decision";
// El nombre accesible del boton: el valor elegido y el nombre del control («Español Idioma / Language»).
const SELECTOR_ES = `${messagesEs.ui.language_name_es} ${messagesEs.ui.language_label}`;
const SELECTOR_EN = `${messagesEn.ui.language_name_en} ${messagesEn.ui.language_label}`;

beforeEach(() => {
  localStorage.clear();
  initLanguage(browserLanguageEnv(window, createLanguageStorage(window))); // como `main.tsx`; jsdom dice `en-US`: ver la prueba del navegador
  chooseLanguage("es");
  localStorage.clear(); // las pruebas parten en espanol y sin preferencia guardada
});
afterEach(() => {
  cleanup();
  initLanguage();
  localStorage.clear();
});

/** Abre el selector y elige una opcion por su nombre. */
function choose(name: string): void {
  fireEvent.click(screen.getByRole("button", { name: /Idioma/ }));
  fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name }));
}

describe("LanguageSelect", () => {
  it("esta en la cabecera con nombre accesible en los dos idiomas y ofrece «Español» y «English», cada una con su `lang`", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary()]) } });
    const button = await screen.findByRole("button", { name: SELECTOR_ES });
    expect(button.closest("header")).not.toBeNull();
    expect(button.getAttribute("aria-haspopup")).toBe("listbox");
    fireEvent.click(button);
    const options = within(screen.getByRole("listbox")).getAllByRole("option");
    expect(options.map((option) => [option.textContent, option.getAttribute("lang"), option.getAttribute("aria-selected")])).toEqual([
      ["Español", "es", "true"],
      ["English", "en", "false"],
      ["Português", "pt-BR", "false"], // cada opcion en su propio idioma y con su `lang`
    ]);
  });

  it("se opera con el teclado: Enter abre la lista, flecha abajo y Enter eligen «English»", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary()]) } });
    const button = await screen.findByRole("button", { name: SELECTOR_ES });
    button.focus();
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyUp(button, { key: "Enter" });
    const listbox = await screen.findByRole("listbox");
    const english = within(listbox).getByRole("option", { name: "English" });
    fireEvent.keyDown(document.activeElement ?? listbox, { key: "ArrowDown" });
    fireEvent.keyUp(document.activeElement ?? listbox, { key: "ArrowDown" });
    english.focus();
    fireEvent.keyDown(english, { key: "Enter" });
    fireEvent.keyUp(english, { key: "Enter" });
    expect(await screen.findByRole("button", { name: SELECTOR_EN })).toBeTruthy();
    expect(getLanguage()).toBe("en");
  });

  it("elegir «English» cambia toda la pantalla (cabecera, menu, vista, tabla, fechas y numeros), `<html lang>`, el titulo y guarda la preferencia", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary({ outcome: "favorable", score: "0.7312" })]) } });
    const table = await screen.findByRole("table");
    expect(within(table).getByText("12/11/2026", { exact: false })).toBeTruthy();
    expect(within(table).getByText("0,7312")).toBeTruthy();
    choose("English");

    expect(await screen.findByRole("button", { name: messagesEn.ui.logout_button })).toBeTruthy();
    expect(screen.getByRole("heading", { name: messagesEn.ui.view_cases })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: messagesEn.ui.nav_label })).toBeTruthy();
    expect(screen.getByText(`Role: ${labelsEn.ROLES.analista}`)).toBeTruthy();
    expect(screen.getByText(messagesEn.ui.app_tagline)).toBeTruthy();
    const english = screen.getByRole("table");
    expect(english).toBe(table); // la misma tabla: la pantalla no se desmonto
    expect(within(english).getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Applicant", "State", "Channel", "Created", "Recommendation", "Score", "Case ID", "Open"]);
    expect(within(english).getByText("12 Nov 2026, 10:00")).toBeTruthy(); // 15:00 UTC en Bogota
    expect(within(english).getByText("0.7312")).toBeTruthy();
    expect(within(english).getByText(labelsEn.CASE_STATES.listo)).toBeTruthy();
    expect(within(english).getByRole("link", { name: "Open case A. G." })).toBeTruthy();
    expect(english.querySelector("td")?.getAttribute("data-label")).toBe("Applicant"); // la etiqueta de la tarjeta en movil
    expect(screen.getByRole("region", { name: "Scrollable table: Case inbox" })).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
    expect(document.title).toBe(`${messagesEn.ui.view_cases} · Vectra Risk`); // el titulo dice la pantalla, en el idioma nuevo
    expect(Object.entries(localStorage)).toEqual([[LANGUAGE_KEY, "en"]]);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
    // ...y de vuelta
    fireEvent.click(screen.getByRole("button", { name: SELECTOR_EN }));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "Español" }));
    expect(await screen.findByRole("button", { name: messagesEs.ui.logout_button })).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("0,7312")).toBeTruthy();
    expect(document.documentElement.lang).toBe("es");
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("es");
  });

  it("ningun texto del catalogo en espanol queda en la pantalla tras cambiar a ingles (bandeja)", async () => {
    renderApp({ role: "cro", routes: { "GET /api/console/cases": page([summary({ state: "modelo_congelado", outcome: "desfavorable", score: "0.2100" })]) } });
    await screen.findByRole("table");
    choose("English");
    await screen.findByRole("button", { name: messagesEn.ui.logout_button });
    const same = new Set(["Vectra Risk", "Español", "English", "Português", "Web", "Manual", "Favorable"]);
    const spanish = [...Object.values(messagesEs.ui), ...Object.values(labelsEs).flatMap((group) => Object.values(group))].filter(
      (text) => !same.has(text) && !text.includes("{"),
    );
    const shown = new Set<string>();
    for (const node of document.body.querySelectorAll("*")) {
      for (const child of node.childNodes) if (child.nodeType === Node.TEXT_NODE && child.textContent !== null) shown.add(child.textContent.trim());
      for (const attribute of ["aria-label", "data-label", "title", "alt", "placeholder"]) {
        const value = node.getAttribute(attribute);
        if (value !== null) shown.add(value);
      }
    }
    expect(shown.size).toBeGreaterThan(30);
    expect(spanish.filter((text) => shown.has(text))).toEqual([]);
  });

  it("el cambio no pierde el estado de la pantalla: un formulario de decision a medio llenar conserva lo elegido, lo escrito y sus errores, ya traducidos", async () => {
    let posts = 0;
    renderApp({
      role: "analista",
      path: `/casos/${CASE_ID}`,
      routes: {
        [GET_CASE]: detail(),
        [DECISION]: () => {
          posts += 1;
          return problem(503, "dependency_unavailable");
        },
      },
    });
    await screen.findByRole("heading", { name: ui("decision_form_title") });
    fireEvent.click(screen.getByRole("radio", { name: label("DECISIONS", "se_aparta") }));
    const justification = screen.getByLabelText(ui("decision_field_justification")) as HTMLTextAreaElement;
    fireEvent.change(justification, { target: { value: "muy corta" } });
    fireEvent.click(screen.getByRole("button", { name: ui("decision_submit") }));
    expect(screen.getByText(messagesEs.ui.decision_error_justification_length)).toBeTruthy();
    expect(screen.getByText(messagesEs.ui.decision_error_factors_size)).toBeTruthy();

    choose("English");
    expect(await screen.findByRole("heading", { name: messagesEn.ui.decision_form_title })).toBeTruthy();
    expect(screen.getByLabelText(messagesEn.ui.decision_field_justification)).toBe(justification); // el mismo campo, no uno nuevo
    expect(justification.value).toBe("muy corta");
    expect((screen.getByRole("radio", { name: labelsEn.DECISIONS.se_aparta }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("radio", { name: labelsEn.FINAL_OUTCOMES.desfavorable }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(messagesEn.ui.decision_error_justification_length)).toBeTruthy();
    expect(screen.getByText(messagesEn.ui.decision_error_factors_size)).toBeTruthy();
    expect(screen.queryByText(messagesEs.ui.decision_error_justification_length)).toBeNull();
    expect(screen.getByText("9 of 2000 characters (minimum 20 when overriding or resolving the review)")).toBeTruthy();

    // El aviso de un 503 (guardado como dato, no como texto) tambien sigue al idioma.
    fireEvent.change(justification, { target: { value: "Una justificación suficientemente larga." } });
    fireEvent.click(screen.getByRole("checkbox", { name: messagesEn.ui.decision_field_none }));
    fireEvent.click(screen.getByRole("button", { name: messagesEn.ui.decision_submit }));
    fireEvent.click(within(await screen.findByRole("dialog", { name: messagesEn.ui.decision_confirm_title })).getByRole("button", { name: messagesEn.ui.decision_confirm_button }));
    expect(await screen.findByText(messagesEn.ui.decision_pending_registry)).toBeTruthy();
    expect(posts).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: SELECTOR_EN }));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "Español" }));
    expect(await screen.findByText(messagesEs.ui.decision_pending_registry)).toBeTruthy();
    expect(posts).toBe(1); // cambiar de idioma no reenvia nada
  });

  it("los textos propios de React Aria (el boton oculto que cierra un dialogo) van en el idioma de la consola, no en el del navegador (jsdom: en-US)", async () => {
    renderApp({ role: "analista", path: `/casos/${CASE_ID}`, routes: { [GET_CASE]: detail() } });
    await screen.findByRole("heading", { name: ui("decision_form_title") });
    fireEvent.click(screen.getByRole("radio", { name: label("DECISIONS", "sigue") }));
    fireEvent.click(screen.getByRole("checkbox", { name: ui("decision_field_none") }));
    fireEvent.click(screen.getByRole("button", { name: ui("decision_submit") }));
    await screen.findByRole("dialog", { name: messagesEs.ui.decision_confirm_title });
    expect(screen.getAllByRole("button", { name: "Descartar", hidden: true }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Dismiss", hidden: true })).toBeNull();
    chooseLanguage("en");
    await screen.findByRole("dialog", { name: messagesEn.ui.decision_confirm_title });
    expect(screen.getAllByRole("button", { name: "Dismiss", hidden: true }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Descartar", hidden: true })).toBeNull();
  });

  it("no pide nada al servidor al cambiar de idioma (el idioma no viaja)", async () => {
    const { world } = renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary()]) } });
    await screen.findByRole("table");
    const before = world.calls.length;
    choose("English");
    await screen.findByRole("button", { name: messagesEn.ui.logout_button });
    expect(world.calls.length).toBe(before);
  });

  it("esta tambien en la pantalla de inicio de sesion, y la eleccion hecha ahi sigue despues", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([]) } });
    fireEvent.click(await screen.findByRole("button", { name: messagesEs.ui.logout_button }));
    expect(await screen.findByRole("button", { name: messagesEs.ui.login_button })).toBeTruthy();
    choose("English");
    expect(await screen.findByRole("button", { name: messagesEn.ui.login_button })).toBeTruthy();
    expect(screen.getByRole("heading", { name: messagesEn.ui.login_title })).toBeTruthy();
    expect(screen.getByRole("button", { name: SELECTOR_EN })).toBeTruthy();
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("en");
  });
});

describe("portugues de Brasil", () => {
  it("elegir «Português» cambia toda la pantalla, `<html lang>` a pt-BR, el titulo por pantalla, las fechas y los numeros, y guarda «pt»", async () => {
    const { world } = renderApp({ role: "analista", routes: { "GET /api/console/cases": page([summary({ outcome: "favorable", score: "0.7312" })]) } });
    const table = await screen.findByRole("table");
    const before = world.calls.length;
    choose("Português");
    expect(await screen.findByRole("button", { name: messagesPt.ui.logout_button })).toBeTruthy();
    expect(screen.getByRole("heading", { name: messagesPt.ui.view_cases })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: messagesPt.ui.nav_label })).toBeTruthy();
    expect(screen.getByText(`Perfil: ${labelsPt.ROLES.analista}`)).toBeTruthy();
    expect(screen.getByText(messagesPt.ui.app_tagline)).toBeTruthy();
    expect(screen.getByRole("table")).toBe(table); // la misma tabla: la pantalla no se desmonto
    expect(within(table).getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Proponente", "Estado", "Canal", "Criado", "Recomendação", "Pontuação", "Identificador", "Abrir"]);
    expect(within(table).getByText("12 de nov. de 2026, 10:00")).toBeTruthy(); // 15:00 UTC en Bogota
    expect(within(table).getByText("0,7312")).toBeTruthy(); // los digitos del servidor, con coma decimal
    expect(within(table).getByText(labelsPt.CASE_STATES.listo)).toBeTruthy();
    expect(within(table).getByRole("link", { name: "Abrir caso A. G." })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Tabela rolável: Fila de casos" })).toBeTruthy();
    expect(document.documentElement.lang).toBe("pt-BR");
    expect(document.title).toBe(`${messagesPt.ui.view_cases} · Vectra Risk`);
    expect(Object.entries(localStorage)).toEqual([[LANGUAGE_KEY, "pt"]]);
    expect(sessionStorage.length).toBe(0);
    expect(world.calls.length).toBe(before); // el idioma no viaja al servidor
    expect(screen.getByRole("button", { name: `Português ${messagesPt.ui.language_label}` })).toBeTruthy();
  });

  it("ningun texto del catalogo en espanol queda a la vista tras cambiar a portugues (salvo los que se escriben igual)", async () => {
    renderApp({ role: "cro", routes: { "GET /api/console/cases": page([summary({ state: "listo", outcome: "desfavorable", score: "0.2100" })]) } });
    await screen.findByRole("table");
    choose("Português");
    await screen.findByRole("button", { name: messagesPt.ui.logout_button });
    const portuguese = new Set([...Object.values(messagesPt.ui), ...Object.values(labelsPt).flatMap((group) => Object.values(group))]);
    const spanish = [...Object.values(messagesEs.ui), ...Object.values(labelsEs).flatMap((group) => Object.values(group))].filter(
      (text) => !portuguese.has(text) && !text.includes("{"),
    );
    const shown = new Set<string>();
    for (const node of document.body.querySelectorAll("*")) {
      for (const child of node.childNodes) if (child.nodeType === Node.TEXT_NODE && child.textContent !== null) shown.add(child.textContent.trim());
      for (const attribute of ["aria-label", "data-label", "title", "alt", "placeholder"]) {
        const value = node.getAttribute(attribute);
        if (value !== null) shown.add(value);
      }
    }
    expect(shown.size).toBeGreaterThan(30);
    expect(spanish.length).toBeGreaterThan(200);
    expect(spanish.filter((text) => shown.has(text))).toEqual([]);
  });

  it("los textos propios de React Aria van en portugues (el boton oculto que cierra un dialogo)", async () => {
    renderApp({ role: "analista", path: `/casos/${CASE_ID}`, routes: { [GET_CASE]: detail() } });
    await screen.findByRole("heading", { name: ui("decision_form_title") });
    chooseLanguage("pt");
    fireEvent.click(await screen.findByRole("radio", { name: labelsPt.DECISIONS.sigue }));
    fireEvent.click(screen.getByRole("checkbox", { name: messagesPt.ui.decision_field_none }));
    fireEvent.click(screen.getByRole("button", { name: messagesPt.ui.decision_submit }));
    await screen.findByRole("dialog", { name: messagesPt.ui.decision_confirm_title });
    expect(screen.getAllByRole("button", { name: /^(Descartar|Dispensar|Fechar)$/, hidden: true }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Dismiss", hidden: true })).toBeNull();
  });

  it("con «pt» guardado la SPA abre en portugues aunque get_me diga es-CO; con el navegador en pt-PT y sin sesion, tambien", async () => {
    localStorage.setItem(LANGUAGE_KEY, "pt");
    initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
    renderApp({ role: "cumplimiento", path: "/congelamientos", routes: { "GET /api/console/freezes": [] } });
    expect(await screen.findByText(messagesPt.ui.freezes_empty)).toBeTruthy();
    expect(screen.getByText(`Perfil: ${labelsPt.ROLES.cumplimiento}`)).toBeTruthy();
    expect(document.documentElement.lang).toBe("pt-BR");
    cleanup();
    localStorage.clear();
    const win = { navigator: { languages: ["pt-PT", "en"], language: "pt-PT" }, document } as unknown as Window;
    initLanguage(browserLanguageEnv(win, createLanguageStorage(window)));
    expect(getLanguage()).toBe("pt");
    expect(localStorage.length).toBe(0); // resolver el idioma no guarda nada
  });
});

describe("el idioma inicial de la SPA montada", () => {
  it("con una preferencia guardada en ingles, la SPA abre en ingles aunque get_me diga es-CO", async () => {
    localStorage.setItem(LANGUAGE_KEY, "en");
    initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
    renderApp({ role: "cumplimiento", path: "/congelamientos", routes: { "GET /api/console/freezes": [] } });
    expect(await screen.findByText(messagesEn.ui.freezes_empty)).toBeTruthy();
    expect(screen.getByText(`Role: ${labelsEn.ROLES.cumplimiento}`)).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
  });

  it("sin preferencia y con el navegador en ingles (jsdom: en-US): al llegar la sesion manda el locale de get_me (es-CO), y no se guarda nada", async () => {
    expect(window.navigator.language).toBe("en-US");
    initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
    expect(getLanguage()).toBe("en"); // antes de la sesion: el navegador
    renderApp({ role: "cumplimiento", path: "/congelamientos", routes: { "GET /api/console/freezes": [] } });
    expect(await screen.findByText(messagesEs.ui.freezes_empty)).toBeTruthy();
    await waitFor(() => {
      expect(document.documentElement.lang).toBe("es");
    });
    expect(localStorage.length).toBe(0);
  });
});
