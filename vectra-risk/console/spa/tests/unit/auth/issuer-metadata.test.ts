// @vitest-environment jsdom
// U10-T06 (CA-2): los endpoints del emisor salen de un solo sitio (`issuerMetadata`) y coinciden con las rutas de `/auth` que publica el
// gateway (`identity-edge/gateway/routes.yaml`, solo lectura). Cambiar una ruta de `ENDPOINT_PATHS` sin cambiar el gateway (o al reves) rompe esta prueba.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { describe, expect, it } from "vitest";
import { ENDPOINT_PATHS, issuerMetadata } from "../../../src/auth/issuer-metadata";
import { createUserManager } from "../../../src/auth/manager";

const ROUTES_YAML = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "..", "identity-edge", "gateway", "routes.yaml");
const AUTHORITY = "https://vectra.example/auth/realms/vectra";
const REALM_PATH = "/auth/realms/vectra";

interface Gateway {
  rate_limits: { name: string; path: { type: string; value: string } }[];
  routes: { name: string; matches?: { type: string; path: string }[] }[];
}
const gateway = parse(readFileSync(ROUTES_YAML, "utf-8")) as Gateway;
const authMatches = gateway.routes.find((route) => route.name === "auth")?.matches ?? [];
const exactAuthPaths = authMatches.filter((match) => match.type === "Exact").map((match) => match.path);
const limiterRegex = (name: string): RegExp => new RegExp(gateway.rate_limits.find((limit) => limit.name === name)?.path.value ?? "(?!)");

describe("issuerMetadata", () => {
  it("deriva los endpoints del emisor de config.json y no incluye endpoints que la SPA no usa", () => {
    expect(issuerMetadata(AUTHORITY)).toEqual({
      issuer: AUTHORITY,
      authorization_endpoint: `${AUTHORITY}/protocol/openid-connect/auth`,
      token_endpoint: `${AUTHORITY}/protocol/openid-connect/token`,
      end_session_endpoint: `${AUTHORITY}/protocol/openid-connect/logout`,
    });
    expect(issuerMetadata(`${AUTHORITY}/`)).toEqual(issuerMetadata(AUTHORITY)); // una barra final no duplica la barra
  });

  it("el UserManager del login usa esos metadatos (no hay descubrimiento)", () => {
    const config = { oidc: { authority: AUTHORITY, client_id: "c" }, redirect_uri: "https://x/callback", stepup_redirect_uri: "https://x/s", grafana: { bias_dashboard_uid: "b" } };
    const manager = createUserManager(config, "https://x", sessionStorage);
    expect(manager.settings.metadata).toEqual(issuerMetadata(AUTHORITY));
    manager.stopSilentRenew();
  });

  it("cada endpoint esta publicado por el gateway: auth, token y logout en la ruta `auth` (Exact) y auth/token con su limite de tasa", () => {
    for (const path of Object.values(ENDPOINT_PATHS)) expect(exactAuthPaths, path).toContain(`${REALM_PATH}${path}`);
    expect(limiterRegex("auth-login").test(`${REALM_PATH}${ENDPOINT_PATHS.authorization}?client_id=x`)).toBe(true);
    expect(limiterRegex("auth-token").test(`${REALM_PATH}${ENDPOINT_PATHS.token}`)).toBe(true);
  });
});
