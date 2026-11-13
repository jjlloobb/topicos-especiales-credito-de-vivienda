// @vitest-environment jsdom
// PBT-U10-05 (stateful; business-logic-model §3): para toda secuencia de eventos del step-up (403 `mfa_required` -> clic; mensajes con
// origen propio u otro, de la ventana abierta, de una anterior o de otra, con `state` igual, viejo u otro; ventana bloqueada o cerrada;
// vencimiento de 5 min; canje fallido; token sin `acr = mfa`; segundo 403; solicitudes y reenvios que llegan tarde):
//   (1) hay como maximo un reintento por accion (uno exacto por cada canje bueno);
//   (2) el reintento lleva exactamente el cuerpo original;
//   (3) solo un mensaje valido lo dispara;
//   (4) el estado del step-up (`state`/`nonce`/`code_verifier`) se borra siempre, y la ventana se cierra;
//   (5) `sessionStorage`, `localStorage` y la URL nunca cambian.
//
// El MODELO es independiente del codigo bajo prueba (F-02 y F-08 de la ronda 1): lleva su propia fase, sus propios contadores y la lista de lo
// que debe haber pasado, y decide con ellos que mensaje es valido; NUNCA lee `flow.state` ni `busy()`. Lo unico que lee del mundo falso es
// el `state` que su backend devolvio al resolver la solicitud. Los generadores llegan al camino de exito con el comando compuesto
// `GoodStep` (el siguiente paso bueno segun el modelo) mezclado con eventos hostiles.
// Perfil y semilla: tests/support/pbt.ts (`VECTRA_PBT_PROFILE`, `VECTRA_PBT_SEED`).
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { StepUpFlow } from "../../../src/stepup/flow";
import { flush, FakePopup, type Harness, harness, OWN } from "../../support/stepup-world";
import { pbtOptions } from "../../support/pbt";

interface Body {
  readonly justification: string;
  readonly factors: readonly string[];
}

type Phase = "idle" | "opening" | "waiting" | "exchanging" | "sending";
type Outcome = "done" | "blocked" | "request" | "closed" | "timeout" | "exchange" | "no_mfa" | "retry";

interface Attempt {
  readonly n: number;
  readonly body: Body;
  readonly popup: number; // indice en `world.popups`
  state: string | null;
}

/** Lo que DEBE haber pasado, segun la especificacion y no segun el codigo. */
interface Model {
  phase: Phase;
  attempt: Attempt | null;
  attempts: number;
  pendingRequests: number[]; // numeros de intento, en orden de llegada
  pendingExchanges: number;
  pendingSends: number;
  sends: Body[];
  exchangeCalls: number;
  popupsOpened: number;
  pastStates: string[];
  announcements: string[];
  finishes: number;
  failures: number;
  hrefAtStart: string;
}

interface Real {
  world: Harness<Body>;
  flow: StepUpFlow<Body>;
}

type Cmd = fc.AsyncCommand<Model, Real>;

const busy = (model: Model): boolean => model.phase !== "idle";

/** El intento termina: se anuncia, vuelve el foco y se reporta salvo `done` y `retry`. */
function end(model: Model, outcome: Outcome): void {
  model.phase = "idle";
  model.attempt = null;
  model.finishes += 1;
  model.announcements.push(outcome);
  if (outcome !== "done" && outcome !== "retry") model.failures += 1;
}

