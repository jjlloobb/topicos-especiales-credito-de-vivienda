// Punto de entrada (BR-U10-05, 06). Detecta `/stepup-callback` **antes** de montar React y de crear el `UserManager`.
// `/stepup-callback` solo corre `runStepUpCallback()`: no canjea, no guarda nada y no pide `config.json`.
import { entryKind } from "./entry";

async function boot(): Promise<void> {
  const kind = entryKind(window.location.pathname);
  if (kind === "stepup-callback") {
    (await import("./stepup-callback")).runStepUpCallback();
    return;
  }
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
