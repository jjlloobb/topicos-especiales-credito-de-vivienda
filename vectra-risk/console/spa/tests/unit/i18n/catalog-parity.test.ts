// Los catalogos en ingles y en portugues tienen EXACTAMENTE las claves de los catalogos en espanol (ni una mas ni una menos, en el mismo orden)
// y cada mensaje lleva los mismos marcadores de interpolacion (`{nombre}`): un texto nuevo en un idioma rompe esta prueba hasta que exista en
// los otros dos. Ademas: ningun texto vacio, ninguna frase prohibida de U0 en ingles ni en portugues (BR-U10-18) y ningun texto traducido igual
// al espanol salvo los que se escriben igual en los dos idiomas (lista explicita por idioma), para que un texto copiado sin traducir no pase.
import { describe, expect, it } from "vitest";
import labelsEn from "../../../src/i18n/labels.en.json";
import labelsEs from "../../../src/i18n/labels.es.json";
import labelsPt from "../../../src/i18n/labels.pt.json";
import messagesEn from "../../../src/i18n/messages.en.json";
import messagesEs from "../../../src/i18n/messages.es.json";
import messagesPt from "../../../src/i18n/messages.pt.json";
import { allStrings, forbiddenPatterns, violations } from "../../support/phrases";

const TRANSLATIONS = [
  ["en", "messages", messagesEs, messagesEn],
  ["en", "labels", labelsEs, labelsEn],
  ["pt", "messages", messagesEs, messagesPt],
  ["pt", "labels", labelsEs, labelsPt],
] as const;
const ALL = [messagesEs, labelsEs, messagesEn, labelsEn, messagesPt, labelsPt];

const placeholders = (text: string): string[] => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1] as string).sort();

// Se escriben igual en espanol y en ingles: la marca, los nombres de los idiomas (cada uno en su idioma) y palabras comunes a los dos.
const SAME_AS_SPANISH_EN = [
  "ui.app_title",
  "ui.document_title_view", // «{pantalla} · Vectra Risk»: la pantalla va traducida; lo fijo es la marca
  "ui.language_name_es",
  "ui.language_name_en",
  "ui.language_name_pt",
  "ui.freeze_source_item",
  "FINAL_OUTCOMES.favorable",
  "OUTCOMES.favorable",
  "CHANNELS.web",
  "CHANNELS.manual",
];

// Se escriben igual en espanol y en portugues de Brasil: son lenguas hermanas y estas palabras coinciden letra por letra («Canal», «Estado»,
// «Modelo congelado», «Página anterior»...). La lista es explicita y esta revisada una por una: un texto NUEVO igual al espanol rompe la prueba
// hasta que alguien confirme que en portugues se escribe igual.
const SAME_AS_SPANISH_PT = [
  "ui.app_title", "ui.stepup_dialog_cancel", "ui.view_models", "ui.view_policies", "ui.filters_legend", "ui.filter_states", "ui.filter_channel",
  "ui.col_state", "ui.col_channel", "ui.col_open", "ui.open_case", "ui.page_previous", "ui.page_current", "ui.recommendation_outcome",
  "ui.explanation_narrative", "ui.application_channel", "ui.application_department", "ui.decision_sending", "ui.col_model_state",
  "ui.col_registered_by", "ui.model_state", "ui.model_registered_by", "ui.validation_auc", "ui.validation_disclaimer", "ui.col_trigger",
  "ui.freeze_open_context", "ui.freeze_summary_trigger", "ui.freeze_section_before", "ui.disparity_attribute", "ui.disparity_aggregate",
  "ui.disparity_col_group", "ui.disparity_col_n", "ui.resolve_counter", "ui.freeze_source_item", "ui.page_of", "ui.page_last",
  "ui.freeze_compare_col_attribute", "ui.language_label", "ui.language_name_es", "ui.language_name_en", "ui.language_name_pt", "ui.theme_label",
  "ui.theme_system", "ui.theme_light", "ui.col_case_id", "ui.copy_button", "ui.copy_done", "ui.document_title_view", "ui.page_jump_button",
  "CASE_STATES.modelo_congelado", "CASE_STATES.decidido", "CASE_STATES.vencido", "CREDIT_STATUSES.cancelado", "ENTRY_TYPES.model_event",
  "ENTRY_TYPES.policy_event", "FAIL_CLOSED_CAUSES.model_frozen", "LOG_EVENTS.case.viewed", "ROLES.analista", "SCOPES.case:recommend",
  "SCOPES.governance:freeze", "SCOPES.governance:promotion", "SCOPES.registry:append:case", "SERVING_STATES.congelado", "MODEL_STATES.registrado",
  "MODEL_STATES.congelado", "MODEL_STATES.retirado", "RESOLUTION_ACTIONS.descartar", "RESOLUTION_ACTIONS.investigar", "ATTRIBUTES.sexo",
  "ATTRIBUTES.estrato", "BANDS.lt_20", "BANDS.20_30", "CHANNELS.web", "CHANNELS.manual", "GROUPS.M", "GROUPS.andina", "GROUPS.caribe",
  "GROUPS.pacifica", "GROUPS.insular",
];
const SAME_AS_SPANISH = { en: SAME_AS_SPANISH_EN, pt: SAME_AS_SPANISH_PT } as const;

