// La carga a demanda de cada vista (NFR-U10-03): `React.lazy` sobre un `import()`. Un `import()` que falla se reporta como
// `chunk_load_failed` (BR-U10-22) y el error sube al `ErrorBoundary`.
import { type ComponentType, lazy, type LazyExoticComponent } from "react";

export type Loader = () => Promise<{ readonly default: ComponentType }>;

export function lazyView(loader: Loader, onFailure: () => void): LazyExoticComponent<ComponentType> {
  return lazy(() =>
    loader().catch((error: unknown) => {
      onFailure();
      throw error;
    }),
  );
}
