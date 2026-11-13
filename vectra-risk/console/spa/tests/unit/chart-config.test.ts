// El `config.json` que rinde el chart de `console-spa` pasa por el `parseConfig` REAL de la SPA (Paso 18; INF-U10-03; C-3). Un chart que renderiza bien no prueba que la SPA
// arranque: con una clave de mas o de menos `parseConfig` lanza `ConfigError` y la pantalla queda en blanco.
// `VECTRA_CHART_RENDER` es el directorio con un render por entorno (`<dir>/kind`, `<dir>/staging`, `<dir>/prod`, cada uno con el YAML de `helm template`): el target
// `make -C console policy-chart` los deja en `platform/.tools/integration/u10/spa`. Sin la variable, o sin los tres archivos, la prueba FALLA; no se salta.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { TIME_CONSTANTS } from "../../src/config/constants";
import { ConfigError, parseConfig } from "../../src/config/load";

const ENVS = ["kind", "staging", "prod"] as const;

function renderDirectory(): string {
  const dir = process.env["VECTRA_CHART_RENDER"];
  if (dir === undefined || dir === "") {
    throw new Error("falta VECTRA_CHART_RENDER: corre `make -C console policy-chart` o apunta al render de console/chart/spa (no se salta)");
  }
  return dir;
}

function renderedConfig(env: string): { text: string; json: Record<string, unknown> } {
  const folder = join(renderDirectory(), env);
  const files = readdirSync(folder).filter((name) => name.endsWith(".yaml"));
  if (files.length === 0) throw new Error(`sin render de ${env} en ${folder}`);
  const documents = files.flatMap((name) => readFileSync(join(folder, name), "utf-8").split(/^---$/m).map((doc) => parse(doc) as unknown));
  const maps = documents.filter(
    (doc): doc is { kind: string; metadata: { name: string }; data: Record<string, string> } =>
      typeof doc === "object" && doc !== null && (doc as { kind?: string }).kind === "ConfigMap",
  );
  const map = maps.find((m) => m.metadata.name === "console-spa-config");
  if (map === undefined) throw new Error(`el render de ${env} no trae el ConfigMap console-spa-config`);
  const text = map.data["config.json"];
  if (text === undefined) throw new Error(`el ConfigMap de ${env} no trae config.json`);
  return { text, json: JSON.parse(text) as Record<string, unknown> };
}

function code(run: () => unknown): ConfigError["code"] | "none" {
  try {
    run();
    return "none";
  } catch (error) {
    if (error instanceof ConfigError) return error.code;
    throw error;
  }
}

describe("el config.json que rinde el chart pasa por el parseConfig real", () => {
  it.each(ENVS)("%s: no lanza y trae el authority y los dos redirect_uri del entorno", (env) => {
    const { json } = renderedConfig(env);
    const config = parseConfig(json);
    expect(config.oidc.client_id).toBe("vectra-console");
    expect(new URL(config.oidc.authority).pathname).toBe("/auth/realms/vectra");
    const origin = new URL(config.oidc.authority).origin;
    expect(new URL(config.redirect_uri)).toMatchObject({ origin, pathname: "/callback" });
    expect(new URL(config.stepup_redirect_uri)).toMatchObject({ origin, pathname: "/stepup-callback" });
  });

  it.each(ENVS)("%s: las claves son exactamente las del esquema y ninguna constante de tiempo", (env) => {
    const { json } = renderedConfig(env);
    expect(Object.keys(json).sort()).toEqual(["grafana", "oidc", "redirect_uri", "stepup_redirect_uri"]);
    expect(Object.keys(json["oidc"] as object).sort()).toEqual(["authority", "client_id"]);
    expect(Object.keys(json["grafana"] as object)).toEqual(["bias_dashboard_uid"]);
    const names = JSON.stringify(json).toUpperCase();
    for (const constant of Object.keys(TIME_CONSTANTS)) expect(names).not.toContain(`"${constant}"`);
  });

  it.each(ENVS)("%s: con una clave de mas lanza unknown, con una de menos missing y con una constante constant", (env) => {
    const { json } = renderedConfig(env);
    expect(code(() => parseConfig({ ...json, extra: 1 }))).toBe("unknown");
    expect(code(() => parseConfig({ ...json, oidc: { ...(json["oidc"] as object), scope: "openid" } }))).toBe("unknown");
    const { grafana: _grafana, ...withoutGrafana } = json;
    expect(code(() => parseConfig(withoutGrafana))).toBe("missing");
    expect(code(() => parseConfig({ ...json, oidc: { authority: (json["oidc"] as { authority: string }).authority } }))).toBe("missing");
    expect(code(() => parseConfig({ ...json, version_poll_seconds: 60 }))).toBe("constant");
    expect(code(() => parseConfig({ ...json, oidc: { ...(json["oidc"] as object), STEPUP_TIMEOUT_SECONDS: 5 } }))).toBe("constant");
  });

  it("falla, y no se salta, sin VECTRA_CHART_RENDER o con un directorio sin render", () => {
    const saved = process.env["VECTRA_CHART_RENDER"];
    try {
      delete process.env["VECTRA_CHART_RENDER"];
      expect(() => renderedConfig("kind")).toThrow(/VECTRA_CHART_RENDER/);
      process.env["VECTRA_CHART_RENDER"] = join(process.cwd(), "no-existe");
      expect(() => renderedConfig("kind")).toThrow();
    } finally {
      if (saved !== undefined) process.env["VECTRA_CHART_RENDER"] = saved;
    }
  });
});
