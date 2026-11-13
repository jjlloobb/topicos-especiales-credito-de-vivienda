// BR-U10-06; P-U10-07; NFR-U10-61: el nucleo puro del step-up, rama por rama. PBT-U10-05 lo recorre con secuencias (tests/property).
import { describe, expect, it } from "vitest";
import { type StepUpEvent, type StepUpState, busy, IDLE, parseMessage, step } from "../../../src/stepup/machine";

const OWN = "https://console.test";
type B = { justification: string };
const BODY: B = { justification: "porque si" };
const msg = (over: Partial<Extract<StepUpEvent<B>, { type: "message" }>> = {}): StepUpEvent<B> => ({
  type: "message",
  origin: OWN,
  fromPopup: true,
  data: { code: "c", state: "s1" },
  ...over,
});
const run = (state: StepUpState<B>, event: StepUpEvent<B>) => step(state, event, OWN);

const opening: StepUpState<B> = { phase: "opening", body: BODY };
const waiting: StepUpState<B> = { phase: "waiting", body: BODY, expected: "s1" };
const exchanging: StepUpState<B> = { phase: "exchanging", body: BODY };
const sending: StepUpState<B> = { phase: "sending", body: BODY };

describe("start", () => {
  it("desde idle, con ventana: abre, crea la solicitud y vigila", () => {
    expect(run(IDLE, { type: "start", body: BODY, opened: true })).toEqual({
      state: opening,
      effects: [{ type: "create_request" }, { type: "watch" }],
    });
  });

  it("ventana bloqueada: falla `blocked` sin crear nada", () => {
    expect(run(IDLE, { type: "start", body: BODY, opened: false })).toEqual({
      state: { phase: "failed", failure: "blocked" },
      effects: [{ type: "finish", outcome: "blocked" }],
    });
  });

  it.each([opening, waiting, exchanging, sending])("con un intento en curso (%o) se ignora", (state) => {
    expect(run(state, { type: "start", body: { justification: "otra" }, opened: true })).toEqual({ state, effects: [] });
  });

  it.each([{ phase: "done" } as const, { phase: "failed", failure: "closed" } as const])(
    "tras un intento terminado (%o) empieza otro",
    (state) => {
      expect(run(state, { type: "start", body: BODY, opened: true }).state).toEqual(opening);
    },
  );
});

describe("request_ready y request_failed", () => {
  it("la solicitud lista deja esperando el mensaje con ese state", () => {
    expect(run(opening, { type: "request_ready", state: "s1" })).toEqual({ state: waiting, effects: [] });
  });
  it("fuera de `opening` se ignora", () => {
    expect(run(IDLE, { type: "request_ready", state: "s1" }).state).toEqual(IDLE);
    expect(run(IDLE, { type: "request_failed" }).state).toEqual(IDLE);
  });
  it("la solicitud que falla termina el intento", () => {
    expect(run(opening, { type: "request_failed" })).toEqual({
      state: { phase: "failed", failure: "request" },
      effects: [{ type: "finish", outcome: "request" }],
    });
  });
});

describe("message", () => {
  it("origen propio, ventana abierta y state igual: canjea", () => {
    expect(run(waiting, msg())).toEqual({
      state: exchanging,
      effects: [{ type: "exchange", code: "c", state: "s1" }],
    });
  });
  it.each([
    ["otro origen", msg({ origin: "https://evil.test" })],
    ["otra ventana", msg({ fromPopup: false })],
    ["otro state", msg({ data: { code: "c", state: "otro" } })],
    ["sin forma de mensaje", msg({ data: "hola" })],
  ])("%s: se ignora sin canje", (_name, event) => {
    expect(run(waiting, event)).toEqual({ state: waiting, effects: [] });
  });
  it.each([IDLE, opening, exchanging, sending, { phase: "done" } as const])("fuera de `waiting` (%o) se ignora", (state) => {
    expect(run(state, msg()).effects).toEqual([]);
  });
});

describe("closed y timeout", () => {
  it.each([opening, waiting])("%o: ventana cerrada sin terminar", (state) => {
    expect(run(state, { type: "closed" })).toEqual({
      state: { phase: "failed", failure: "closed" },
      effects: [{ type: "finish", outcome: "closed" }],
    });
  });
  it.each([opening, waiting])("%o: vencen los 5 minutos", (state) => {
    expect(run(state, { type: "timeout" }).state).toEqual({ phase: "failed", failure: "timeout" });
  });
  it.each([IDLE, exchanging, sending, { phase: "done" } as const])("%o: el cierre y el vencimiento ya no importan", (state) => {
    expect(run(state, { type: "closed" })).toEqual({ state, effects: [] });
    expect(run(state, { type: "timeout" })).toEqual({ state, effects: [] });
  });
});

describe("exchanged y sent", () => {
  it("canje bueno con MFA: envia una vez el cuerpo original", () => {
    expect(run(exchanging, { type: "exchanged", outcome: "ok" })).toEqual({
      state: sending,
      effects: [{ type: "send", body: BODY }],
    });
  });
  it("canje fallido o sin acr = mfa: termina sin enviar", () => {
    expect(run(exchanging, { type: "exchanged", outcome: "failed" }).state).toEqual({ phase: "failed", failure: "exchange" });
    expect(run(exchanging, { type: "exchanged", outcome: "no_mfa" }).state).toEqual({ phase: "failed", failure: "no_mfa" });
  });
  it("el resultado de un canje fuera de `exchanging` se ignora", () => {
    expect(run(waiting, { type: "exchanged", outcome: "ok" })).toEqual({ state: waiting, effects: [] });
  });
  it("el reenvio aceptado termina bien; el rechazado (incluido otro 403) termina con `retry` y no hay tercero", () => {
    expect(run(sending, { type: "sent", ok: true })).toEqual({
      state: { phase: "done" },
      effects: [{ type: "finish", outcome: "done" }],
    });
    expect(run(sending, { type: "sent", ok: false })).toEqual({
      state: { phase: "failed", failure: "retry" },
      effects: [{ type: "finish", outcome: "retry" }],
    });
  });
  it("un resultado de reenvio fuera de `sending` se ignora", () => {
    expect(run(IDLE, { type: "sent", ok: true })).toEqual({ state: IDLE, effects: [] });
  });
});

describe("busy y parseMessage", () => {
  it("busy solo en las cuatro fases en curso", () => {
    expect([IDLE, opening, waiting, exchanging, sending, { phase: "done" } as const].map(busy)).toEqual([
      false, true, true, true, true, false,
    ]);
  });
  it("parseMessage acepta solo {code, state} de cadenas", () => {
    expect(parseMessage({ code: "c", state: "s", extra: 1 })).toEqual({ code: "c", state: "s" });
    for (const bad of [null, undefined, "x", 1, {}, { code: "c" }, { state: "s" }, { code: 1, state: "s" }, { code: "c", state: 2 }]) {
      expect(parseMessage(bad)).toBeNull();
    }
  });
});
