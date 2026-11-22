// El idioma de la consola (enmienda del 2026-11-21 a NFR-U10-53), en un navegador real sobre el BUILD con la CSP de U2:
//  - el idioma inicial: la preferencia guardada; si no hay, el `locale` de `get_me`; si no, el del navegador; si no, espanol;
//  - el cambio en el selector es inmediato (sin recargar: ni la sesion ni el estado de la pantalla se pierden), actualiza `<html lang>` y el
//    titulo, y queda guardado en UNA clave del almacenamiento local (nada en el de sesion, ninguna cookie, nada hacia el servidor);
//  - la preferencia sobrevive a la recarga y al paso por el login por redireccion;
//  - el recorrido de las demos en ingles: bandeja (chips, filtros, paginacion), detalle (explicacion, formulario de decision y sus errores),
//    congelamientos y el paquete con la tabla comparativa, modelos y los dialogos, sin que quede a la vista ningun texto del catalogo en espanol.
import { type Page, expect, test } from "@playwright/test";
import { CASES, chooseLanguage, control, EN, ES, FREEZE_ID, goTo, LANG_TAG, languageButton, loginAs, ORIGIN, PREFERENCE_KEYS, PT, seedPreferences, spanishLeft } from "./support";
import { completeStepUp, openCase, openInactivityDialog, walk } from "./tour";

test.use({ baseURL: ORIGIN });

const storage = (page: Page) =>
  page.evaluate(() => ({ local: Object.entries(localStorage), session: Object.keys(sessionStorage), cookie: document.cookie }));

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

