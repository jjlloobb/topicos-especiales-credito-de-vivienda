// El selector de idioma (enmienda del 2026-11-21 a NFR-U10-53): «Espanol», «English» o «Português», en la cabecera y en la pantalla de inicio de sesion.
// Su nombre accesible va en los dos idiomas («Idioma / Language»), para que lo encuentre tambien quien no lee el idioma en curso, y cada
// opcion lleva su propio `lang` (un lector de pantalla la pronuncia en su idioma). Elegir cambia el idioma ya, sin recargar, y guarda la
// preferencia (`i18n/language.ts`).
import { ui } from "../../i18n";
import { chooseLanguage, LANGUAGE_TAGS, LANGUAGES } from "../../i18n/language";
import { useLanguage } from "../../i18n/useLanguage";
import { IconLanguage } from "./icons";
import { PreferenceSelect } from "./PreferenceSelect";

const NAMES = { es: "language_name_es", en: "language_name_en", pt: "language_name_pt" } as const;

export function LanguageSelect({ onBrand = false }: { readonly onBrand?: boolean }) {
  const language = useLanguage();
  return (
    <PreferenceSelect
      label={ui("language_label")}
      icon={<IconLanguage />}
      options={LANGUAGES.map((id) => ({ id, text: ui(NAMES[id]), lang: LANGUAGE_TAGS[id] }))}
      selected={language}
      onChange={chooseLanguage}
      onBrand={onBrand}
    />
  );
}
