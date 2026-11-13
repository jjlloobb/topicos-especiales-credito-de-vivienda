// Los endpoints del BFF que usa la SPA: `get_me` y `report_client_error` (U10-T03) y los de las vistas que entran en U10-T04 (casos,
// modelos y congelamientos). Cada funcion devuelve el cuerpo tipado con `contracts/ts` o lanza `ApiError`/`MfaRequiredError`/`TransportError`.
import type { components, paths } from "@vectra/contracts/src/generated/console-bff";
import { type ApiClient, request } from "./client";

type Schemas = components["schemas"];

export type SessionInfo = NonNullable<paths["/api/console/me"]["get"]["responses"]["200"]["content"]["application/json"]>;
export type ClientErrorReport = NonNullable<paths["/api/console/client-errors"]["post"]["requestBody"]>["content"]["application/json"];

export type CaseState = Schemas["CaseState"];
export type CaseSummary = Schemas["CaseSummary"];
export type CaseDetail = Schemas["CaseDetail"];
export type CasePage = Schemas["Page_CaseSummary_"];
export type DecisionIn = Schemas["DecisionIn"];
export type DecisionRef = Schemas["DecisionRef"];
export type ModelVersion = Schemas["ModelVersion"];
export type ModelVersionDetail = Schemas["ModelVersionDetail"];
export type ModelPage = Schemas["Page_ModelVersion_"];
export type FreezeSummary = Schemas["FreezeSummary"];
export type FreezeRecord = Schemas["FreezeRecord"];
export type FrozenResolutionIn = Schemas["FrozenResolutionIn"];
export type DisparityResult = Schemas["DisparityResult"];
export type AttributeResult = Schemas["AttributeResult"];

/** Los filtros de la bandeja que van al BFF (`CaseFilter` de U0): ninguno lleva datos del solicitante. */
export interface CaseQuery {
  readonly state?: readonly CaseState[];
  readonly channel?: string;
  readonly created_from?: string;
  readonly created_to?: string;
  readonly model_frozen_after_recommendation?: boolean;
  readonly page?: number;
  readonly page_size?: number;
}

export async function getMe(api: ApiClient, onContractMismatch?: () => void): Promise<SessionInfo> {
  return request(api.GET("/api/console/me"), onContractMismatch);
}

export async function listCases(api: ApiClient, query: CaseQuery): Promise<CasePage> {
  const { state, ...rest } = query;
  return request(api.GET("/api/console/cases", { params: { query: { ...rest, ...(state === undefined ? {} : { state: [...state] }) } } }));
}

export async function getCase(api: ApiClient, caseId: string): Promise<CaseDetail> {
  return request(api.GET("/api/console/cases/{id}", { params: { path: { id: caseId } } }));
}

/** `record_explanation_view` (BR-U10-08): solo con rol `analista`; responde 204. */
export async function recordExplanationView(api: ApiClient, caseId: string): Promise<void> {
  await request(api.POST("/api/console/cases/{id}/explanation-views", { params: { path: { id: caseId } } }));
}

export async function recordDecision(api: ApiClient, caseId: string, body: DecisionIn): Promise<DecisionRef> {
  return request(api.POST("/api/console/cases/{id}/decision", { params: { path: { id: caseId } }, body }));
}

export async function listModels(api: ApiClient): Promise<ModelPage> {
  return request(api.GET("/api/console/models", { params: { query: { page_size: 100 } } }));
}

export async function getModel(api: ApiClient, modelId: string): Promise<ModelVersionDetail> {
  return request(api.GET("/api/console/models/{id}", { params: { path: { id: modelId } } }));
}

export async function listFreezes(api: ApiClient): Promise<FreezeSummary[]> {
  return request(api.GET("/api/console/freezes"));
}

export async function getFreeze(api: ApiClient, freezeId: string): Promise<FreezeRecord> {
  return request(api.GET("/api/console/freezes/{id}", { params: { path: { id: freezeId } } }));
}

/** `resolve_frozen` (BR-U10-13): con MFA; un 403 `mfa_required` lo atiende `stepup`. */
export async function resolveFrozen(api: ApiClient, modelVersionId: string, body: FrozenResolutionIn): Promise<void> {
  await request(api.POST("/api/console/models/{id}/frozen-resolution", { params: { path: { id: modelVersionId } }, body }));
}
