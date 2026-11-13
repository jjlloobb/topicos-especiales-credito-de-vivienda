// P-U10-07: `createOidcBackend` sobre un `OidcClient` falso: `prompt=login`, `max_age=0`, `acr_values=mfa`, el `redirect_uri` del
// callback y un `nonce` en memoria; el canje exige `acr = mfa`.
import type { OidcClient, SigninResponse, StateStore } from "oidc-client-ts";
import { describe, expect, it, vi } from "vitest";
import { createOidcBackend } from "../../../src/stepup/oidc";

const CALLBACK = "https://console.test/stepup-callback";

function backendWith(response: Partial<SigninResponse> | Error) {
  const createSigninRequest = vi.fn(async (_args: unknown) => ({ url: "https://console.test/auth?x=1", state: { id: "s-1" } }));
  const processSigninResponse = vi.fn(async (_url: string) => {
    if (response instanceof Error) throw response;
    return response as SigninResponse;
  });
  const remove = vi.fn(async (_key: string) => null);
  const accepted: SigninResponse[] = [];
  const backend = createOidcBackend(
    { createSigninRequest, processSigninResponse } as unknown as OidcClient,
    { remove } as unknown as StateStore,
    CALLBACK,
    (r) => accepted.push(r),
  );
  return { backend, createSigninRequest, processSigninResponse, remove, accepted };
}

describe("createOidcBackend", () => {
  it("createRequest pide prompt=login, max_age=0, acr_values=mfa, el redirect del callback y un nonce", async () => {
    const { backend, createSigninRequest } = backendWith({});
    expect(await backend.createRequest()).toEqual({ url: "https://console.test/auth?x=1", id: "s-1" });
    const args = createSigninRequest.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(args).toMatchObject({ redirect_uri: CALLBACK, prompt: "login", max_age: 0, acr_values: "mfa" });
    expect(args["nonce"]).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("un canje con acr = mfa entrega los tokens", async () => {
    const response = { profile: { acr: "mfa" } } as unknown as SigninResponse;
    const { backend, accepted, processSigninResponse } = backendWith(response);
    expect(await backend.exchange(`${CALLBACK}?code=c&state=s`)).toBe("ok");
    expect(processSigninResponse).toHaveBeenCalledWith(`${CALLBACK}?code=c&state=s`);
    expect(accepted).toEqual([response]);
  });

  it("un canje sin acr = mfa no entrega nada", async () => {
    const { backend, accepted } = backendWith({ profile: { acr: "pwd" } } as unknown as SigninResponse);
    expect(await backend.exchange(CALLBACK)).toBe("no_mfa");
    expect(accepted).toEqual([]);
  });

  it("un canje que lanza (state, nonce o codigo invalidos) es `failed`", async () => {
    const { backend, accepted } = backendWith(new Error("nonce"));
    expect(await backend.exchange(CALLBACK)).toBe("failed");
    expect(accepted).toEqual([]);
  });

  it("removeState borra ese intento del stateStore", async () => {
    const { backend, remove } = backendWith({});
    await backend.removeState("s-1");
    expect(remove).toHaveBeenCalledWith("s-1");
  });
});