test.describe("el idioma inicial y el cambio", () => {
  test("navegador en espanol, sin preferencia: espanol de principio a fin y nada guardado", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await expect(page).toHaveTitle(ES.ui("document_title"));
    await expect(languageButton(page, ES)).toBeVisible(); // el selector esta en la pantalla de inicio de sesion
    await loginAs(page, "analista");
    await expect(page.getByRole("heading", { name: ES.ui("view_cases") })).toBeVisible();
    expect((await storage(page)).local).toEqual([]);
  });

  test("elegir «English»: toda la pantalla cambia sin recargar ni perder el estado; queda guardado y sobrevive a la recarga y al login", async ({ page }) => {
    const apiCalls: string[] = [];
    await loginAs(page, "analista");
    await openCase(page, CASES.listo);
    // un formulario a medio llenar, con un error de validacion a la vista
    await page.getByRole("radio", { name: ES.label("DECISIONS", "se_aparta") }).check();
    await page.getByLabel(ES.ui("decision_field_justification")).fill("corta");
    await page.getByRole("button", { name: ES.ui("decision_submit") }).click();
    await expect(page.getByRole("alert").filter({ hasText: ES.ui("decision_error_justification_length") })).toBeVisible();
    await page.evaluate(() => {
      (window as never as { __sameDocument: boolean }).__sameDocument = true; // una recarga borraria esta marca
    });
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/auth/")) apiCalls.push(`${request.method()} ${url.pathname}${url.search}`);
    });

    await chooseLanguage(page, ES, EN);

    await expect(page.getByRole("heading", { name: EN.ui("view_case_detail") })).toBeVisible();
    await expect(page.getByRole("button", { name: EN.ui("logout_button") })).toBeVisible();
    await expect(page).toHaveTitle(EN.ui("document_title_view", { view: EN.ui("view_case_detail") })); // el titulo dice la pantalla, en el idioma nuevo
    expect(await page.evaluate(() => (window as never as { __sameDocument?: boolean }).__sameDocument)).toBe(true); // no recargo
    // el estado de la pantalla sigue: lo elegido, lo escrito y el error, ya en ingles
    await expect(page.getByRole("radio", { name: EN.label("DECISIONS", "se_aparta") })).toBeChecked();
    await expect(page.getByLabel(EN.ui("decision_field_justification"))).toHaveValue("corta");
    await expect(page.getByRole("alert").filter({ hasText: EN.ui("decision_error_justification_length") })).toBeVisible();
    expect(await spanishLeft(page)).toEqual([]);
    // una sola clave en el almacenamiento local; nada en el de sesion; ninguna cookie legible; el idioma no viaja al servidor
    const state = await storage(page);
    expect(state.local).toEqual([[PREFERENCE_KEYS.language, "en"]]);
    expect(state.session).toEqual([]);
    expect(state.cookie).toBe("");
    expect(apiCalls.filter((call) => /lang|locale|idioma/i.test(call))).toEqual([]);

    // recarga completa: los tokens viven en memoria, asi que pasa por el emisor (`prompt=none`) y vuelve; el idioma sigue
    await page.reload();
    await expect(page.getByRole("button", { name: EN.ui("logout_button") })).toBeVisible();
    await expect(page.getByRole("heading", { name: EN.ui("view_case_detail") })).toBeVisible(); // y el enlace directo tambien (H-12)
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    expect((await storage(page)).session).toEqual([]); // la prueba del login: no queda NINGUNA clave en el almacenamiento de sesion
    // cerrar sesion: la pantalla de inicio de sesion tambien sale en ingles, y volver a entrar tambien
    await page.getByRole("button", { name: EN.ui("logout_button") }).click();
    await expect(page.getByRole("button", { name: EN.ui("login_button") })).toBeVisible();
    await expect(page.getByRole("heading", { name: EN.ui("login_title") })).toBeVisible();
    await loginAs(page, "analista", "/", EN);
    await expect(page.getByRole("heading", { name: EN.ui("view_cases") })).toBeVisible();
    // y de vuelta al espanol
    await chooseLanguage(page, EN, ES);
    await expect(page.getByRole("heading", { name: ES.ui("view_cases") })).toBeVisible();
    expect((await storage(page)).local).toEqual([[PREFERENCE_KEYS.language, "es"]]);
  });

  test("el selector se opera con el teclado y su lista dice cual esta elegido", async ({ page }) => {
    await loginAs(page, "analista");
    const button = languageButton(page, ES);
    await button.focus();
    await page.keyboard.press("Enter");
    const options = page.getByRole("listbox").getByRole("option");
    await expect(options).toHaveText(["Español", "English", "Português"]);
    await expect(options.nth(0)).toHaveAttribute("aria-selected", "true");
    await expect(options.nth(0)).toHaveAttribute("lang", "es");
    await expect(options.nth(1)).toHaveAttribute("lang", "en");
    await expect(options.nth(2)).toHaveAttribute("lang", "pt-BR");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(languageButton(page, EN)).toBeFocused(); // el foco vuelve al selector
    await expect(page.getByRole("heading", { name: EN.ui("view_cases") })).toBeVisible();
    await languageButton(page, EN).press("Enter");
    await expect(page.getByRole("listbox")).toBeVisible();
    await page.keyboard.press("Escape"); // Escape cierra sin cambiar
    await expect(page.getByRole("listbox")).toHaveCount(0);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  test.describe("con el navegador en ingles", () => {
    test.use({ locale: "en-US" });

    test("sin preferencia: el inicio de sesion sale en ingles (navegador); con la sesion manda el locale de get_me (es-CO); elegir «English» lo fija", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("button", { name: EN.ui("login_button") })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await expect(page).toHaveTitle(EN.ui("document_title"));
      await loginAs(page, "analista", "/", { ...EN, ui: (key, params) => (key === "logout_button" ? ES.ui(key, params) : EN.ui(key, params)) });
      await expect(page.getByRole("heading", { name: ES.ui("view_cases") })).toBeVisible(); // `get_me` dice es-CO y no hay preferencia
      await expect(page.locator("html")).toHaveAttribute("lang", "es");
      expect((await storage(page)).local).toEqual([]);
      await chooseLanguage(page, ES, EN);
      await page.reload();
      await expect(page.getByRole("heading", { name: EN.ui("view_cases") })).toBeVisible(); // ya hay preferencia: gana a `get_me`
    });

    test("con «es» guardado, espanol aunque el navegador este en ingles", async ({ page, context }) => {
      await seedPreferences(context, { language: "es" });
      await page.goto("/");
      await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("lang", "es");
    });
  });

  test.describe("con el navegador en otro idioma", () => {
    test.use({ locale: "fr-FR" });

    test("ni espanol, ni ingles, ni portugues: espanol", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("lang", "es");
    });
  });
});