async function invariants(model: Model, real: Real): Promise<void> {
  await flush();
  const { world } = real;
  // (1) y (2): un reenvio por cada canje bueno, con el cuerpo (el mismo objeto) de su accion
  expect(world.sends.length).toBe(model.sends.length);
  model.sends.forEach((expected, i) => expect(world.sends[i]?.body).toBe(expected));
  // (3) solo un mensaje valido canjea
  expect(world.backend.exchangeCalls).toBe(model.exchangeCalls);
  expect(world.popups.length).toBe(model.popupsOpened);
  // lo que se anuncio, se devolvio de foco y se reporto
  expect(world.announcements).toEqual(model.announcements);
  expect(world.focusRestored).toBe(model.finishes);
  expect(world.failuresReported).toBe(model.failures);
  // (4) el `state` solo vive mientras el intento espera, canjea o reenvia; terminado, nada en memoria, ventanas cerradas y sin temporizadores
  const live = model.phase === "waiting" || model.phase === "exchanging" || model.phase === "sending";
  expect(world.backend.secrets.size).toBe(live ? 1 : 0);
  world.popups.forEach((popup, i) => {
    if (!busy(model) || i !== model.attempt?.popup) expect(popup.closed, `la ventana ${String(i)} debia estar cerrada`).toBe(true);
  });
  expect(world.timers.handles).toHaveLength(busy(model) ? 2 : 0);
  // (5) nada de almacenamiento ni cambio de URL
  expect(sessionStorage.length).toBe(0);
  expect(localStorage.length).toBe(0);
  expect(window.location.href).toBe(model.hrefAtStart);
}

const body = fc.record({
  justification: fc.string({ maxLength: 40 }),
  factors: fc.array(fc.string({ maxLength: 8 }), { maxLength: 3 }),
});

// ---- las acciones: cada una actualiza el modelo con la especificacion y las usa tambien el comando compuesto -----------------------
function start(model: Model, real: Real, b: Body, blocked: boolean): void {
  const opened = real.world.popups.length;
  real.world.blockNextOpen = blocked;
  real.flow.start(b);
  if (busy(model)) {
    expect(real.world.popups.length).toBe(opened); // un intento a la vez: no abre otra ventana
    return;
  }
  if (blocked) {
    expect(real.world.popups.length).toBe(opened);
    end(model, "blocked");
    return;
  }
  expect(real.world.popups.length).toBe(opened + 1);
  model.attempts += 1;
  model.phase = "opening";
  model.attempt = { n: model.attempts, body: b, popup: opened, state: null };
  model.popupsOpened += 1;
  model.announcements.push("opened");
  model.pendingRequests.push(model.attempts);
}

function resolveRequest(model: Model, real: Real, ok: boolean): void {
  const n = model.pendingRequests.shift();
  if (ok) {
    const id = real.world.backend.resolveRequest();
    if (n === undefined) return;
    if (model.phase === "opening" && model.attempt?.n === n) {
      model.phase = "waiting";
      model.attempt.state = id;
    } else model.pastStates.push(id); // llego tarde: su `state` se descarta
  } else {
    real.world.backend.rejectRequest();
    if (n !== undefined && model.phase === "opening" && model.attempt?.n === n) end(model, "request");
  }
}

type Source = "current" | "old" | "foreign";
type Which = "right" | "stale" | "wrong";

function message(model: Model, real: Real, own: boolean, source: Source, which: Which, shape: "ok" | "garbage"): void {
  const { world, flow } = real;
  const current = model.attempt === null ? world.popups.at(-1) : world.popups[model.attempt.popup];
  const old = world.popups.find((popup) => popup !== current);
  const from = source === "current" ? current : source === "old" ? (old ?? { otra: true }) : { otra: true };
  const state = which === "right" ? (model.attempt?.state ?? "sin-state") : which === "stale" ? (model.pastStates.at(-1) ?? "viejo") : "otro-state";
  const valid = model.phase === "waiting" && own && source === "current" && which === "right" && shape === "ok" && current !== undefined;
  const before = world.backend.exchangeCalls;
  flow.handleMessage({
    origin: own ? OWN : "https://evil.test",
    source: from,
    data: shape === "ok" ? { code: "codigo", state } : "basura",
  });
  expect(world.backend.exchangeCalls - before).toBe(valid ? 1 : 0); // (3)
  if (valid) {
    model.exchangeCalls += 1;
    model.phase = "exchanging";
    model.pendingExchanges += 1;
  }
}

