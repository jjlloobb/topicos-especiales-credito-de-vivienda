// Los `import()` de las vistas que entran: cada una es un fragmento aparte (NFR-U10-03), fuera del paquete inicial.
import type { Loader } from "./lazyView";
import type { ViewId } from "./routes";

export const LOADERS: Partial<Record<ViewId, Loader>> = {
  CasesInbox: () => import("../cases/CasesInbox").then((m) => ({ default: m.CasesInbox })),
  CaseDetail: () => import("../cases/CaseDetail").then((m) => ({ default: m.CaseDetail })),
  Models: () => import("../governance/Models").then((m) => ({ default: m.Models })),
  ModelDetail: () => import("../governance/ModelDetail").then((m) => ({ default: m.ModelDetail })),
  Freezes: () => import("../governance/Freezes").then((m) => ({ default: m.Freezes })),
  FreezeContextView: () => import("../governance/FreezeContextView").then((m) => ({ default: m.FreezeContextView })),
};
