// P-U10-04; NFR-U10-33: el cliente de la API con el timeout de 10 s, el token en `Authorization` y ningun reintento.
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApi, createApiFetch, MfaRequiredError, request, TransportError, unwrap } from "../../../src/api/client";
import { getMe } from "../../../src/api/endpoints";
import { createQueryClient } from "../../../src/api/queryClient";
import { API_TIMEOUT_SECONDS } from "../../../src/config/constants";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

const problem = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/problem+json" } });
const ok = (body: unknown) => new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
const SESSION = { role: "analista", mfa: true, auth_time: "2026-11-12T15:00:00Z", locale: "es-CO" };

function api(fetchImpl: (r: Request) => Promise<Response>, token: string | null = "tok", mismatch = vi.fn()) {
  return {
    client: createApi({ baseUrl: "https://console.test", getToken: () => token, fetchImpl: fetchImpl as typeof fetch, onContractMismatch: mismatch }),
    mismatch,
  };
}

describe("la solicitud", () => {
  it("lleva el token en Authorization", async () => {
    const seen: Request[] = [];
    const { client } = api(async (r) => (seen.push(r), ok(SESSION)));
    expect(await getMe(client)).toEqual(SESSION);
    expect(seen[0]?.headers.get("authorization")).toBe("Bearer tok");
    expect(seen[0]?.url).toBe("https://console.test/api/console/me");
  });

  it("sin token no pone Authorization", async () => {
    const seen: Request[] = [];
    const { client } = api(async (r) => (seen.push(r), ok(SESSION)), null);
    await getMe(client);
    expect(seen[0]?.headers.has("authorization")).toBe(false);
  });

  it("el timeout de 10 s corta la solicitud", async () => {
    let signal: AbortSignal | undefined;
    const { client } = api((r) => {
      signal = r.signal;
      return new Promise<Response>((_resolve, reject) => r.signal.addEventListener("abort", () => reject(new Error("abort"))));
    });
    const pending = getMe(client).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_SECONDS * 1000 - 1);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const error = await pending;
    expect(error).toBeInstanceOf(TransportError);
    expect((error as TransportError).kind).toBe("timeout");
    expect(signal?.aborted).toBe(true);
  });

  it("un fallo de red es `network`, no `timeout`", async () => {
    const { client } = api(async () => Promise.reject(new TypeError("fetch failed")));
    const error = await getMe(client).catch((e: unknown) => e);
    expect((error as TransportError).kind).toBe("network");
  });

  it("un 503 produce UNA sola solicitud (sin reintento)", async () => {
    const calls: Request[] = [];
    const { client } = api(async (r) => (calls.push(r), problem(503, { code: "dependency_unavailable", correlation_id: "a".repeat(32) })));
    const error = await getMe(client).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).problem).toMatchObject({ code: "dependency_unavailable" });
    expect((error as ApiError).status).toBe(503);
    expect(calls).toHaveLength(1);
  });

  it("la API por omision usa el fetch global y el timeout de la constante", async () => {
    const seen: Request[] = [];
    vi.stubGlobal("fetch", async (r: Request) => (seen.push(r), ok(SESSION)));
    const wrapped = createApiFetch({ baseUrl: "https://console.test", getToken: () => null });
    expect((await wrapped("https://console.test/api/console/me")).status).toBe(200);
    expect(seen).toHaveLength(1);
    vi.unstubAllGlobals();
  });
});

describe("los errores llegan como Problem", () => {
  it("un 403 mfa_required es MfaRequiredError (se entrega a stepup)", async () => {
    const { client } = api(async () => problem(403, { code: "mfa_required", correlation_id: "b".repeat(32) }));
    const error = await getMe(client).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(MfaRequiredError);
    expect((error as MfaRequiredError).problem.code).toBe("mfa_required");
  });

  it("un 403 forbidden o un 409 con reason es un ApiError con code, reason y correlation_id", async () => {
    for (const [status, body] of [
      [403, { code: "forbidden", correlation_id: "c".repeat(32) }],
      [409, { code: "conflict_state", reason: "decision_already_recorded", correlation_id: "d".repeat(32) }],
    ] as const) {
      const { client } = api(async () => problem(status, body));
      const error = (await getMe(client).catch((e: unknown) => e)) as ApiError;
      expect(error).not.toBeInstanceOf(MfaRequiredError);
      expect(error.problem).toEqual({ code: body.code, reason: "reason" in body ? body.reason : undefined, correlation_id: body.correlation_id });
    }
  });

  it("un 422 conserva `invalid_params` (BR-U10-09: el error va en su campo); un nulo se omite", async () => {
    const invalid = [{ name: "justification", reason_code: "justification_length" }];
    const { client } = api(async () => problem(422, { code: "validation_error", correlation_id: "e".repeat(32), invalid_params: invalid }));
    const error = (await getMe(client).catch((e: unknown) => e)) as ApiError;
    expect(error.problem.invalid_params).toEqual(invalid);
    const { client: other } = api(async () => problem(422, { code: "validation_error", correlation_id: "e".repeat(32), invalid_params: null }));
    const second = (await getMe(other).catch((e: unknown) => e)) as ApiError;
    expect("invalid_params" in second.problem).toBe(false);
  });

  it("un error que no es un Problem es `internal_error` y avisa api_contract_mismatch", async () => {
    const { client, mismatch } = api(async () => new Response("<html>502</html>", { status: 502, headers: { "content-type": "text/html" } }));
    const error = (await getMe(client, mismatch).catch((e: unknown) => e)) as ApiError;
    expect(error.problem).toEqual({ code: "internal_error" });
    expect(mismatch).toHaveBeenCalled();
  });

  it("una 2xx que no es JSON es api_contract_mismatch", async () => {
    const { client } = api(async () => new Response("no es json", { status: 200, headers: { "content-type": "application/json" } }));
    const mismatch = vi.fn();
    const error = (await getMe(client, mismatch).catch((e: unknown) => e)) as ApiError;
    expect(error.problem).toEqual({ code: "internal_error" });
    expect(mismatch).toHaveBeenCalledOnce();
  });

  it("unwrap y request sin avisar al reporter por omision", async () => {
    expect(() => unwrap({ error: "x", response: new Response(null, { status: 500 }) }, () => undefined)).toThrow(ApiError);
    await expect(request(Promise.reject(new SyntaxError("json")))).rejects.toBeInstanceOf(ApiError);
    await expect(request(Promise.reject(new TransportError("timeout")))).rejects.toBeInstanceOf(TransportError);
  });
});

describe("TanStack Query sin reintentos ni refresco por foco", () => {
  it("la configuracion por omision", () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries).toMatchObject({ retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false });
    expect(defaults.mutations).toMatchObject({ retry: false });
  });

  it("una consulta que falla se pide una sola vez", async () => {
    const client: QueryClient = createQueryClient();
    const queryFn = vi.fn(async () => Promise.reject(new Error("503")));
    await client.fetchQuery({ queryKey: ["x"], queryFn }).catch(() => undefined);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(queryFn).toHaveBeenCalledOnce();
  });

  it("una mutacion que falla se envia una sola vez", async () => {
    const client = createQueryClient();
    const mutationFn = vi.fn(async () => Promise.reject(new Error("503")));
    await client.getMutationCache().build(client, { mutationFn }).execute(undefined).catch(() => undefined);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(mutationFn).toHaveBeenCalledOnce();
  });
});