function settleExchange(model: Model, real: Real, outcome: "ok" | "failed" | "no_mfa" | "throws"): void {
  if (model.pendingExchanges === 0) return;
  model.pendingExchanges -= 1;
  if (outcome === "throws") real.world.backend.rejectExchange();
  else real.world.backend.resolveExchange(outcome);
  if (outcome === "ok") {
    model.phase = "sending";
    model.sends.push((model.attempt as Attempt).body);
    model.pendingSends += 1;
  } else end(model, outcome === "no_mfa" ? "no_mfa" : "exchange");
}

function settleSend(model: Model, real: Real, ok: boolean): void {
  if (model.pendingSends === 0) return;
  model.pendingSends -= 1;
  const pending = real.world.sends.find((send) => !send.settled);
  pending?.result.resolve(ok); // `ok = false` es el segundo 403
  if (pending !== undefined) pending.settled = true;
  end(model, ok ? "done" : "retry");
}

class Start implements Cmd {
  constructor(
    readonly body: Body,
    readonly blocked: boolean,
  ) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    start(model, real, this.body, this.blocked);
    await invariants(model, real);
  }
  toString = (): string => `start(${JSON.stringify(this.body)}, blocked=${String(this.blocked)})`;
}

class ResolveRequest implements Cmd {
  constructor(readonly ok: boolean) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    resolveRequest(model, real, this.ok);
    await invariants(model, real);
  }
  toString = (): string => `request(${this.ok ? "ok" : "falla"})`;
}

class Message implements Cmd {
  constructor(
    readonly own: boolean,
    readonly source: Source,
    readonly which: Which,
    readonly shape: "ok" | "garbage",
  ) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    message(model, real, this.own, this.source, this.which, this.shape);
    await invariants(model, real);
  }
  toString = (): string => `message(propio=${String(this.own)}, ventana=${this.source}, state=${this.which}, forma=${this.shape})`;
}

class ClosePopup implements Cmd {
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    const popup: FakePopup | undefined = real.world.popups.at(-1);
    if (popup !== undefined) popup.closed = true;
    real.world.timers.fireInterval();
    if (model.phase === "opening" || model.phase === "waiting") end(model, "closed");
    await invariants(model, real);
  }
  toString = (): string => "close()";
}

class Timeout implements Cmd {
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    real.world.timers.fireTimeout();
    if (model.phase === "opening" || model.phase === "waiting") end(model, "timeout");
    await invariants(model, real);
  }
  toString = (): string => "timeout(5 min)";
}

class SettleExchange implements Cmd {
  constructor(readonly outcome: "ok" | "failed" | "no_mfa" | "throws") {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    settleExchange(model, real, this.outcome);
    await invariants(model, real);
  }
  toString = (): string => `exchange(${this.outcome})`;
}

class SettleSend implements Cmd {
  constructor(readonly ok: boolean) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    settleSend(model, real, this.ok);
    await invariants(model, real);
  }
  toString = (): string => `send(${this.ok ? "200" : "403"})`;
}

/**
 * El siguiente paso bueno del camino de exito, segun el MODELO: clic -> solicitud -> mensaje valido -> canje bueno -> reenvio 200.
 * Sin esto, una secuencia al azar casi nunca llega a `done` y las mutaciones del final del flujo sobreviven (F-02).
 */
class GoodStep implements Cmd {
  constructor(readonly body: Body) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    switch (model.phase) {
      case "idle":
        start(model, real, this.body, false);
        break;
      case "opening":
        resolveRequest(model, real, true);
        break;
      case "waiting":
        message(model, real, true, "current", "right", "ok");
        break;
      case "exchanging":
        settleExchange(model, real, "ok");
        break;
      case "sending":
        settleSend(model, real, true);
        break;
    }
    await invariants(model, real);
  }
  toString = (): string => "buen-paso()";
}

/**
 * Abandona un intento con la solicitud aun pendiente (cierra la ventana), abre otro y deja que llegue, bien o mal, la solicitud TARDIA del
 * primero: no puede tocar al intento nuevo (ni terminarlo ni mezclar su `state`).
 */