test.describe("con el navegador en portugues", () => {
  for (const locale of ["pt-BR", "pt-PT"]) {
    test.describe(locale, () => {
      test.use({ locale });

      test(`sin preferencia (${locale}): el inicio de sesion sale en portugues de Brasil; elegir «Português» lo fija y sobrevive a la recarga`, async ({ page }) => {
        await page.goto("/");
        await expect(page.getByRole("button", { name: PT.ui("login_button") })).toBeVisible();
        await expect(page.getByRole("heading", { name: PT.ui("login_title") })).toBeVisible();
        await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
        await expect(page).toHaveTitle(PT.ui("document_title"));
        await expect(languageButton(page, PT)).toBeVisible();
        expect((await storage(page)).local).toEqual([]);
        // con la sesion manda el `locale` de `get_me` (es-CO) mientras no haya preferencia
        await loginAs(page, "analista", "/", { ...PT, ui: (key, params) => (key === "logout_button" ? ES.ui(key, params) : PT.ui(key, params)) });
        await expect(page.getByRole("heading", { name: ES.ui("view_cases") })).toBeVisible();
        await chooseLanguage(page, ES, PT);
        await expect(page.getByRole("heading", { name: PT.ui("view_cases") })).toBeVisible();
        await expect(page).toHaveTitle(PT.ui("document_title_view", { view: PT.ui("view_cases") }));
        expect((await storage(page)).local).toEqual([[PREFERENCE_KEYS.language, "pt"]]);
        await page.reload();
        await expect(page.getByRole("heading", { name: PT.ui("view_cases") })).toBeVisible(); // ya hay preferencia: gana a `get_me`
        await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
        expect((await storage(page)).session).toEqual([]);
      });
    });
  }
});

test.describe("el idioma viaja al login del emisor como `ui_locales`", () => {
  const AUTHORIZE = "/protocol/openid-connect/auth";

  /** Las peticiones de autorizacion (documentos) que salen de cualquier pagina del contexto, tambien de la ventana del step-up. */
  function watchAuthorize(context: import("@playwright/test").BrowserContext): URL[] {
    const requests: URL[] = [];
    context.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.endsWith(AUTHORIZE) && request.resourceType() === "document") requests.push(url);
    });
    return requests;
  }
  const summaryOf = (url: URL | undefined) => ({ ui_locales: url?.searchParams.getAll("ui_locales"), prompt: url?.searchParams.get("prompt") ?? null });

  test("login silencioso, login interactivo y step-up llevan el idioma activo; al cambiar el idioma, cambia; lo demas del flujo sigue igual", async ({ page, context }) => {
    const authorize = watchAuthorize(context);
    // 1. carga sin sesion, en espanol: el `prompt=none` y, tras el clic, el login interactivo
    await loginAs(page, "cumplimiento");
    expect(authorize.map(summaryOf)).toEqual([
      { ui_locales: ["es"], prompt: "none" },
      { ui_locales: ["es"], prompt: null },
    ]);
    // 2. cambia a ingles: la recarga (otro `prompt=none`) ya lo lleva
    await chooseLanguage(page, ES, EN);
    await page.reload();
    await expect(page.getByRole("button", { name: EN.ui("logout_button") })).toBeVisible();
    expect(summaryOf(authorize.at(-1))).toEqual({ ui_locales: ["en"], prompt: "none" });
    // 3. el step-up, en la ventana emergente: `prompt=login`, `max_age=0` y `acr_values=mfa` como siempre, mas `ui_locales=en`
    await goTo(page, `/congelamientos/${FREEZE_ID}`);
    await page.getByRole("button", { name: EN.ui("resolve_open") }).click();
    await page.getByLabel(EN.ui("resolve_justification")).fill("Reviewed");
    await completeStepUp(context, () => page.getByRole("button", { name: EN.ui("verify_and_confirm") }).click(), "cumplimiento");
    await expect(page.getByText(EN.ui("freeze_resolution_done"))).toBeVisible();
    const stepUp = authorize.at(-1) as URL;
    expect(Object.fromEntries(["ui_locales", "prompt", "max_age", "acr_values", "code_challenge_method"].map((name) => [name, stepUp.searchParams.get(name)]))).toEqual({
      ui_locales: "en",
      prompt: "login",
      max_age: "0",
      acr_values: "mfa",
      code_challenge_method: "S256",
    });
    expect(stepUp.searchParams.get("redirect_uri")).toBe(`${ORIGIN}/stepup-callback`);
    // 4. cerrar sesion y entrar otra vez, en ingles: el login interactivo lo lleva
    await page.getByRole("button", { name: EN.ui("logout_button") }).click();
    await page.getByRole("button", { name: EN.ui("login_button") }).click();
    await page.waitForURL(new RegExp(AUTHORIZE.replaceAll("/", "\\/")));
    expect(summaryOf(authorize.at(-1))).toEqual({ ui_locales: ["en"], prompt: null });
    // En todas: un solo `ui_locales`, de los dos valores posibles, PKCE S256, `state`, `nonce` y el `redirect_uri` de la SPA; nunca `kc_locale`.
    expect(authorize.length).toBeGreaterThanOrEqual(5);
    for (const url of authorize) {
      expect(["es", "en", "pt-BR"]).toContain(url.searchParams.get("ui_locales"));
      expect(url.searchParams.getAll("ui_locales")).toHaveLength(1);
      expect(url.searchParams.get("code_challenge_method")).toBe("S256");
      expect(url.searchParams.get("state")).toBeTruthy();
      expect(url.searchParams.get("nonce")).toBeTruthy();
      expect([`${ORIGIN}/callback`, `${ORIGIN}/stepup-callback`]).toContain(url.searchParams.get("redirect_uri"));
      expect(url.searchParams.has("kc_locale")).toBe(false);
    }
  });
});

