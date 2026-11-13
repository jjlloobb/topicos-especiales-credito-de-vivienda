// Los filtros de la bandeja (BR-U10-10; `CaseFilter` de U0) y su forma en la URL. Ningun filtro lleva datos del solicitante, asi que todos
// pueden ir en la URL; y la lectura de la URL es **estricta**: solo entran valores de un conjunto cerrado (estados, canales conocidos,
// fechas `AAAA-MM-DD`, un entero), de modo que ninguna clave ni valor puede venir de `applicant_display` ni de la solicitud. No hay busqueda
// por nombre (revision del FD de U10, A3).
import { CASE_STATES } from "@vectra/contracts";
import type { CaseQuery, CaseState } from "../../api/endpoints";

export const DEFAULT_STATES: readonly CaseState[] = CASE_STATES.filter((state) => state !== "vencido");
/** Los canales que se pueden filtrar: el de las solicitudes web y el del alta manual (C04, `create_manual_application`). */
export const KNOWN_CHANNELS = ["web", "manual"] as const;
export const PAGE_SIZE = 20;
const MAX_PAGE = 10_000;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface InboxFilter {
  /** `null`: los de por omision (todos menos `vencido`). */
  readonly states: readonly CaseState[] | null;
  readonly channel: string | null;
  readonly createdFrom: string | null;
  readonly createdTo: string | null;
  readonly frozenAfter: boolean;
  readonly page: number;
}

export const EMPTY_FILTER: InboxFilter = { states: null, channel: null, createdFrom: null, createdTo: null, frozenAfter: false, page: 1 };

const isDate = (value: string | null): value is string => value !== null && DATE.test(value) && !Number.isNaN(Date.parse(value));

export function parseFilter(params: URLSearchParams): InboxFilter {
  const wanted = params.getAll("state").filter((value): value is CaseState => (CASE_STATES as readonly string[]).includes(value));
  const channel = params.get("channel");
  const from = params.get("from");
  const to = params.get("to");
  const rawPage = params.get("page") ?? "1";
  const page = /^\d{1,5}$/.test(rawPage) ? parseInt(rawPage, 10) : 1;
  return {
    states: wanted.length === 0 ? null : CASE_STATES.filter((state) => wanted.includes(state)),
    channel: (KNOWN_CHANNELS as readonly string[]).includes(channel ?? "") ? channel : null,
    createdFrom: isDate(from) ? from : null,
    createdTo: isDate(to) ? to : null,
    frozenAfter: params.get("frozen") === "1",
    page: page >= 1 && page <= MAX_PAGE ? page : 1,
  };
}

export function toSearchParams(filter: InboxFilter): URLSearchParams {
  const params = new URLSearchParams();
  for (const state of filter.states ?? []) params.append("state", state);
  if (filter.channel !== null) params.set("channel", filter.channel);
  if (filter.createdFrom !== null) params.set("from", filter.createdFrom);
  if (filter.createdTo !== null) params.set("to", filter.createdTo);
  if (filter.frozenAfter) params.set("frozen", "1");
  if (filter.page > 1) params.set("page", String(filter.page));
  return params;
}

/** Los parametros de `GET /api/console/cases`: por omision, todos los estados menos `vencido`. Las fechas son del dia de Bogota (UTC-5). */
export function toQuery(filter: InboxFilter): CaseQuery {
  return {
    state: filter.states ?? DEFAULT_STATES,
    ...(filter.channel === null ? {} : { channel: filter.channel }),
    ...(filter.createdFrom === null ? {} : { created_from: `${filter.createdFrom}T00:00:00-05:00` }),
    ...(filter.createdTo === null ? {} : { created_to: `${filter.createdTo}T23:59:59-05:00` }),
    ...(filter.frozenAfter ? { model_frozen_after_recommendation: true } : {}),
    page: filter.page,
    page_size: PAGE_SIZE,
  };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** «Ir al caso»: un identificador de caso (UUID), que no es un dato personal. */
export function isCaseId(value: string): boolean {
  return UUID.test(value);
}