class AbandonAndRetry implements Cmd {
  constructor(
    readonly first: Body,
    readonly second: Body,
    readonly lateOk: boolean,
  ) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    if (busy(model)) return invariants(model, real); // solo desde cero: un intento a la vez
    start(model, real, this.first, false);
    const popup = real.world.popups.at(-1) as FakePopup;
    popup.closed = true;
    real.world.timers.fireInterval();
    end(model, "closed");
    start(model, real, this.second, false);
    resolveRequest(model, real, this.lateOk); // la mas antigua: la del primer intento
    await invariants(model, real);
  }
  toString = (): string => `abandona-y-reintenta(tardia ${this.lateOk ? "ok" : "falla"})`;
}

// `fc.commands` elige entre los generadores con la misma probabilidad: se repiten para dar pesos. `GoodStep` pesa mas que todo lo hostil
// junto, para que casi toda secuencia llegue a un canje bueno y a su reenvio; los hostiles se mezclan entre los pasos buenos.
const repeat = <T>(times: number, arbitrary: fc.Arbitrary<T>): fc.Arbitrary<T>[] => Array.from({ length: times }, () => arbitrary);
const hostileMessage = fc
  .tuple(fc.boolean(), fc.constantFrom("current", "old", "foreign"), fc.constantFrom("right", "stale", "wrong"), fc.constantFrom("ok", "garbage"))
  .map(([own, source, which, shape]) => new Message(own, source, which, shape));
const commands: fc.Arbitrary<Cmd>[] = [
  ...repeat(24, body.map((b) => new GoodStep(b))),
  ...repeat(3, fc.tuple(body, fc.constantFrom(false, false, false, true)).map(([b, blocked]) => new Start(b, blocked))),
  ...repeat(3, fc.constantFrom(true, true, true, false).map((ok) => new ResolveRequest(ok))),
  ...repeat(3, hostileMessage),
  // validos salvo en un solo campo: son los que un defecto en UNA comprobacion deja pasar
  fc.constant(new Message(false, "current", "right", "ok")),
  fc.constant(new Message(true, "foreign", "right", "ok")),
  fc.constant(new Message(true, "old", "right", "ok")),
  fc.constant(new Message(true, "current", "wrong", "ok")),
  fc.constant(new Message(true, "current", "stale", "ok")),
  fc.constant(new Message(true, "current", "right", "garbage")),
  fc.constant(new ClosePopup()),
  fc.constant(new Timeout()),
  ...repeat(3, fc.tuple(body, body, fc.boolean()).map(([a, b, lateOk]) => new AbandonAndRetry(a, b, lateOk))),
  ...repeat(3, fc.constantFrom("ok", "failed", "no_mfa", "throws").map((outcome) => new SettleExchange(outcome))),
  ...repeat(3, fc.constantFrom(true, false).map((ok) => new SettleSend(ok))),
];

describe("PBT-U10-05: stepup", () => {
  it("toda secuencia de eventos cumple las cinco invariantes frente al modelo independiente", async () => {
    const options = pbtOptions("PBT-U10-05");
    await fc.assert(
      fc.asyncProperty(fc.commands(commands, { maxCommands: 40 }), async (cmds) => {
        const setup = (): { model: Model; real: Real } => {
          const world = harness<Body>();
          return {
            model: {
              phase: "idle",
              attempt: null,
              attempts: 0,
              pendingRequests: [],
              pendingExchanges: 0,
              pendingSends: 0,
              sends: [],
              exchangeCalls: 0,
              popupsOpened: 0,
              pastStates: [],
              announcements: [],
              finishes: 0,
              failures: 0,
              hrefAtStart: window.location.href,
            },
            real: { world, flow: new StepUpFlow<Body>(world.deps) },
          };
        };
        await fc.asyncModelRun(setup, cmds);
      }),
      options,
    );
  });
});
