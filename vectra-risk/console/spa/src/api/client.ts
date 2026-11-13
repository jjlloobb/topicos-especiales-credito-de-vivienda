// Cliente de la API del BFF (P-U10-04; NFR-U10-33): `createClient<paths>` de `@vectra/contracts` (openapi-fetch) con los tipos de
// `contracts/ts/src/generated/console-bff.d.ts`. Timeout de `API_TIMEOUT_SECONDS` por solicitud, el token en `Authorization`, y
// **ningun reintento** (el BFF no reintenta y la SPA tampoco; el unico reintento es el del step-up).
import { createClient } from "@vectra/contracts";
import type { paths } from "@vectra/contracts/src/generated/console-bff";
import { API_TIMEOUT_SECONDS } from "../config/constants";
import type { Problem } from "../i18n";

export type ApiClient = ReturnType<typeof createClient<paths>>;

/** Un error de la API que llega a quien llamo como `Problem` (`code`, `reason?`, `correlation_id`). */
export class ApiError extends Error {
  readonly problem: Problem;
  readonly status: number;

  constructor(problem: Problem, status: number) {
    super(problem.code);
    this.name = "ApiError";
    this.problem = problem;
    this.status = status;
  }
}

/** 403 con `code = mfa_required`: no es un error para mostrar, es la senal para `stepup`. */
export class MfaRequiredError extends ApiError {}

/** Fallo de transporte: `timeout` (10 s) o `network`. */
export class TransportError extends Error {
  readonly kind: "timeout" | "network";

  constructor(kind: "timeout" | "network") {
    super(kind);
    this.name = "TransportError";
    this.kind = kind;
  }
}

export interface ApiDeps {
  readonly baseUrl: string;
  readonly getToken: () => string | null;
  readonly fetchImpl?: typeof fetch;
  readonly timeoutMs?: number;
  /** Una respuesta que no respeta el contrato (2xx que no es JSON, error que no es `Problem`): `api_contract_mismatch` (P-3). */
  readonly onContractMismatch?: () => void;
}

function isProblem(value: unknown): value is Problem {
  return typeof value === "object" && value !== null && typeof (value as { code?: unknown }).code === "string";
}

/** `fetch` con el token, el timeout y sin reintentos. `openapi-fetch` le entrega un `Request`. */
export function createApiFetch(deps: ApiDeps): typeof fetch {
  const base = deps.fetchImpl ?? fetch;
  const timeoutMs = deps.timeoutMs ?? API_TIMEOUT_SECONDS * 1000;
  return async (input, init) => {
    const request = new Request(input, init);
    const headers = new Headers(request.headers);
    const token = deps.getToken();
    if (token !== null) headers.set("authorization", `Bearer ${token}`);
    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);
    try {
      return await base(new Request(request, { headers, signal: controller.signal }));
    } catch {
      throw new TransportError(controller.signal.aborted ? "timeout" : "network");
    } finally {
      clearTimeout(timer);
    }
  };
}

export function createApi(deps: ApiDeps): ApiClient {
  return createClient<paths>({ baseUrl: deps.baseUrl, fetch: createApiFetch(deps) });
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/**
 * Resuelve la respuesta de `openapi-fetch`: el cuerpo en exito, o lanza `MfaRequiredError` (403 `mfa_required`), `ApiError` (un
 * `Problem`) o `ApiError` con `code = internal_error` si el error no es un `Problem` (y avisa al `reporter`).
 */
export function unwrap<T>(result: Result<T>, onContractMismatch: () => void): T {
  const { data, error, response } = result;
  if (error === undefined) return data as T;
  if (!isProblem(error)) {
    onContractMismatch();
    throw new ApiError({ code: "internal_error" }, response.status);
  }
  const problem: Problem = { code: error.code, reason: error.reason, correlation_id: error.correlation_id };
  if (response.status === 403 && problem.code === "mfa_required") throw new MfaRequiredError(problem, 403);
  throw new ApiError(problem, response.status);
}

/**
 * Espera una llamada del cliente y la resuelve con `unwrap`. Un fallo de transporte (`TransportError`) pasa tal cual; una 2xx cuyo
 * cuerpo no es JSON (la libreria lanza al leerlo) es `api_contract_mismatch`.
 */
export async function request<T>(call: Promise<Result<T>>, onContractMismatch: () => void = () => undefined): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (error) {
    if (error instanceof TransportError) throw error;
    onContractMismatch();
    throw new ApiError({ code: "internal_error" }, 0);
  }
  return unwrap(result, onContractMismatch);
}
