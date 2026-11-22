// Las preferencias de la persona que se guardan en el navegador (enmienda del 2026-11-21 a BR-U10-05 y NFR-U10-53; pedido del dueno del
// proyecto para la sustentacion): el idioma y el tema. Es el UNICO modulo de `src/` que toca el almacenamiento local del navegador (excepcion
// acotada de ESLint, `eslint.config.mjs`). Son DOS claves, cada una con un valor de un conjunto cerrado («es» | «en» | «pt»; «system» | «light» |
// «dark»), y solo se escriben cuando la persona elige en el selector: no son datos personales ni secretos, y los tokens, el usuario y el
// estado del login NO pasan por aqui (siguen en memoria y en `auth/loginStateStorage.ts`). Van en el almacenamiento local y no en el de
// sesion para que sobrevivan al cierre de la pestana y no anadan claves al de sesion, que es del login. Lo que se lee se valida: cualquier
// otro valor es como si no hubiera preferencia. Si el navegador no deja leer o escribir (modo privado, bloqueado), no pasa nada.
//
// `public/theme-boot.js` lee la clave del tema ANTES de la primera pintura (un guion clasico del mismo origen: la CSP no admite guiones en
// linea): la clave y los valores de alla son los de aqui (`tests/unit/theme/theme-boot.test.ts` los ata).
import type { Language, LanguageStorage } from "../i18n/language";
import type { ThemeChoice, ThemeStorage } from "../theme/theme";

export const LANGUAGE_KEY = "vectra.console.language";
export const THEME_KEY = "vectra.console.theme";

const LANGUAGE_VALUES: readonly Language[] = ["es", "en", "pt"];
const THEME_VALUES: readonly ThemeChoice[] = ["system", "light", "dark"];

function entry<T extends string>(win: Window, key: string, values: readonly T[]) {
  return {
    read: (): T | null => {
      try {
        const value = win.localStorage.getItem(key);
        return values.find((allowed) => allowed === value) ?? null;
      } catch {
        return null;
      }
    },
    write: (value: T): void => {
      try {
        win.localStorage.setItem(key, value);
      } catch {
        // Sin almacenamiento: la eleccion vale para esta carga de pagina.
      }
    },
  };
}

export function createLanguageStorage(win: Window = window): LanguageStorage {
  return entry(win, LANGUAGE_KEY, LANGUAGE_VALUES);
}

export function createThemeStorage(win: Window = window): ThemeStorage {
  return entry(win, THEME_KEY, THEME_VALUES);
}
