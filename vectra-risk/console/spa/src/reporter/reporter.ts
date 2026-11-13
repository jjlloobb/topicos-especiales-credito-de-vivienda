// Reportero unico de errores del navegador (BR-U10-22; P-U10-09; NFR-U10-34).
//
// Traduce cada error al catalogo cerrado de `error_code` de `ClientErrorReport` (U0 §9.5; correspondencia en P-3 de U10-T03, `spa.md`)
// y lo envia al BFF, como maximo `REPORTER_MAX_PER_MINUTE` por ventana de 60 s; los que sobran se descartan (no se encolan). Envia
// solo `error_code`, `route_template` (la **plantilla** de la ruta, nunca la URL), `app_version` y, si lo hay, `correlation_id`: nunca
// mensajes, trazas, la URL con parametros ni datos de formularios. `fetch` con `keepalive`. Sin token no se envia. Un fallo del envio no
// genera otro reporte.
import { REPORTER_MAX_PER_MINUTE } from "../config/constants";

export type ErrorCode =
  | "render_error"
  | "chunk_load_failed"
  | "unhandled_rejection"
  | "api_contract_mismatch"
  | "stepup_failed"
  | "csp_violation";

export interface ClientErrorBody {
  readonly error_code: ErrorCode;
  readonly route_template: string;
  readonly app_version: string;
  readonly correlation_id?: string;
}

export interface ReporterDeps {
  readonly endpoint: string;
  readonly getToken: () => string | null;
  readonly routeTemplate: () => string;
  readonly appVersion: string;
  readonly fetchImpl?: typeof fetch;
  readonly now?: () => number;
}

const WINDOW_MS = 60_000;
const CORRELATION_ID = /^[0-9a-f]{32}$/;

export class Reporter {
  private sentAt: number[] = [];

  constructor(private readonly deps: ReporterDeps) {}

  /** Devuelve si el reporte salio (no si el BFF lo acepto): `false` si se descarto por el limite o por no tener token. */
  report(code: ErrorCode, correlationId?: string | null): boolean {
    const now = (this.deps.now ?? Date.now)();
    this.sentAt = this.sentAt.filter((at) => now - at < WINDOW_MS);
    const token = this.deps.getToken();
    if (token === null || this.sentAt.length >= REPORTER_MAX_PER_MINUTE) return false;
    this.sentAt.push(now);
    const body: ClientErrorBody = {
      error_code: code,
      route_template: this.deps.routeTemplate(),
      app_version: this.deps.appVersion,
      ...(correlationId != null && CORRELATION_ID.test(correlationId) ? { correlation_id: correlationId } : {}),
    };
    void (this.deps.fetchImpl ?? fetch)(this.deps.endpoint, {
      method: "POST",
      keepalive: true,
      headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    }).catch(() => undefined); // un fallo del envio no genera otro reporte
    return true;
  }

  /** Un `import()` de vista que no carga (el aviso con boton es de `version`, diferido). */
  reportChunkLoadFailure(): boolean {
    return this.report("chunk_load_failed");
  }

  /** Engancha `error`, `unhandledrejection` y `securitypolicyviolation`; devuelve la funcion que los suelta. */
  install(target: Pick<Window, "addEventListener" | "removeEventListener">): () => void {
    const handlers: [string, () => void][] = [
      ["error", () => this.report("unhandled_rejection")],
      ["unhandledrejection", () => this.report("unhandled_rejection")],
      ["securitypolicyviolation", () => this.report("csp_violation")],
    ];
    for (const [type, handler] of handlers) target.addEventListener(type, handler);
    return () => {
      for (const [type, handler] of handlers) target.removeEventListener(type, handler);
    };
  }
}

/**
 * La plantilla de la ruta de la SPA (P-7 (a)): conoce `/`, `/callback` y `/stepup-callback` y devuelve una plantilla fija para lo demas.
 * Nunca es `location.pathname` tal cual. U10-T04 la sustituye por la del enrutador.
 */
export function routeTemplateOf(pathname: string): string {
  return ["/", "/callback", "/stepup-callback"].includes(pathname) ? pathname : "/{ruta}";
}
