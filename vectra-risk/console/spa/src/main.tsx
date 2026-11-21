// Punto de entrada (BR-U10-05, 06). Detecta `/stepup-callback` **antes** de montar React y de crear el `UserManager`.
// `/stepup-callback` solo corre `runStepUpCallback()`: no canjea, no guarda nada y no pide `config.json`.
import { entryKind } from "./entry";
import "./styles.css";

async function boot(): Promise<void> {
  const kind = entryKind(window.location.pathname);
  if (kind === "stepup-callback") {
    (await import("./stepup-callback")).runStepUpCallback();
    return;
  }
  // El idioma se fija antes de pintar (`<html lang>` y el titulo incluidos): la preferencia guardada o, si no hay, el idioma del navegador.
  // El tema ya lo puso `theme-boot.js` antes de la primera pintura; aqui lo toma el estado de la aplicacion.
  const [{ browserLanguageEnv, initLanguage }, { browserThemeEnv, initTheme }, { createLanguageStorage, createThemeStorage }] = await Promise.all([
    import("./i18n/language"),
    import("./theme/theme"),
    import("./preferences/storage"),
  ]);
  initTheme(browserThemeEnv(window, createThemeStorage(window)));
  initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
  const { loadConfig } = await import("./config/load");
  const config = await loadConfig();
  const [{ createRoot }, { App }, { createWiring }] = await Promise.all([
    import("react-dom/client"),
    import("./App"),
    import("./wiring"),
  ]);
  createRoot(document.getElementById("root") as HTMLElement).render(<App wiring={createWiring(config)} />);
}

void boot();
