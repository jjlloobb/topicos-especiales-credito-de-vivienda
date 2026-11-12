// BR-U10-22; P-U10-09; NFR-U10-34: el `reporter` del navegador.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { REPORTER_MAX_PER_MINUTE } from "../../../src/config/constants";
import { type ErrorCode, Reporter, routeTemplateOf } from "../../../src/reporter/reporter";
import { APP_VERSION } from "../../../src/reporter/version";

const SPA = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const CODES: ErrorCode[] = ["render_error", "chunk_load_failed", "unhandled_rejection", "api_contract_mismatch", "stepup_failed", "csp_violation"];
const ALLOWED = new Set(["error_code", "route_template", "app_version", "correlation_id"]);

function setup(over: { token?: string | null; fail?: boolean } = {}) {
  let now = 1_000_000;
  const sent: { url: string; init: RequestInit }[] = [];
  const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    sent.push({ url: String(url), init: init as RequestInit });
    if (over.fail) throw new Error("red");
    return new Response(null, { status: 204 });
  });
  const reporter = new Reporter({
    endpoint: "/api/console/client-errors",
    getToken: () => (over.token === undefined ? "tok" : over.token),
    routeTemplate: () => "/",
    appVersion: "0.1.0",
    fetchImpl: fetchImpl as typeof fetch,
    now: () => now,
  });
  return { reporter, sent, fetchImpl, advance: (ms: number) => (now += ms) };
}

describe("el envio", () => {
  it("envia solo ClientErrorReport, con fetch keepalive y el token", () => {
    const { reporter, sent } = setup();
    expect(reporter.report("render_error")).toBe(true);
    const init = sent[0]?.init as RequestInit;
    expect(sent[0]?.url).toBe("/api/console/client-errors");
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    expect((init.headers as Record<string, string>)["authorization"]).toBe("Bearer tok");
    expect(JSON.parse(init.body as string)).toEqual({ error_code: "render_error", route_template: "/", app_version: "0.1.0" });
  });

  it("incluye correlation_id solo si es valido (32 hex)", () => {
    const { reporter, sent } = setup();
    reporter.report("api_contract_mismatch", "ab".repeat(16));
    reporter.report("api_contract_mismatch", "no-es-un-id");
    reporter.report("api_contract_mismatch", null);
    const bodies = sent.map((s) => JSON.parse(s.init.body as string) as Record<string, unknown>);
    expect(bodies[0]?.["correlation_id"]).toBe("ab".repeat(16));
    expect(bodies[1]).not.toHaveProperty("correlation_id");
    expect(bodies[2]).not.toHaveProperty("correlation_id");
  });

  it("sin token no se envia", () => {
    const { reporter, fetchImpl } = setup({ token: null });
    expect(reporter.report("render_error")).toBe(false);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("un fallo del envio no genera otro reporte ni una excepcion", async () => {
    const { reporter, fetchImpl } = setup({ fail: true });
    expect(reporter.report("render_error")).toBe(true);
    await Promise.resolve();
    await Promise.resolve();
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it("usa el fetch global y Date.now por omision", () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const reporter = new Reporter({ endpoint: "/x", getToken: () => "t", routeTemplate: () => "/", appVersion: "0.1.0" });
    expect(reporter.report("render_error")).toBe(true);
    expect(fetchMock).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
  });
});

describe("el limite de 10 por minuto", () => {
  it("20 errores en un minuto -> exactamente 10 envios, ninguno con una clave fuera de ClientErrorReport ni una ruta con ? o un identificador", () => {
    const { reporter, sent, advance } = setup();
    let accepted = 0;
    for (let i = 0; i < 20; i += 1) {
      advance(1000);
      if (reporter.report(CODES[i % CODES.length] as ErrorCode, i % 2 === 0 ? "cd".repeat(16) : undefined)) accepted += 1;
    }
    expect(accepted).toBe(REPORTER_MAX_PER_MINUTE);
    expect(sent).toHaveLength(10);
    for (const { init } of sent) {
      const body = JSON.parse(init.body as string) as Record<string, string>;
      for (const key of Object.keys(body)) expect(ALLOWED.has(key)).toBe(true);
      expect(body["route_template"]).not.toMatch(/[?#]|\d{4,}|[0-9a-f]{8}-/);
      expect(CODES).toContain(body["error_code"]);
      expect(body["app_version"]).toMatch(/^\d+\.\d+\.\d+$/);
    }
  });

  it("los que sobran se descartan, no se encolan: pasado el minuto vuelve a enviar", () => {
    const { reporter, sent, advance } = setup();
    for (let i = 0; i < 15; i += 1) reporter.report("render_error");
    expect(sent).toHaveLength(10);
    advance(59_999);
    expect(reporter.report("render_error")).toBe(false);
    advance(1);
    expect(reporter.report("render_error")).toBe(true);
    expect(sent).toHaveLength(11); // solo el nuevo: los 5 descartados no se reenviaron
  });
});

describe("las fuentes", () => {
  it("install engancha error, unhandledrejection y securitypolicyviolation, y los suelta", () => {
    const { reporter, sent } = setup();
    const target = new EventTarget();
    const off = reporter.install(target);
    target.dispatchEvent(new Event("error"));
    target.dispatchEvent(new Event("unhandledrejection"));
    target.dispatchEvent(new Event("securitypolicyviolation"));
    expect(sent.map((s) => (JSON.parse(s.init.body as string) as { error_code: string }).error_code)).toEqual([
      "unhandled_rejection",
      "unhandled_rejection",
      "csp_violation",
    ]);
    off();
    target.dispatchEvent(new Event("error"));
    expect(sent).toHaveLength(3);
  });

  it("un fallo de carga de fragmento es chunk_load_failed", () => {
    const { reporter, sent } = setup();
    reporter.reportChunkLoadFailure();
    expect(JSON.parse(sent[0]?.init.body as string)).toMatchObject({ error_code: "chunk_load_failed" });
  });

  it("ni el mensaje ni la traza del error salen: el cuerpo no tiene mas claves que las del catalogo", () => {
    const { reporter, sent } = setup();
    const target = new EventTarget();
    reporter.install(target);
    target.dispatchEvent(Object.assign(new Event("error"), { message: "secreto", error: new Error("traza"), filename: "https://x/y?token=1" }));
    expect(sent[0]?.init.body).not.toContain("secreto");
    expect(sent[0]?.init.body).not.toContain("token=1");
  });
});

describe("route_template (P-7 (a)) y app_version", () => {
  it("conoce /, /callback y /stepup-callback; lo demas es una plantilla fija, nunca la ruta tal cual", () => {
    expect(["/", "/callback", "/stepup-callback"].map(routeTemplateOf)).toEqual(["/", "/callback", "/stepup-callback"]);
    expect(routeTemplateOf("/cases/5b1d3f0e-0000-4000-8000-000000000001")).toBe("/{ruta}");
    expect(routeTemplateOf("/models/mv-123/freeze")).toBe("/{ruta}");
  });

  it("app_version es SemVer y es el `version` de package.json", () => {
    const pkg = JSON.parse(readFileSync(resolve(SPA, "package.json"), "utf-8")) as { version: string };
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
    expect(APP_VERSION).toBe(pkg.version);
  });
});
