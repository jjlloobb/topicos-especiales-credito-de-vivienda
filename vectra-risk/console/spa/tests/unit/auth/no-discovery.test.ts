// @vitest-environment jsdom
// U10-T06: el step-up (el `OidcClient` de `wiring.ts`) tampoco depende del documento de descubrimiento OIDC. El realm de kind responde 500 a
// `.well-known/openid-configuration` (Keycloak 26.8.1, `Duplicate key 2`; defecto conocido de U2): el emisor de esta prueba lo falla y cuenta las
// peticiones. El login, la recarga y el logout con el mismo defecto estan en `session.test.tsx`.
import type { UserManager } from "oidc-client-ts";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AppConfig } from "../../../src/config/load";
import { createWiring } from "../../../src/wiring";

const ORIGIN = window.location.origin;
const AUTHORITY = `${ORIGIN}/auth/realms/vectra`;
const CONFIG: AppConfig = {
  oidc: { authority: AUTHORITY, client_id: "vectra-console" },
  redirect_uri: `${ORIGIN}/callback`,
  stepup_redirect_uri: `${ORIGIN}/stepup-callback`,
  grafana: { bias_dashboard_uid: "bias" },
};

const b64 = (value: unknown): string => btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
const jwt = (claims: Record<string, unknown>): string => `${b64({ alg: "RS256", kid: "k1" })}.${b64(claims)}.firma`;

afterEach(() => vi.unstubAllGlobals());

describe("step-up con el descubrimiento OIDC respondiendo 500", () => {
  it("pide la autorizacion y canjea el codigo sin pedir `.well-known/openid-configuration`", async () => {
    const urls: string[] = [];
    let nonce = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input instanceof Request ? input.url : input);
        urls.push(url);
        if (url.includes(".well-known")) return new Response("boom", { status: 500 });
        const now = Math.floor(Date.now() / 1000);
        const claims = { iss: AUTHORITY, sub: "analista", aud: "vectra-console", exp: now + 300, iat: now, auth_time: now, acr: "mfa", nonce };
        return new Response(JSON.stringify({ access_token: "access-mfa", token_type: "Bearer", expires_in: 300, scope: "openid", id_token: jwt(claims) }), {
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const wiring = createWiring(CONFIG, window);
    const request = await wiring.stepUpEnv.backend.createRequest();
    const authorize = new URL(request.url);
    expect(authorize.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/auth");
    expect(authorize.searchParams.get("prompt")).toBe("login");
    expect(authorize.searchParams.get("max_age")).toBe("0");
    expect(authorize.searchParams.get("acr_values")).toBe("mfa");
    expect(authorize.searchParams.get("code_challenge_method")).toBe("S256");
    nonce = authorize.searchParams.get("nonce") as string;

    expect(await wiring.stepUpEnv.backend.exchange(`${CONFIG.stepup_redirect_uri}?code=c&state=${request.id}`)).toBe("ok");
    expect(urls).toEqual([`${AUTHORITY}/protocol/openid-connect/token`]); // solo el canje; ni descubrimiento ni jwks
    (wiring.manager as unknown as UserManager).stopSilentRenew();
  });
});
