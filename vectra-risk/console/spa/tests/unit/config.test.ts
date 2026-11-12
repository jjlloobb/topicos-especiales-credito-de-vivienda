// CA-5 (Paso 2): constantes de domain-entities §4, `IDLE_LOGOUT_SECONDS` contra los tres realms de U2 y `load.ts`.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { describe, expect, it } from "vitest";
import * as constants from "../../src/config/constants";
import { ConfigError, loadConfig, parseConfig } from "../../src/config/load";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");

// domain-entities §4 de U10, segunda tabla «Constantes del código», transcrita una sola vez.
const TABLE = {
  STEPUP_TIMEOUT_SECONDS: 300,
  IDLE_WARNING_SECONDS: 1500,
  IDLE_LOGOUT_SECONDS: 1800,
  ACTIVITY_BROADCAST_SECONDS: 30,
  VERSION_POLL_SECONDS: 300,
  REPORTER_MAX_PER_MINUTE: 10,
  API_TIMEOUT_SECONDS: 10,
  INBOX_REFRESH_SECONDS: 15,
  CASE_REFRESH_SECONDS: 3,
  CASE_REFRESH_MAX_SECONDS: 120,
} as const;

const VALID = {
  oidc: { authority: "https://console.vectra.example/auth/realms/vectra", client_id: "vectra-console" },
  redirect_uri: "https://console.vectra.example/",
  stepup_redirect_uri: "https://console.vectra.example/stepup-callback",
  grafana: { bias_dashboard_uid: "vectra-bias" },
};

describe("constants.ts", () => {
  it("coincide con la tabla de domain-entities §4", () => {
    expect({ ...constants.TIME_CONSTANTS }).toEqual(TABLE);
    for (const [name, value] of Object.entries(TABLE)) {
      expect((constants as Record<string, unknown>)[name]).toBe(value);
    }
  });

  it("el aviso de inactividad llega antes del cierre", () => {
    expect(constants.IDLE_WARNING_SECONDS).toBeLessThan(constants.IDLE_LOGOUT_SECONDS);
    expect(constants.CASE_REFRESH_SECONDS).toBeLessThan(constants.CASE_REFRESH_MAX_SECONDS);
  });

  it.each(["kind", "staging", "prod"])("IDLE_LOGOUT_SECONDS = ssoSessionIdleTimeout de realm.%s.yaml", (env) => {
    const path = resolve(VECTRA_RISK, "identity-edge", "keycloak", "realm", `realm.${env}.yaml`);
    const realm = parse(readFileSync(path, "utf-8")) as { ssoSessionIdleTimeout?: number };
    expect(realm.ssoSessionIdleTimeout).toBe(constants.IDLE_LOGOUT_SECONDS);
  });
});

describe("load.ts", () => {
  it("acepta un config.json completo", () => {
    expect(parseConfig(VALID)).toEqual(VALID);
  });

  it.each([
    ["oidc.authority", { ...VALID, oidc: { client_id: "vectra-console" } }],
    ["oidc.client_id", { ...VALID, oidc: { authority: VALID.oidc.authority } }],
    ["redirect_uri", { oidc: VALID.oidc, stepup_redirect_uri: VALID.stepup_redirect_uri, grafana: VALID.grafana }],
    ["stepup_redirect_uri", { oidc: VALID.oidc, redirect_uri: VALID.redirect_uri, grafana: VALID.grafana }],
    ["grafana.bias_dashboard_uid", { ...VALID, grafana: {} }],
    ["grafana.bias_dashboard_uid", { oidc: VALID.oidc, redirect_uri: VALID.redirect_uri, stepup_redirect_uri: VALID.stepup_redirect_uri, grafana: {} }],
  ])("rechaza un campo faltante: %s", (field, raw) => {
    expect(() => parseConfig(raw)).toThrowError(expect.objectContaining({ code: "missing", field }));
  });

  it("rechaza un campo desconocido, en la raiz y anidado", () => {
    expect(() => parseConfig({ ...VALID, extra: "x" })).toThrowError(expect.objectContaining({ code: "unknown", field: "extra" }));
    expect(() => parseConfig({ ...VALID, oidc: { ...VALID.oidc, secret: "x" } })).toThrowError(
      expect.objectContaining({ code: "unknown", field: "oidc.secret" }),
    );
  });

  it.each(Object.keys(TABLE))("rechaza la constante de tiempo %s", (name) => {
    expect(() => parseConfig({ ...VALID, [name]: 1 })).toThrowError(expect.objectContaining({ code: "constant", field: name }));
    expect(() => parseConfig({ ...VALID, oidc: { ...VALID.oidc, [name.toLowerCase()]: 1 } })).toThrowError(
      expect.objectContaining({ code: "constant" }),
    );
  });

  it("rechaza tipos invalidos", () => {
    expect(() => parseConfig(null)).toThrowError(expect.objectContaining({ code: "invalid" }));
    expect(() => parseConfig([])).toThrowError(expect.objectContaining({ code: "invalid" }));
    expect(() => parseConfig({ ...VALID, oidc: "x" })).toThrowError(expect.objectContaining({ code: "invalid", field: "oidc" }));
    expect(() => parseConfig({ ...VALID, redirect_uri: "" })).toThrowError(expect.objectContaining({ code: "invalid" }));
    expect(() => parseConfig({ ...VALID, grafana: { bias_dashboard_uid: 7 } })).toThrowError(expect.objectContaining({ code: "invalid" }));
  });

  it("carga /config.json con fetch", async () => {
    const calls: string[] = [];
    const fake = (async (url: string) => {
      calls.push(url);
      return new Response(JSON.stringify(VALID), { status: 200 });
    }) as unknown as typeof fetch;
    expect(await loadConfig(fake)).toEqual(VALID);
    expect(calls).toEqual(["/config.json"]);
  });

  it("falla si el fetch falla, si no es 2xx o si el cuerpo no es JSON", async () => {
    const boom = (async () => {
      throw new Error("red");
    }) as unknown as typeof fetch;
    const notFound = (async () => new Response("", { status: 404 })) as unknown as typeof fetch;
    const notJson = (async () => new Response("<html>", { status: 200 })) as unknown as typeof fetch;
    for (const fake of [boom, notFound, notJson]) {
      await expect(loadConfig(fake)).rejects.toThrowError(expect.objectContaining({ code: "unreadable" }));
    }
  });

  it("propaga el error de validacion al cargar un config.json con una constante", async () => {
    const withConstant = (async () =>
      new Response(JSON.stringify({ ...VALID, IDLE_LOGOUT_SECONDS: 1 }), { status: 200 })) as unknown as typeof fetch;
    await expect(loadConfig(withConstant)).rejects.toBeInstanceOf(ConfigError);
  });
});
