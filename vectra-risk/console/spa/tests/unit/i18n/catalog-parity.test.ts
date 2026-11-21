// Los catalogos en ingles tienen EXACTAMENTE las claves de los catalogos en espanol (ni una mas ni una menos, en el mismo orden) y cada mensaje
// lleva los mismos marcadores de interpolacion (`{nombre}`): un texto nuevo en un idioma rompe esta prueba hasta que exista en el otro.
// Ademas: ningun texto vacio, ninguna frase prohibida de U0 en ingles (BR-U10-18) y ningun texto en ingles igual al espanol salvo los que
// se escriben igual en los dos idiomas (lista explicita), para que un texto copiado sin traducir no pase.
import { describe, expect, it } from "vitest";
import labelsEn from "../../../src/i18n/labels.en.json";
import labelsEs from "../../../src/i18n/labels.es.json";
import messagesEn from "../../../src/i18n/messages.en.json";
import messagesEs from "../../../src/i18n/messages.es.json";
import { allStrings, forbiddenPatterns, violations } from "../../support/phrases";

const CATALOGS = [
  ["messages", messagesEs, messagesEn],
  ["labels", labelsEs, labelsEn],
] as const;

const placeholders = (text: string): string[] => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1] as string).sort();

// Se escriben igual en espanol y en ingles: la marca, los nombres de los idiomas (cada uno en su idioma) y palabras comunes a los dos.
const SAME_IN_BOTH = new Set([
  "ui.app_title",
  "ui.document_title_view", // «{pantalla} · Vectra Risk»: la pantalla va traducida; lo fijo es la marca
  "ui.language_name_es",
  "ui.language_name_en",
  "ui.freeze_source_item",
  "FINAL_OUTCOMES.favorable",
  "OUTCOMES.favorable",
  "CHANNELS.web",
  "CHANNELS.manual",
]);

describe("paridad de los catalogos es / en", () => {
  it.each(CATALOGS)("%s: las mismas claves, en el mismo orden", (_name, es, en) => {
    const keysEs = allStrings(es).map(([path]) => path);
    const keysEn = allStrings(en).map(([path]) => path);
    expect(keysEs.length).toBeGreaterThan(100);
    expect(keysEn).toEqual(keysEs);
  });

  it.each(CATALOGS)("%s: cada texto tiene los mismos marcadores de interpolacion en los dos idiomas", (_name, es, en) => {
    const english = new Map(allStrings(en));
    for (const [path, text] of allStrings(es)) {
      expect(placeholders(english.get(path) ?? ""), `marcadores de ${path}`).toEqual(placeholders(text));
    }
  });

  it("hay mensajes con marcadores (la comparacion no es vacia) y un marcador distinto se detecta", () => {
    expect(allStrings(messagesEs).filter(([, text]) => placeholders(text).length > 0).length).toBeGreaterThan(30);
    expect(placeholders("Página {page} de {pages}")).toEqual(["page", "pages"]);
    expect(placeholders("Page {page} of {total}")).not.toEqual(placeholders("Página {page} de {pages}"));
  });

  it("ningun texto vacio ni con espacios en los bordes, en ningun idioma", () => {
    for (const [, es, en] of CATALOGS) {
      for (const [path, text] of [...allStrings(es), ...allStrings(en)]) {
        expect(text.length, path).toBeGreaterThan(0);
        expect(text, path).toBe(text.trim());
      }
    }
  });

  it("ningun texto en ingles es el espanol copiado (salvo los que se escriben igual)", () => {
    const same: string[] = [];
    for (const [, es, en] of CATALOGS) {
      const english = new Map(allStrings(en));
      for (const [path, text] of allStrings(es)) if (english.get(path) === text) same.push(path);
    }
    expect(same.sort()).toEqual([...SAME_IN_BOTH].sort());
  });

  it("los nombres de los idiomas van cada uno en su idioma, en los dos catalogos", () => {
    for (const messages of [messagesEs, messagesEn]) {
      expect(messages.ui.language_name_es).toBe("Español");
      expect(messages.ui.language_name_en).toBe("English");
    }
  });

  it("BR-U10-18: ningun texto en ingles contiene una frase prohibida", () => {
    const patterns = forbiddenPatterns();
    for (const [path, text] of [...allStrings(messagesEn), ...allStrings(labelsEn)]) {
      expect(violations(text, patterns), `${path} contiene una frase prohibida`).toEqual([]);
    }
    expect(violations("This model is unbiased.", patterns)).toEqual(["unbiased"]);
  });
});
