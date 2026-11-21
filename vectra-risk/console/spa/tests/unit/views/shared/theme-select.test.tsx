// @vitest-environment jsdom
// El selector de tema en la SPA montada (enmienda del 2026-11-21 a NFR-U10-51): junto al de idioma, en la cabecera y en la pantalla de inicio de
// sesion; «Sistema» (por omision), «Claro» y «Oscuro»; nombre accesible en el idioma en curso con el valor elegido; cambia `data-theme` sin
// desmontar nada ni pedir nada al servidor, y guarda la eleccion.
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chooseLanguage, initLanguage } from "../../../../src/i18n/language";
import messagesEn from "../../../../src/i18n/messages.en.json";
import messagesEs from "../../../../src/i18n/messages.es.json";
import { createThemeStorage, THEME_KEY } from "../../../../src/preferences/storage";
import { browserThemeEnv, initTheme } from "../../../../src/theme/theme";
import { page, summary } from "../../../support/fixtures";
import { renderApp } from "../../../support/views-world";

const root = document.documentElement;
const CASES = { "GET /api/console/cases": page([summary()]) };
const themeButton = (value: string, label = messagesEs.ui.theme_label) => screen.getByRole("button", { name: `${value} ${label}` });

beforeEach(() => {
  localStorage.clear();
  root.removeAttribute("data-theme");
  initTheme(browserThemeEnv(window, createThemeStorage(window))); // como `main.tsx`
});
afterEach(() => {
  cleanup();
  initTheme();
  initLanguage();
  root.removeAttribute("data-theme");
  localStorage.clear();
});

function choose(current: string, option: string, label = messagesEs.ui.theme_label): void {
  fireEvent.click(themeButton(current, label));
  fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: option }));
}

describe("ThemeSelect", () => {
  it("esta en la cabecera junto al de idioma, dentro del grupo de preferencias, y ofrece «Sistema» (elegido), «Claro» y «Oscuro»", async () => {
    renderApp({ role: "analista", routes: CASES });
    await screen.findByRole("table");
    const group = screen.getByRole("group", { name: messagesEs.ui.preferences_label });
    expect(group.closest("header")).not.toBeNull();
    expect(within(group).getAllByRole("button").map((button) => button.textContent)).toEqual(["Español", "Sistema"]);
    const button = themeButton("Sistema");
    expect(button.getAttribute("aria-haspopup")).toBe("listbox");
    fireEvent.click(button);
    expect(within(screen.getByRole("listbox")).getAllByRole("option").map((option) => [option.textContent, option.getAttribute("aria-selected")])).toEqual([
      ["Sistema", "true"],
      ["Claro", "false"],
      ["Oscuro", "false"],
    ]);
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.length).toBe(0);
  });

  it("elegir «Oscuro» y luego «Claro» pone `data-theme` en <html>, anuncia el valor en el boton, guarda y no desmonta ni pide nada", async () => {
    const { world } = renderApp({ role: "analista", routes: CASES });
    const table = await screen.findByRole("table");
    const calls = world.calls.length;
    choose("Sistema", "Oscuro");
    expect(themeButton("Oscuro")).toBeTruthy();
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(Object.entries(localStorage)).toEqual([[THEME_KEY, "dark"]]);
    choose("Oscuro", "Claro");
    expect(themeButton("Claro")).toBeTruthy();
    expect(root.getAttribute("data-theme")).toBe("light");
    choose("Claro", "Sistema");
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
    expect(screen.getByRole("table")).toBe(table);
    expect(world.calls.length).toBe(calls);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("con «Oscuro» guardado, la SPA abre en oscuro y el selector lo dice", async () => {
    localStorage.setItem(THEME_KEY, "dark");
    initTheme(browserThemeEnv(window, createThemeStorage(window)));
    renderApp({ role: "analista", routes: CASES });
    await screen.findByRole("table");
    expect(root.getAttribute("data-theme")).toBe("dark");
    fireEvent.click(themeButton("Oscuro"));
    expect(within(screen.getByRole("listbox")).getByRole("option", { name: "Oscuro" }).getAttribute("aria-selected")).toBe("true");
  });

  it("sus textos siguen al idioma: «Theme», «System», «Light» y «Dark»", async () => {
    renderApp({ role: "analista", routes: CASES });
    await screen.findByRole("table");
    chooseLanguage("en");
    const button = await screen.findByRole("button", { name: `${messagesEn.ui.theme_system} ${messagesEn.ui.theme_label}` });
    expect(screen.getByRole("group", { name: messagesEn.ui.preferences_label })).toBeTruthy();
    fireEvent.click(button);
    expect(within(screen.getByRole("listbox")).getAllByRole("option").map((option) => option.textContent)).toEqual(["System", "Light", "Dark"]);
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "Dark" }));
    expect(themeButton("Dark", messagesEn.ui.theme_label)).toBeTruthy();
    expect(root.getAttribute("data-theme")).toBe("dark");
  });

  it("esta tambien en la pantalla de inicio de sesion", async () => {
    renderApp({ role: "analista", routes: { "GET /api/console/cases": page([]) } });
    fireEvent.click(await screen.findByRole("button", { name: messagesEs.ui.logout_button }));
    await screen.findByRole("button", { name: messagesEs.ui.login_button });
    choose("Sistema", "Oscuro");
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(themeButton("Oscuro").closest("main")).not.toBeNull();
  });
});