test.describe("el portugues viaja al login como `ui_locales=pt-BR`", () => {
  test("login silencioso, login interactivo y step-up en portugues llevan `pt-BR` (el codigo de Keycloak), y nada mas cambia", async ({ page, context }) => {
    const requests: URL[] = [];
    context.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.endsWith("/protocol/openid-connect/auth") && request.resourceType() === "document") requests.push(url);
    });
    await seedPreferences(context, { language: "pt" });
    await loginAs(page, "cumplimiento", "/", PT);
    expect(requests.map((url) => [url.searchParams.getAll("ui_locales"), url.searchParams.get("prompt")])).toEqual([
      [["pt-BR"], "none"],
      [["pt-BR"], null],
    ]);
    await goTo(page, `/congelamientos/${FREEZE_ID}`);
    await page.getByRole("button", { name: PT.ui("resolve_open") }).click();
    await page.getByLabel(PT.ui("resolve_justification")).fill("Revisado pela área de compliance");
    await expect(page.getByText(PT.ui("resolve_mfa_hint", { minutes: "15" }))).toBeVisible();
    await completeStepUp(context, () => page.getByRole("button", { name: PT.ui("verify_and_confirm") }).click(), "cumplimiento");
    await expect(page.getByText(PT.ui("freeze_resolution_done"))).toBeVisible();
    const stepUp = requests.at(-1) as URL;
    expect(Object.fromEntries(["ui_locales", "prompt", "max_age", "acr_values", "code_challenge_method"].map((name) => [name, stepUp.searchParams.get(name)]))).toEqual({
      ui_locales: "pt-BR",
      prompt: "login",
      max_age: "0",
      acr_values: "mfa",
      code_challenge_method: "S256",
    });
    for (const url of requests) {
      expect(url.searchParams.getAll("ui_locales")).toEqual(["pt-BR"]);
      expect(url.searchParams.has("kc_locale")).toBe(false);
      expect(url.searchParams.get("state")).toBeTruthy();
      expect(url.searchParams.get("nonce")).toBeTruthy();
    }
  });
});

