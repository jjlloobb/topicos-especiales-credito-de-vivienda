// `config.json` por entorno (INF-U10-03; domain-entities §4): solo OIDC y el `uid` de `bias.json`.
// Falla si falta un campo, si aparece uno desconocido o si trae una constante del codigo.
import { TIME_CONSTANTS } from "./constants";

export interface AppConfig {
  readonly oidc: { readonly authority: string; readonly client_id: string };
  readonly redirect_uri: string;
  readonly stepup_redirect_uri: string;
  readonly grafana: { readonly bias_dashboard_uid: string };
}

export class ConfigError extends Error {
  readonly code: "unreadable" | "missing" | "unknown" | "constant" | "invalid";
  readonly field: string;

  constructor(code: ConfigError["code"], field: string) {
    super(`${code}:${field}`);
    this.name = "ConfigError";
    this.code = code;
    this.field = field;
  }
}

const SCHEMA = {
  oidc: ["authority", "client_id"],
  redirect_uri: null,
  stepup_redirect_uri: null,
  grafana: ["bias_dashboard_uid"],
} as const;

const CONSTANT_NAMES: ReadonlySet<string> = new Set(Object.keys(TIME_CONSTANTS));

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertNoConstants(value: unknown, path: string): void {
  if (!isRecord(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (CONSTANT_NAMES.has(key.toUpperCase())) throw new ConfigError("constant", `${path}${key}`);
    assertNoConstants(child, `${path}${key}.`);
  }
}

function assertString(value: unknown, field: string): string {
  if (typeof value !== "string" || value === "") throw new ConfigError("invalid", field);
  return value;
}

function assertKeys(value: Record<string, unknown>, allowed: readonly string[], path: string): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) throw new ConfigError("unknown", `${path}${key}`);
  }
  for (const key of allowed) {
    if (!(key in value)) throw new ConfigError("missing", `${path}${key}`);
  }
}

function section(raw: Record<string, unknown>, name: "oidc" | "grafana"): Record<string, unknown> {
  const value = raw[name];
  if (!isRecord(value)) throw new ConfigError("invalid", name);
  assertKeys(value, SCHEMA[name], `${name}.`);
  return value;
}

/** Valida un `config.json` ya leido; devuelve la configuracion tipada o lanza `ConfigError`. */
export function parseConfig(raw: unknown): AppConfig {
  if (!isRecord(raw)) throw new ConfigError("invalid", "$");
  assertNoConstants(raw, "");
  assertKeys(raw, Object.keys(SCHEMA), "");
  const oidc = section(raw, "oidc");
  const grafana = section(raw, "grafana");
  return {
    oidc: {
      authority: assertString(oidc["authority"], "oidc.authority"),
      client_id: assertString(oidc["client_id"], "oidc.client_id"),
    },
    redirect_uri: assertString(raw["redirect_uri"], "redirect_uri"),
    stepup_redirect_uri: assertString(raw["stepup_redirect_uri"], "stepup_redirect_uri"),
    grafana: { bias_dashboard_uid: assertString(grafana["bias_dashboard_uid"], "grafana.bias_dashboard_uid") },
  };
}

/** Carga `/config.json` con `fetch` (el ConfigMap del chart lo monta junto a la SPA). */
export async function loadConfig(fetchImpl: typeof fetch = fetch, url = "/config.json"): Promise<AppConfig> {
  let raw: unknown;
  try {
    const response = await fetchImpl(url, { cache: "no-store" });
    if (!response.ok) throw new ConfigError("unreadable", url);
    raw = await response.json();
  } catch (error) {
    if (error instanceof ConfigError) throw error;
    throw new ConfigError("unreadable", url);
  }
  return parseConfig(raw);
}
