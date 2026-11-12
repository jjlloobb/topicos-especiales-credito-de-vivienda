// Nucleo puro del step-up (BR-U10-06; P-U10-07; PBT-U10-05). Una maquina de estados: recibe eventos y devuelve el estado nuevo y
// los efectos que debe ejecutar quien la use. No toca `window`, `fetch` ni el reloj: todo eso llega por los eventos.
//
// Un intento a la vez. Cada `start` aceptado es una accion con su cuerpo; despues de una verificacion completa se envia **una**
// vez ese mismo cuerpo (`send`): no existe una segunda posibilidad ni un tercero.

export type Failure = "blocked" | "request" | "closed" | "timeout" | "exchange" | "no_mfa" | "retry";

export type StepUpState<B> =
  | { readonly phase: "idle" }
  | { readonly phase: "opening"; readonly body: B }
  | { readonly phase: "waiting"; readonly body: B; readonly expected: string }
  | { readonly phase: "exchanging"; readonly body: B }
  | { readonly phase: "sending"; readonly body: B }
  | { readonly phase: "done" }
  | { readonly phase: "failed"; readonly failure: Failure };

export type StepUpEvent<B> =
  /** El clic: `opened` es si `window.open` devolvio una ventana (false = bloqueada). */
  | { readonly type: "start"; readonly body: B; readonly opened: boolean }
  | { readonly type: "request_ready"; readonly state: string }
  | { readonly type: "request_failed" }
  /** `fromPopup`: `event.source` es la ventana que abrimos. `data` llega sin validar. */
  | { readonly type: "message"; readonly origin: string; readonly fromPopup: boolean; readonly data: unknown }
  | { readonly type: "closed" }
  | { readonly type: "timeout" }
  | { readonly type: "exchanged"; readonly outcome: "ok" | "failed" | "no_mfa" }
  | { readonly type: "sent"; readonly ok: boolean };

export type StepUpEffect<B> =
  | { readonly type: "create_request" }
  | { readonly type: "watch" }
  | { readonly type: "exchange"; readonly code: string; readonly state: string }
  | { readonly type: "send"; readonly body: B }
  /** Fin del intento, con exito o sin el: se borra `state`/`nonce`/`code_verifier`, se cierra la ventana, se anuncia y vuelve el foco. */
  | { readonly type: "finish"; readonly outcome: "done" | Failure };

export interface Transition<B> {
  readonly state: StepUpState<B>;
  readonly effects: readonly StepUpEffect<B>[];
}

export const IDLE = { phase: "idle" } as const;

/** Hay un intento en curso: un `start` nuevo se ignora. */
export function busy<B>(state: StepUpState<B>): boolean {
  return (
    state.phase === "opening" ||
    state.phase === "waiting" ||
    state.phase === "exchanging" ||
    state.phase === "sending"
  );
}

/** El mensaje de `/stepup-callback`: `{code, state}` de dos cadenas. Cualquier otra cosa no es un mensaje del step-up. */
export function parseMessage(data: unknown): { readonly code: string; readonly state: string } | null {
  if (typeof data !== "object" || data === null) return null;
  const { code, state } = data as Record<string, unknown>;
  return typeof code === "string" && typeof state === "string" ? { code, state } : null;
}

const STAY = <B>(state: StepUpState<B>): Transition<B> => ({ state, effects: [] });

function fail<B>(failure: Failure): Transition<B> {
  return { state: { phase: "failed", failure }, effects: [{ type: "finish", outcome: failure }] };
}

/** `ownOrigin` es `location.origin` de la ventana principal. */
export function step<B>(state: StepUpState<B>, event: StepUpEvent<B>, ownOrigin: string): Transition<B> {
  switch (event.type) {
    case "start":
      if (busy(state)) return STAY(state);
      if (!event.opened) return fail("blocked");
      return {
        state: { phase: "opening", body: event.body },
        effects: [{ type: "create_request" }, { type: "watch" }],
      };
    case "request_ready":
      if (state.phase !== "opening") return STAY(state);
      return { state: { phase: "waiting", body: state.body, expected: event.state }, effects: [] };
    case "request_failed":
      return state.phase === "opening" ? fail("request") : STAY(state);
    case "message": {
      if (state.phase !== "waiting") return STAY(state);
      const message = parseMessage(event.data);
      if (event.origin !== ownOrigin || !event.fromPopup || message === null || message.state !== state.expected) {
        return STAY(state);
      }
      return {
        state: { phase: "exchanging", body: state.body },
        effects: [{ type: "exchange", code: message.code, state: message.state }],
      };
    }
    case "closed":
    case "timeout": {
      const waiting = state.phase === "opening" || state.phase === "waiting";
      return waiting ? fail(event.type === "closed" ? "closed" : "timeout") : STAY(state);
    }
    case "exchanged":
      if (state.phase !== "exchanging") return STAY(state);
      if (event.outcome === "failed") return fail("exchange");
      if (event.outcome === "no_mfa") return fail("no_mfa");
      return { state: { phase: "sending", body: state.body }, effects: [{ type: "send", body: state.body }] };
    case "sent":
      if (state.phase !== "sending") return STAY(state);
      return event.ok
        ? { state: { phase: "done" }, effects: [{ type: "finish", outcome: "done" }] }
        : fail("retry");
  }
}