test.describe("las demos en portugues de Brasil", () => {
  test.beforeEach(async ({ context }) => {
    await seedPreferences(context, { language: "pt" });
  });

  test("bandeja y detalle: columnas, fechas y numeros de pt-BR, pesos como COP (sin convertir), y ningun texto en espanol a la vista", async ({ page }) => {
    await loginAs(page, "analista", "/", PT);
    await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
    const region = page.getByRole("region", { name: "Tabela rolável: Fila de casos" });
    await expect(region.getByRole("columnheader")).toHaveText(["Proponente", "Estado", "Canal", "Criado", "Recomendação", "Pontuação", "Identificador", "Abrir"]);
    await expect(page.getByText(/^Casos com estes filtros: \d+$/)).toBeVisible();
    // fechas: dia/mes/anio y hora de 24 h (zona de Bogota); puntajes: coma decimal, los digitos del servidor
    await expect(region.getByRole("row").nth(1).getByRole("cell").nth(3)).toHaveText(/^\d{2}\/\d{2}\/\d{4}, \d{2}:\d{2}$/);
    await expect(region.getByRole("cell", { name: /^0,\d{4}$/ }).first()).toBeVisible();
    const chips = page.getByRole("group", { name: PT.ui("quick_states_label") });
    await chips.getByRole("button", { name: PT.label("CASE_STATES", "decidido"), exact: true }).click();
    await expect(region.getByRole("row")).toHaveCount(2);
    expect(new URL(page.url()).searchParams.getAll("state")).toEqual(["decidido"]); // la URL lleva el codigo, no el texto traducido
    await chips.getByRole("button", { name: PT.ui("quick_states_default") }).click();
    await page.getByText(PT.ui("filters_more")).click();
    await expect(page.getByLabel(PT.ui("filter_channel"))).toBeVisible();
    const pagination = page.getByRole("navigation", { name: PT.ui("pagination_label") });
    await expect(pagination.getByRole("button")).toHaveText([PT.ui("page_first"), PT.ui("page_previous"), PT.ui("page_next"), PT.ui("page_last")]);
    await page.getByLabel(PT.ui("go_to_case_label")).fill("não-é-um-uuid");
    await page.getByRole("button", { name: PT.ui("go_to_case_button") }).click();
    await expect(page.getByRole("alert")).toHaveText(PT.ui("go_to_case_invalid"));
    expect(await spanishLeft(page, PT)).toEqual([]);

    await openCase(page, CASES.listo, PT);
    await expect(page).toHaveTitle(PT.ui("document_title_view", { view: PT.ui("view_case_detail") }));
    await expect(page.getByText(/^Pontuação: 0,\d{4}$/)).toBeVisible();
    await expect(page.getByText(PT.notice("credit_not_integrated"))).toBeVisible();
    await page.getByText(PT.ui("application_toggle")).click();
    await expect(page.getByText(/^COP\s[\d.]+$/).first()).toBeVisible(); // pesos colombianos: ni «R$» ni conversion
    await expect(page.getByText(/R\$/)).toHaveCount(0);
    await page.getByRole("button", { name: PT.ui("explanation_button") }).click();
    await expect(page.getByText(/Contribuição: -?0,\d{4}$/).first()).toBeVisible();
    await page.getByRole("radio", { name: PT.label("DECISIONS", "se_aparta") }).check();
    await page.getByLabel(PT.ui("decision_field_justification")).fill("muito curta");
    await page.getByRole("button", { name: PT.ui("decision_submit") }).click();
    await expect(page.getByRole("alert").filter({ hasText: PT.ui("decision_error_justification_length") })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: PT.ui("decision_error_factors_size") })).toBeVisible();
    expect(await spanishLeft(page, PT)).toEqual([]);
  });

  for (const role of ["analista", "ingeniero_riesgo", "cro", "cumplimiento"] as const) {
    test(`recorrido de ${role} en portugues: en ninguna parada queda un texto del catalogo en espanol`, async ({ page, context }) => {
      const stops: string[] = [];
      await walk(
        page,
        context,
        role,
        async (name) => {
          expect(await spanishLeft(page, PT), `textos en espanol en «${name}»`).toEqual([]);
          await expect(page.locator("html")).toHaveAttribute("lang", LANG_TAG[PT.lang]);
          stops.push(name);
        },
        PT,
      );
      expect(stops.length).toBeGreaterThan(2);
    });
  }
});

