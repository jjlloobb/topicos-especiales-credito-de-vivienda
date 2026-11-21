// El tema de la interfaz (enmienda del 2026-11-21 a NFR-U10-51): «Sistema» (por omision: decide `prefers-color-scheme`, como antes), «Claro»
// u «Oscuro». La paleta es UNA (`styles.css`: cada token lleva su valor claro y su valor oscuro con `light-dark()`); elegir un tema solo pone
// `data-theme="light"` o `"dark"` en `<html>`, que fija `color-scheme` y gana a la preferencia del sistema en los dos sentidos; «Sistema»
// quita el atributo. Solo la eleccion explicita se guarda (`preferences/storage.ts`); no viaja al servidor.
//
// Antes de la primera pintura lo aplica `public/theme-boot.js` (la memoria de la pagina aun no existe); este modulo lo repite al arrancar
// (`main.tsx`) y lo cambia despues sin recargar.
export const THEMES = ["system", "light", "dark"] as const;
export type ThemeChoice = (typeof THEMES)[number];
export const DEFAULT_THEME: ThemeChoice = "system";

export function themeOf(value: unknown): ThemeChoice | null {
  return THEMES.find((theme) => theme === value) ?? null;
}

export interface ThemeStorage {
  read(): ThemeChoice | null;
  write(theme: ThemeChoice): void;
}

export interface ThemeEnv {
  readonly storage: ThemeStorage | null;
  /** El elemento raiz (`<html>`) que lleva `data-theme`. */
  readonly root: Pick<HTMLElement, "setAttribute" | "removeAttribute"> | null;
}

const NO_ENV: ThemeEnv = { storage: null, root: null };

let env: ThemeEnv = NO_ENV;
let current: ThemeChoice = DEFAULT_THEME;
const listeners = new Set<() => void>();

function apply(next: ThemeChoice): void {
  const changed = next !== current;
  current = next;
  if (env.root !== null) {
    if (next === "system") env.root.removeAttribute("data-theme");
    else env.root.setAttribute("data-theme", next);
  }
  if (changed) for (const listener of [...listeners]) listener();
}

export function getTheme(): ThemeChoice {
  return current;
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Al arrancar la pagina (`main.tsx`), antes de pintar: el tema guardado o «Sistema». Sin argumento vuelve al estado de fabrica. */
export function initTheme(next: ThemeEnv = NO_ENV): void {
  env = next;
  apply(env.storage?.read() ?? DEFAULT_THEME);
}

/** La persona elige el tema en el selector: cambia ya, sin recargar, y queda guardado. */
export function chooseTheme(theme: ThemeChoice): void {
  env.storage?.write(theme);
  apply(theme);
}

export function browserThemeEnv(win: Window, storage: ThemeStorage | null): ThemeEnv {
  return { storage, root: win.document.documentElement };
}