describe("paridad de los catalogos es / en / pt", () => {
  it.each(TRANSLATIONS)("%s, %s: las mismas claves que en espanol, en el mismo orden", (_language, _name, es, other) => {
    const keysEs = allStrings(es).map(([path]) => path);
    const keysOther = allStrings(other).map(([path]) => path);
    expect(keysEs.length).toBeGreaterThan(100);
    expect(keysOther).toEqual(keysEs);
  });

  it.each(TRANSLATIONS)("%s, %s: cada texto tiene los mismos marcadores de interpolacion que en espanol", (_language, _name, es, other) => {
    const translated = new Map(allStrings(other));
    for (const [path, text] of allStrings(es)) {
      expect(placeholders(translated.get(path) ?? ""), `marcadores de ${path}`).toEqual(placeholders(text));
    }
  });

  it("hay mensajes con marcadores (la comparacion no es vacia) y un marcador distinto se detecta", () => {
    expect(allStrings(messagesEs).filter(([, text]) => placeholders(text).length > 0).length).toBeGreaterThan(30);
    expect(placeholders("Página {page} de {pages}")).toEqual(["page", "pages"]);
    expect(placeholders("Page {page} of {total}")).not.toEqual(placeholders("Página {page} de {pages}"));
  });

  it("ningun texto vacio ni con espacios en los bordes, en ningun idioma", () => {
    for (const catalog of ALL) {
      for (const [path, text] of allStrings(catalog)) {
        expect(text.length, path).toBeGreaterThan(0);
        expect(text, path).toBe(text.trim());
      }
    }
  });

  it.each(["en", "pt"] as const)("ningun texto en %s es el espanol copiado (salvo los que se escriben igual)", (language) => {
    const same: string[] = [];
    for (const [of, , es, other] of TRANSLATIONS) {
      if (of !== language) continue;
      const translated = new Map(allStrings(other));
      for (const [path, text] of allStrings(es)) if (translated.get(path) === text) same.push(path);
    }
    expect(same.sort()).toEqual([...SAME_AS_SPANISH[language]].sort());
  });

  it("el portugues no es el ingles copiado: solo coinciden la marca, los nombres de los idiomas, «Compliance» y lo que no tiene palabras", () => {
    const english = new Map([...allStrings(messagesEn), ...allStrings(labelsEn)]);
    const same = [...allStrings(messagesPt), ...allStrings(labelsPt)].filter(([path, text]) => english.get(path) === text).map(([path]) => path);
    expect(same.sort()).toEqual(
      ["ui.app_title", "ui.document_title_view", "ROLES.cumplimiento", "ui.language_name_es", "ui.language_name_en", "ui.language_name_pt", "ui.freeze_source_item", "CHANNELS.web", "CHANNELS.manual"].sort(),
    );
  });

  it("los nombres de los idiomas van cada uno en su idioma, en los tres catalogos", () => {
    for (const messages of [messagesEs, messagesEn, messagesPt]) {
      expect(messages.ui.language_name_es).toBe("Español");
      expect(messages.ui.language_name_en).toBe("English");
      expect(messages.ui.language_name_pt).toBe("Português");
    }
  });

  it("BR-U10-18: ningun texto en ingles ni en portugues contiene una frase prohibida", () => {
    const patterns = forbiddenPatterns();
    for (const [path, text] of [...allStrings(messagesEn), ...allStrings(labelsEn), ...allStrings(messagesPt), ...allStrings(labelsPt)]) {
      expect(violations(text, patterns), `${path} contiene una frase prohibida`).toEqual([]);
    }
    expect(violations("This model is unbiased.", patterns)).toEqual(["unbiased"]);
  });

  it("BR-U10-18 en portugues: la lista de U0 no trae frases en portugues, asi que se comprueban aqui las equivalentes a las suyas", () => {
    // Las mismas ideas que prohibe `contracts/forbidden-phrases.yaml` (el modelo «no tiene sesgo», «es justo», «esta certificado», «garantiza»),
    // dichas en portugues. No sustituye a ampliar la lista de U0 (candidata): impide que el catalogo de la consola las afirme.
    const banned = [/\bsem vies\b/, /\blivre de vies\b/, /\bimparcial\b/, /\bnao discrimina\b/, /\bjusto\b/, /\bcertificad[oa]\b/, /\bgarant(e|ido|ida|imos)\b/];
    const normalize = (text: string): string => text.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();
    for (const [path, text] of [...allStrings(messagesPt), ...allStrings(labelsPt)]) {
      expect(banned.filter((pattern) => pattern.test(normalize(text))).map(String), path).toEqual([]);
    }
    expect(banned.some((pattern) => pattern.test(normalize("O modelo é livre de viés.")))).toBe(true);
  });
});