test.describe("las demos en ingles", () => {
  test.beforeEach(async ({ context }) => {
    await seedPreferences(context, { language: "en" });
  });

  test("bandeja: chips, filtros, paginacion, fechas y numeros en ingles", async ({ page }) => {
    await loginAs(page, "analista", "/", EN);
    const region = page.getByRole("region", { name: "Scrollable table: Case inbox" });
    await expect(region.getByRole("columnheader")).toHaveText(["Applicant", "State", "Channel", "Created", "Recommendation", "Score", "Case ID", "Open"]);
    await expect(page.getByText(/^Cases matching these filters: \d+$/)).toBeVisible();
    await expect(page.getByText(/^Showing 1 to \d+$/)).toBeVisible();
    await expect(page.getByText("Refreshes every 15 seconds while this tab is visible.")).toBeVisible();
    // fechas: dia, mes con letras y hora de 24 h (zona de Bogota); puntajes: punto decimal, los digitos del servidor
    const created = region.getByRole("row").nth(1).getByRole("cell").nth(3);
    await expect(created).toHaveText(/^\d{1,2} [A-Z][a-z]{2} \d{4}, \d{2}:\d{2}$/);
    await expect(region.getByRole("cell", { name: /^0\.\d{4}$/ }).first()).toBeVisible();
    await expect(region.getByText(/\d,\d{4}/)).toHaveCount(0);
    // chips de un clic
    const chips = page.getByRole("group", { name: EN.ui("quick_states_label") });
    await expect(chips.getByRole("button").first()).toHaveText(EN.ui("quick_states_default"));
    await chips.getByRole("button", { name: EN.label("CASE_STATES", "decidido"), exact: true }).click();
    await expect(chips.getByRole("button", { name: EN.label("CASE_STATES", "decidido"), exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(region.getByRole("row")).toHaveCount(2);
    await expect(region.getByRole("row").nth(1)).toContainText(EN.label("CASE_STATES", "decidido"));
    expect(new URL(page.url()).searchParams.getAll("state")).toEqual(["decidido"]); // la URL lleva el codigo, no el texto traducido
    await chips.getByRole("button", { name: EN.ui("quick_states_default") }).click();
    // «More filters»
    await page.getByText(EN.ui("filters_more")).click();
    await expect(page.getByLabel(EN.ui("filter_channel"))).toBeVisible();
    await expect(page.getByLabel(EN.ui("filter_created_from"))).toBeVisible();
    await expect(page.getByRole("option", { name: EN.ui("filter_channel_all") })).toBeAttached();
    await page.getByRole("checkbox", { name: EN.label("CASE_STATES", "vencido") }).click();
    await expect(page.getByRole("checkbox", { name: EN.label("CASE_STATES", "vencido") })).toBeChecked();
    await expect(region.getByRole("row").filter({ hasText: EN.label("CASE_STATES", "vencido") })).toHaveCount(1);
    expect(await spanishLeft(page)).toEqual([]);
    await page.getByRole("button", { name: EN.ui("filter_clear") }).click();
    // paginacion
    const pagination = page.getByRole("navigation", { name: EN.ui("pagination_label") });
    await expect(pagination.getByRole("button")).toHaveText([EN.ui("page_first"), EN.ui("page_previous"), EN.ui("page_next"), EN.ui("page_last")]);
    await expect(pagination.getByText(/^Page 1( of \d+)?$/)).toBeVisible();
    // «Go to case»
    await page.getByLabel(EN.ui("go_to_case_label")).fill("not-a-uuid");
    await page.getByRole("button", { name: EN.ui("go_to_case_button") }).click();
    await expect(page.getByRole("alert")).toHaveText(EN.ui("go_to_case_invalid"));
    expect(await spanishLeft(page)).toEqual([]);
  });

  test("detalle: recomendacion, solicitud con pesos (COP), explicacion y el formulario de decision con sus errores", async ({ page }) => {
    await loginAs(page, "analista", "/", EN);
    await openCase(page, CASES.listo, EN);
    await expect(page.getByRole("heading", { name: EN.ui("recommendation_title") })).toBeVisible();
    await expect(page.getByText(/^Score: 0\.\d{4}$/)).toBeVisible();
    await expect(page.getByText(/^Confidence: 0\.\d{4}$/)).toBeVisible();
    await expect(page.getByText(EN.notice("credit_not_integrated"))).toBeVisible();
    await page.getByText(EN.ui("application_toggle")).click();
    await expect(page.getByText(EN.ui("application_income"))).toBeVisible();
    await expect(page.getByText(/^COP\s[\d,]+$/).first()).toBeVisible(); // pesos colombianos, sin «$» suelto
    await expect(page.getByText(/^\$\s?[\d.]+$/)).toHaveCount(0);
    await page.getByRole("button", { name: EN.ui("explanation_button") }).click();
    await expect(page.getByRole("heading", { name: EN.ui("explanation_title") })).toBeVisible();
    await expect(page.getByText(EN.ui("explanation_narrative"))).toBeVisible();
    await expect(page.getByText(EN.ui("explanation_factors"))).toBeVisible();
    await expect(page.getByText(/Contribution: -?0\.\d{4}$/).first()).toBeVisible();
    // el formulario: sin elegir nada
    await page.getByRole("button", { name: EN.ui("decision_submit") }).click();
    await expect(page.getByRole("alert").filter({ hasText: EN.ui("decision_error_choose_decision") })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: EN.ui("decision_error_choose_final") })).toBeVisible();
    // apartarse con una justificacion corta y sin factores
    await page.getByRole("radio", { name: EN.label("DECISIONS", "se_aparta") }).check();
    await page.getByLabel(EN.ui("decision_field_justification")).fill("too short");
    await expect(page.getByText(EN.ui("decision_counter", { count: "9" }))).toBeVisible();
    await page.getByRole("button", { name: EN.ui("decision_submit") }).click();
    await expect(page.getByRole("alert").filter({ hasText: EN.ui("decision_error_justification_length") })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: EN.ui("decision_error_factors_size") })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(await spanishLeft(page)).toEqual([]);
    // seguir la recomendacion: el dialogo de confirmacion y el registro
    await page.getByRole("radio", { name: EN.label("DECISIONS", "sigue") }).check();
    await page.getByRole("checkbox", { name: EN.ui("decision_field_none") }).check();
    await page.getByRole("button", { name: EN.ui("decision_submit") }).click();
    const dialog = page.getByRole("dialog", { name: EN.ui("decision_confirm_title") });
    await expect(dialog).toContainText(EN.ui("decision_confirm_summary", { decision: EN.label("DECISIONS", "sigue"), final: EN.label("FINAL_OUTCOMES", "favorable") }));
    expect(await spanishLeft(page)).toEqual([]);
    await dialog.getByRole("button", { name: EN.ui("decision_confirm_button") }).click();
    await expect(page.getByText(EN.ui("decision_saved"))).toBeVisible();
    await expect(page.getByRole("heading", { name: EN.ui("decision_recorded_title") })).toBeVisible();
    await expect(page.getByText(/^Recorded by .+ on \d{1,2} [A-Z][a-z]{2} \d{4}, \d{2}:\d{2}$/)).toBeVisible();
    // las marcas de los otros casos
    await openCase(page, CASES.bajaConfianza, EN);
    await expect(page.locator(".mark-low")).toContainText("Low confidence");
    await openCase(page, CASES.revision, EN);
    await expect(page.locator(".mark-review")).toContainText("requires a human review");
    await openCase(page, CASES.congelado, EN);
    await expect(page.getByText(EN.notice("model_frozen_after_recommendation"))).toBeVisible();
    await goTo(page, `/casos/${CASES.inexistente}`);
    await expect(page.getByRole("alert")).toContainText(EN.problemCode("not_found"));
    expect(await spanishLeft(page)).toEqual([]);
  });

  test("congelamientos, el paquete con la tabla comparativa, modelos y los dialogos de resolver y de verificacion en dos pasos", async ({ page, context }) => {
    await loginAs(page, "cumplimiento", "/", EN);
    const list = page.getByRole("table");
    await expect(list.getByRole("columnheader")).toContainText([EN.ui("col_freeze"), EN.ui("col_frozen_at"), EN.ui("col_trigger")]);
    expect(await spanishLeft(page)).toEqual([]);
    await page.getByRole("link", { name: EN.ui("freeze_open_context", { id: FREEZE_ID }) }).click();
    await expect(page.getByRole("heading", { name: EN.ui("freeze_context_title") })).toBeVisible();
    await expect(page.getByText(EN.ui("bias_disclaimer"))).toBeVisible();
    const comparison = page.getByRole("table", { name: EN.ui("freeze_compare_caption") });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByRole("columnheader").first()).toHaveText(EN.ui("freeze_compare_col_attribute"));
    await expect(comparison.getByRole("columnheader")).toContainText([EN.ui("freeze_compare_col_validation"), EN.ui("freeze_section_before"), EN.ui("freeze_section_after"), EN.ui("freeze_section_last7"), EN.ui("freeze_compare_col_limit")]);
    await expect(comparison.getByText(EN.ui("col_trigger"))).toBeVisible();
    await expect(comparison.getByText(/^-?\d+\.\d{4}$/).first()).toBeVisible(); // disparidades con punto decimal
    await expect(comparison.getByText(/\d,\d{4}/)).toHaveCount(0);
    await expect(page.getByText(EN.ui("cell_insufficient")).first()).toBeVisible();
    await expect(page.getByText(EN.ui("freeze_no_data")).first()).toBeVisible();
    for (const toggle of await page.getByText(EN.ui("disparity_detail_toggle")).all()) await toggle.click();
    expect(await spanishLeft(page)).toEqual([]);
    // resolver: sin MFA reciente, «Verify and confirm» abre la ventana
    await page.getByRole("button", { name: EN.ui("resolve_open") }).click();
    const dialog = page.getByRole("dialog", { name: EN.ui("resolve_title") });
    await expect(dialog.getByRole("radio")).toHaveCount(3);
    for (const action of ["reactivar", "descartar", "investigar"]) await expect(dialog.getByRole("radio", { name: EN.label("RESOLUTION_ACTIONS", action) })).toBeVisible();
    await expect(dialog.getByText(EN.ui("resolve_reactivate_warning"))).toBeVisible();
    await expect(dialog.getByText(EN.ui("resolve_error_required"))).toBeVisible();
    await dialog.getByLabel(EN.ui("resolve_justification")).fill("Reviewed by compliance");
    await expect(dialog.getByText(EN.ui("resolve_counter", { count: "22" }))).toBeVisible();
    expect(await spanishLeft(page)).toEqual([]);
    await completeStepUp(context, () => page.getByRole("button", { name: EN.ui("verify_and_confirm") }).click(), "cumplimiento");
    await expect(page.getByText(EN.ui("freeze_resolution_done"))).toBeVisible();
    await expect(page.getByText(EN.ui("session_with_mfa"))).toBeVisible();
    // un 403 mfa_required inesperado: el dialogo de verificacion en dos pasos
    await control.forceMfaRequired(page, 1);
    await page.getByRole("button", { name: EN.ui("resolve_open") }).click();
    await page.getByLabel(EN.ui("resolve_justification")).fill("Second time");
    await page.getByRole("button", { name: EN.ui("resolve_submit") }).click();
    const stepUp = page.getByRole("dialog", { name: EN.ui("stepup_dialog_title") });
    await expect(stepUp).toContainText(EN.ui("stepup_dialog_body"));
    expect(await spanishLeft(page)).toEqual([]);
    await completeStepUp(context, () => stepUp.getByRole("button", { name: EN.ui("verify_identity") }).click(), "cumplimiento");
    await expect(page.getByText(EN.ui("freeze_resolution_done"))).toBeVisible();
    // modelos y su informe de validacion
    await goTo(page, "/modelos");
    await expect(page.getByText(EN.ui("models_intro"))).toBeVisible();
    await expect(page.getByRole("table").getByRole("columnheader")).toHaveText([EN.ui("col_model"), EN.ui("col_model_state"), EN.ui("col_registered_by"), EN.ui("col_updated")]);
    expect(await spanishLeft(page)).toEqual([]);
    await page.getByRole("link", { name: "mv-activo" }).click();
    await expect(page.getByRole("heading", { name: EN.ui("validation_title") })).toBeVisible();
    await expect(page.getByText(/^AUC-ROC: 0\.\d{4} \(target 0\.\d{4}\)$/)).toBeVisible();
    expect(await spanishLeft(page)).toEqual([]);
    // el aviso de inactividad
    await openInactivityDialog(page, EN);
    await expect(page.getByRole("alertdialog")).toContainText(EN.ui("idle_body"));
    expect(await spanishLeft(page)).toEqual([]);
    await page.getByRole("button", { name: EN.ui("idle_continue") }).click();
    await expect(page.getByRole("alertdialog")).toHaveCount(0);
  });

  for (const role of ["analista", "ingeniero_riesgo", "cro", "cumplimiento"] as const) {
    test(`recorrido de ${role} en ingles: en ninguna parada queda un texto del catalogo en espanol`, async ({ page, context }) => {
      const stops: string[] = [];
      await walk(
        page,
        context,
        role,
        async (name) => {
          expect(await spanishLeft(page), `textos en espanol en «${name}»`).toEqual([]);
          await expect(page.locator("html")).toHaveAttribute("lang", "en");
          stops.push(name);
        },
        EN,
      );
      expect(stops.length).toBeGreaterThan(2);
    });
  }
});
