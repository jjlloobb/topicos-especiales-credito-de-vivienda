// Textos y formatos (BR-U10-17, 18; NFR-U10-53). Todo texto visible sale de los catalogos `messages.<idioma>.json` y `labels.<idioma>.json`
// (espanol e ingles, con las mismas claves: `tests/unit/i18n/catalog-parity.test.ts`), y las fechas y los numeros se formatean con `Intl` en
// el `locale` del idioma en curso (`language.ts`). Los catalogos en espanol dan los tipos de las claves.
import labelsEn from "./labels.en.json";
import labelsEs from "./labels.es.json";
import { getLanguage, type Language, LOCALES } from "./language";
import messagesEn from "./messages.en.json";
import messagesEs from "./messages.es.json";

const TIME_ZONE = "America/Bogota";

type Messages = typeof messagesEs;
type Labels = typeof labelsEs;
export type UiKey = keyof Messages["ui"];
export type NoticeKey = keyof Messages["notice"];
export type LabelGroup = keyof Labels;

const MESSAGES: Readonly<Record<Language, Messages>> = { es: messagesEs, en: messagesEn };
const LABELS: Readonly<Record<Language, Labels>> = { es: labelsEs, en: labelsEn };

const messagesNow = (): Messages => MESSAGES[getLanguage()];
const labelsNow = (): Labels => LABELS[getLanguage()];
const locale = (): string => LOCALES[getLanguage()];

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
  return fill(messagesNow().ui[key], params);
}

export function notice(key: NoticeKey): string {
  return messagesNow().notice[key];
}

/** El texto de un valor de enumerado (`labels.<idioma>.json`). */
export function label<G extends LabelGroup>(group: G, value: keyof Labels[G] & string): string {
  return (labelsNow()[group] as Record<string, string>)[value] ?? messagesNow().ui.unknown_value;
}

/**
 * El mensaje de un `Problem`: el de su `reason` si lo hay y el catalogo lo conoce, si no el de su `code`; un `code` desconocido da el
 * mensaje generico con el `correlation_id` para soporte.
 */
export function problemText(problem: Problem): string {
  const messages = messagesNow();
  const byReason = problem.reason == null ? undefined : (messages.reason as Record<string, string>)[problem.reason];
  const byCode = (messages.code as Record<string, string>)[problem.code];
  return byReason ?? byCode ?? fill(messages.generic, { correlation_id: problem.correlation_id ?? "" });
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE }).format(new Date(iso));
}

const DECIMAL = /^-?\d+(\.\d+)?$/;

/**
 * Formatea un decimal que llega como cadena (`Decimal4`) con `Intl`, sin pasar por `Number(` ni `parseFloat` (NFR-U0-34):
 * `Intl.NumberFormat.prototype.format` acepta la cadena decimal.
 */
export function formatDecimal(value: string, digits = 4): string {
  if (!DECIMAL.test(value)) throw new RangeError(`no es un decimal: ${value}`);
  const format = new Intl.NumberFormat(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return format.format(value as `${number}`);
}

/** Pesos colombianos sin decimales, con `Intl` (los montos de la solicitud son enteros): «$ 1.500.000» en espanol, «COP 1,500,000» en ingles. */
export function formatMoney(value: number): string {
  return new Intl.NumberFormat(locale(), { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(value);
}

/** Un conteo entero (casos, paginas) con los separadores del idioma. */
export function formatCount(value: number): string {
  return new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 }).format(value);
}

/** El texto de un canal: el catalogo lo conoce para los filtrables; cualquier otro se muestra tal cual (es un codigo, no un dato personal). */
export function channelText(channel: string): string {
  return (labelsNow().CHANNELS as Record<string, string>)[channel] ?? channel;
}

/** `formatDecimal` para un valor que llega del servidor: si no es un decimal se muestra tal cual (texto), en vez de romper la pantalla. */
export function safeDecimal(value: string, digits = 4): string {
  return DECIMAL.test(value) ? formatDecimal(value, digits) : value;
}

/** Un dia `AAAA-MM-DD` del servidor (sin hora): se formatea en UTC para que no se corra al dia anterior por la zona horaria. */
export function formatDay(day: string): string {
  return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeZone: "UTC" }).format(new Date(day));
}

/** Como `label`, pero un valor que el catalogo no conoce se muestra tal cual (llega dentro de un `JsonValue`, sin tipo). */
export function labelOrRaw(group: LabelGroup, value: string): string {
  return (labelsNow()[group] as Record<string, string>)[value] ?? value;
}
