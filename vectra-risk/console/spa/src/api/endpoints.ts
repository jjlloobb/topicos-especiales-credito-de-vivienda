// Los endpoints que usa esta mitad del Bloque E: `get_me` y `report_client_error`. Los demas los agrega U10-T04 con cada vista.
import type { paths } from "@vectra/contracts/src/generated/console-bff";
import { type ApiClient, request } from "./client";

export type SessionInfo = NonNullable<
  paths["/api/console/me"]["get"]["responses"]["200"]["content"]["application/json"]
>;
export type ClientErrorReport = NonNullable<
  paths["/api/console/client-errors"]["post"]["requestBody"]
>["content"]["application/json"];

export async function getMe(api: ApiClient, onContractMismatch?: () => void): Promise<SessionInfo> {
  return request(api.GET("/api/console/me"), onContractMismatch);
}
