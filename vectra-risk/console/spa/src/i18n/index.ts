// Textos y formatos (BR-U10-17, 18; NFR-U10-53). Todo texto visible sale de `messages.es.json` y `labels.es.json`.
import labels from "./labels.es.json";
import messages from "./messages.es.json";

export const LOCALE = "es-CO";
const TIME_ZONE = "America/Bogota";

export type UiKey = keyof typeof messages.ui;
export type NoticeKey = keyof typeof messages.notice;
export type LabelGroup = keyof typeof labels;

/** El `Problem` de U0 §6 sin `detail`: el `detail` del servidor nunca se muestra (BR-U10-17). */
export interface Problem {
  readonly code: string;
  readonly reason?: string | null | undefined;
  readonly correlation_id?: string | null | undefined;
  /** Los campos que el servidor rechazo (un 422): la vista los muestra en su campo (BR-U10-09). */
  readonly invalid_params?: readonly { readonly name: string; readonly reason_code: string }[] | null | undefined;
}

export function fill(text: string, params: Readonly<Record<string, string>> = {}): string {
  return text.replace(/\{(\w+)\}/g, (_, name: string) => params[name] ?? "");
}

export function ui(key: UiKey, params?: Readonly<Record<string, string>>): string {
  return fill(messages.ui[key], params);
}

export function notice(key: NoticeKey): string {
  return messages.notice[key];
}

/** El texto de un valor de enumerado (`labels.es.json`). */
export function label<G extends LabelGroup>(group: G, value: keyof (typeof labels)[G] & string): string {
  return (labels[group] as Record<string, string>)[value] ?? messages.ui.unknown_value;
}

/**
 * El mensaje de un `Problem`: el de su `reason` si lo hay y el catalogo lo conoce, si no el de su `code`; un `code` desconocido da el
 * mensaje generico con el `correlation_id` para soporte.
 */
export function problemText(problem: Problem): string {
  const byReason = problem.reason == null ? undefined : (messages.reason as Record<string, string>)[problem.reason];
  const byCode = (messages.code as Record<string, string>)[problem.code];
  return byReason ?? byCode ?? fill(messages.generic, { correlation_id: problem.correlation_id ?? "" });
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE }).format(new Date(iso));
}

const DECIMAL = /^-?\d+(\.\d+)?$/;

/**
 * Formatea un decimal que llega como cadena (`Decimal4`) con `Intl`, sin pasar por `Number(` ni `parseFloat` (NFR-U0-34):
 * `Intl.NumberFormat.prototype.format` acepta la cadena decimal.
 */
export function formatDecimal(value: string, digits = 4): string {
  if (!DECIMAL.test(value)) throw new RangeError(`no es un decimal: ${value}`);
  const format = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return format.format(value as `${number}`);
}

/** Pesos colombianos sin decimales, con `Intl` (los montos de la solicitud son enteros). */
export function formatMoney(value: number): string {
  return new Intl.NumberFormat(LOCALE, { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(value);
}

/** El texto de un canal: el catalogo lo conoce para los filtrables; cualquier otro se muestra tal cual (es un codigo, no un dato personal). */
export function channelText(channel: string): string {
  return (labels.CHANNELS as Record<string, string>)[channel] ?? channel;
}

/** `formatDecimal` para un valor que llega del servidor: si no es un decimal se muestra tal cual (texto), en vez de romper la pantalla. */
export function safeDecimal(value: string, digits = 4): string {
  return DECIMAL.test(value) ? formatDecimal(value, digits) : value;
}

/** Un dia `AAAA-MM-DD` del servidor (sin hora): se formatea en UTC para que no se corra al dia anterior por la zona horaria. */
export function formatDay(day: string): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(day));
}

/** Como `label`, pero un valor que el catalogo no conoce se muestra tal cual (llega dentro de un `JsonValue`, sin tipo). */
export function labelOrRaw(group: LabelGroup, value: string): string {
  return (labels[group] as Record<string, string>)[value] ?? value;
}
