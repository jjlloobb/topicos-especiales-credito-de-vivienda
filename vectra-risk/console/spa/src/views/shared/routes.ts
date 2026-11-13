// La tabla de rutas por rol (BR-U10-12; U10-T04): un solo modulo, y cada ruta nombra el `operation_id` de C03 que le da los roles.
// La prueba `tests/unit/views/governance/routes-by-role.test.ts` la compara, ruta por ruta, con la columna «Roles» de
// `aidlc-docs/inception/application-design/component-methods.md` (C03), nunca con esta misma tabla. Se declaran TODAS las vistas de
// frontend-components §1: las que el recorte difiere (`entry: false`) llevan el marcador «no disponible» (P-17 del recorte funcional).
import type { ROLES } from "@vectra/contracts";
import { matchPath } from "react-router";
import type { UiKey } from "../../i18n";

export type Role = (typeof ROLES)[number];

export type ViewId =
  | "CasesInbox"
  | "CaseDetail"
  | "ManualApplicationForm"
  | "PersistentFailures"
  | "Dossier"
  | "IntegrityCheck"
  | "Models"
  | "ModelDetail"
  | "Policies"
  | "DataSources"
  | "BiasDashboard"
  | "Freezes"
  | "FreezeContextView";

export interface RouteSpec {
  readonly view: ViewId;
  /** El patron de React Router. */
  readonly path: string;
  /** La operacion de C03 (`component-methods.md`) de la que salen los roles. */
  readonly operation: string;
  readonly roles: readonly Role[];
  readonly title: UiKey;
  /** `false`: la vista esta diferida y la ruta muestra el marcador (no llama al BFF). */
  readonly entry: boolean;
  /** Aparece en el menu (las rutas con parametro no). */
  readonly inMenu: boolean;
}

export const ROUTES: readonly RouteSpec[] = [
  { view: "CasesInbox", path: "/casos", operation: "list_cases", roles: ["analista", "cro"], title: "view_cases", entry: true, inMenu: true },
  { view: "CaseDetail", path: "/casos/:caseId", operation: "get_case", roles: ["analista", "cro"], title: "view_case_detail", entry: true, inMenu: false },
  { view: "ManualApplicationForm", path: "/casos/nuevo", operation: "create_application", roles: ["analista"], title: "view_manual_application", entry: false, inMenu: true },
  { view: "PersistentFailures", path: "/fallos", operation: "list_persistent_failures", roles: ["cro"], title: "view_failures", entry: false, inMenu: true },
  { view: "Dossier", path: "/expedientes", operation: "get_dossier", roles: ["cro", "cumplimiento"], title: "view_dossier", entry: false, inMenu: true },
  { view: "IntegrityCheck", path: "/integridad", operation: "run_integrity_check", roles: ["cro"], title: "view_integrity", entry: false, inMenu: true },
  { view: "Models", path: "/modelos", operation: "list_models", roles: ["ingeniero_riesgo", "cro", "cumplimiento"], title: "view_models", entry: true, inMenu: true },
  { view: "ModelDetail", path: "/modelos/:modelId", operation: "get_model", roles: ["ingeniero_riesgo", "cro", "cumplimiento"], title: "view_model_detail", entry: true, inMenu: false },
  { view: "Policies", path: "/politicas", operation: "list_policies", roles: ["analista", "cro", "cumplimiento"], title: "view_policies", entry: false, inMenu: true },
  { view: "DataSources", path: "/fuentes", operation: "list_data_sources", roles: ["ingeniero_riesgo", "cro", "cumplimiento"], title: "view_sources", entry: false, inMenu: true },
  { view: "BiasDashboard", path: "/sesgo", operation: "get_disparity", roles: ["cumplimiento", "cro"], title: "view_bias", entry: false, inMenu: true },
  { view: "Freezes", path: "/congelamientos", operation: "list_freezes", roles: ["cumplimiento", "cro"], title: "view_freezes", entry: true, inMenu: true },
  { view: "FreezeContextView", path: "/congelamientos/:freezeId", operation: "get_freeze", roles: ["cumplimiento"], title: "view_freeze_context", entry: true, inMenu: false },
];

export function routesFor(role: Role): readonly RouteSpec[] {
  return ROUTES.filter((route) => route.roles.includes(role));
}

/** La pantalla de inicio de cada rol (a donde lleva `/`): su vista principal, que es una ruta a la que el rol llega (una prueba lo comprueba). */
export const HOME: Readonly<Record<Role, string>> = {
  analista: "/casos",
  ingeniero_riesgo: "/modelos",
  cro: "/casos",
  cumplimiento: "/congelamientos",
};

export function homeFor(role: Role): string {
  return HOME[role];
}

// Las rutas estaticas primero (`/casos/nuevo` antes de `/casos/:caseId`).
const STATIC_FIRST = [...ROUTES.filter((route) => !route.path.includes(":")), ...ROUTES.filter((route) => route.path.includes(":"))];

/** La plantilla de la ruta para el `reporter` (P-7 (a) de U10-T03): nunca la URL con identificadores. */
export function routeTemplate(pathname: string): string {
  if (["/", "/callback", "/stepup-callback"].includes(pathname)) return pathname;
  const found = STATIC_FIRST.find((route) => matchPath({ path: route.path, end: true }, pathname) !== null);
  return found === undefined ? "/{ruta}" : found.path;
}
