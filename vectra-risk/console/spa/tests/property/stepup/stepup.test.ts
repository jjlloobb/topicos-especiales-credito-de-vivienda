// @vitest-environment jsdom
// PBT-U10-05 (stateful; business-logic-model §3): para toda secuencia de eventos del step-up (403 `mfa_required` -> clic; mensajes con
// origen propio u otro, de la ventana abierta u otra, con `state` igual o distinto; ventana bloqueada o cerrada; vencimiento de 5 min;
// canje fallido; token sin `acr = mfa`; segundo 403):
//   (1) hay como maximo un reintento por accion;
//   (2) el reintento lleva exactamente el cuerpo original;
//   (3) solo un mensaje valido lo dispara;
//   (4) el estado del step-up (`state`/`nonce`/`code_verifier`) se borra siempre, y la ventana se cierra;
//   (5) `sessionStorage`, `localStorage` y la URL nunca cambian.
// Perfil y semilla: tests/support/pbt.ts (`VECTRA_PBT_PROFILE`, `VECTRA_PBT_SEED`).
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { StepUpFlow } from "../../../src/stepup/flow";
import { busy } from "../../../src/stepup/machine";
import { flush, FakePopup, type Harness, harness, OWN } from "../../support/stepup-world";
import { pbtOptions } from "../../support/pbt";

interface Body {
  readonly justification: string;
  readonly factors: readonly string[];
}

interface Model {
  starts: { body: Body; sends: number }[];
  validMessages: number;
  okExchanges: number;
  hrefAtStart: string;
}

interface Real {
  world: Harness<Body>;
  flow: StepUpFlow<Body>;
  lastState: string | null;
}

type Cmd = fc.AsyncCommand<Model, Real>;

async function invariants(model: Model, real: Real): Promise<void> {
  await flush();
  const { world, flow } = real;
  // (1) y (2): cada reenvio es del intento en curso, lleva su cuerpo (el mismo objeto) y no pasa de uno por accion
  expect(world.sends.length).toBeLessThanOrEqual(model.starts.length);
  for (const send of world.sends) {
    const owner = model.starts.find((start) => start.body === send.body);
    expect(owner, "un reenvio con un cuerpo que no es el de ninguna accion").toBeDefined();
  }
  for (const start of model.starts) {
    expect(world.sends.filter((send) => send.body === start.body).length).toBeLessThanOrEqual(1);
  }
  // (3) solo un mensaje valido canjea; solo un canje bueno reenvia
  expect(world.backend.exchangeCalls).toBe(model.validMessages);
  expect(world.sends.length).toBeLessThanOrEqual(model.okExchanges);
  // (4) intento terminado: nada en memoria y la ventana cerrada
  if (!busy(flow.state)) {
    expect(world.backend.secrets.size).toBe(0);
    for (const popup of world.popups) expect(popup.closed).toBe(true);
    expect(world.timers.handles).toHaveLength(0);
  }
  // un intento en curso no deja mas de un state vivo
  expect(world.backend.secrets.size).toBeLessThanOrEqual(1);
  // (5) nada de almacenamiento ni cambio de URL
  expect(sessionStorage.length).toBe(0);
  expect(localStorage.length).toBe(0);
  expect(window.location.href).toBe(model.hrefAtStart);
}

const body = fc.record({
  justification: fc.string({ maxLength: 40 }),
  factors: fc.array(fc.string({ maxLength: 8 }), { maxLength: 3 }),
});

class Start implements Cmd {
  constructor(
    readonly body: Body,
    readonly blocked: boolean,
  ) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    const wasBusy = busy(real.flow.state);
    const opened = real.world.popups.length;
    real.world.blockNextOpen = this.blocked;
    real.flow.start(this.body);
    if (wasBusy) {
      expect(real.world.popups.length).toBe(opened); // un intento a la vez: no abre otra ventana
    } else {
      model.starts.push({ body: this.body, sends: 0 });
      expect(real.world.popups.length).toBe(opened + (this.blocked ? 0 : 1));
    }
    await invariants(model, real);
  }
  toString = (): string => `start(${JSON.stringify(this.body)}, blocked=${String(this.blocked)})`;
}

class ResolveRequest implements Cmd {
  constructor(readonly ok: boolean) {}
  check = (m: Model): boolean => m.starts.length > 0;
  async run(model: Model, real: Real): Promise<void> {
    if (this.ok) real.lastState = real.world.backend.resolveRequest();
    else real.world.backend.rejectRequest();
    await invariants(model, real);
  }
  toString = (): string => `request(${this.ok ? "ok" : "falla"})`;
}

class Message implements Cmd {
  constructor(
    readonly own: boolean,
    readonly fromPopup: boolean,
    readonly state: "right" | "wrong",
    readonly shape: "ok" | "garbage",
  ) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    const { world, flow } = real;
    const popup = world.popups.at(-1);
    const expected = flow.state.phase === "waiting" ? flow.state.expected : null;
    const state = this.state === "right" && expected !== null ? expected : "otro-state";
    const valid =
      flow.state.phase === "waiting" &&
      this.own &&
      this.fromPopup &&
      popup !== undefined &&
      this.state === "right" &&
      this.shape === "ok";
    const before = world.backend.exchangeCalls;
    flow.handleMessage({
      origin: this.own ? OWN : "https://evil.test",
      source: this.fromPopup ? popup : { otra: true },
      data: this.shape === "ok" ? { code: "codigo", state } : "basura",
    });
    expect(world.backend.exchangeCalls - before).toBe(valid ? 1 : 0); // (3)
    if (valid) model.validMessages += 1;
    await invariants(model, real);
  }
  toString = (): string =>
    `message(propio=${String(this.own)}, ventana=${String(this.fromPopup)}, state=${this.state}, forma=${this.shape})`;
}

class ClosePopup implements Cmd {
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    const popup: FakePopup | undefined = real.world.popups.at(-1);
    if (popup !== undefined) popup.closed = true;
    real.world.timers.fireInterval();
    await invariants(model, real);
  }
  toString = (): string => "close()";
}

class Timeout implements Cmd {
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    real.world.timers.fireTimeout();
    await invariants(model, real);
  }
  toString = (): string => "timeout(5 min)";
}

class SettleExchange implements Cmd {
  constructor(readonly outcome: "ok" | "failed" | "no_mfa" | "throws") {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    if (real.world.backend.exchanges.length > 0) {
      if (this.outcome === "throws") real.world.backend.rejectExchange();
      else {
        if (this.outcome === "ok") model.okExchanges += 1;
        real.world.backend.resolveExchange(this.outcome);
      }
    }
    await invariants(model, real);
  }
  toString = (): string => `exchange(${this.outcome})`;
}

class SettleSend implements Cmd {
  constructor(readonly ok: boolean) {}
  check = (): boolean => true;
  async run(model: Model, real: Real): Promise<void> {
    real.world.sends.find((send) => !send.settled)?.result.resolve(this.ok); // `ok = false` es el segundo 403
    const pending = real.world.sends.find((send) => !send.settled);
    if (pending !== undefined) pending.settled = true;
    await invariants(model, real);
  }
  toString = (): string => `send(${this.ok ? "200" : "403"})`;
}

// `fc.commands` elige entre los generadores con la misma probabilidad: se repiten para dar pesos. Las secuencias utiles (clic, solicitud,
// mensaje valido, canje bueno, reenvio) tienen que salir con frecuencia; los eventos hostiles (origen ajeno, otra ventana, state
// distinto, cierre, vencimiento) se mezclan entre ellas.
const repeat = <T>(times: number, arbitrary: fc.Arbitrary<T>): fc.Arbitrary<T>[] => Array.from({ length: times }, () => arbitrary);
const hostileMessage = fc
  .tuple(fc.boolean(), fc.boolean(), fc.constantFrom("right", "wrong"), fc.constantFrom("ok", "garbage"))
  .map(([own, fromPopup, state, shape]) => new Message(own, fromPopup, state, shape));
const commands: fc.Arbitrary<Cmd>[] = [
  ...repeat(4, fc.tuple(body, fc.constantFrom(false, false, false, true)).map(([b, blocked]) => new Start(b, blocked))),
  ...repeat(4, fc.constantFrom(true, true, true, false).map((ok) => new ResolveRequest(ok))),
  ...repeat(5, fc.constant(new Message(true, true, "right", "ok"))),
  ...repeat(2, hostileMessage),
  // validos salvo en un solo campo: son los que un defecto en UNA comprobacion deja pasar
  fc.constant(new Message(false, true, "right", "ok")),
  fc.constant(new Message(true, false, "right", "ok")),
  fc.constant(new Message(true, true, "wrong", "ok")),
  fc.constant(new Message(true, true, "right", "garbage")),
  fc.constant(new ClosePopup()),
  fc.constant(new Timeout()),
  ...repeat(4, fc.constantFrom("ok", "ok", "failed", "no_mfa", "throws").map((outcome) => new SettleExchange(outcome))),
  ...repeat(4, fc.constantFrom(true, false).map((ok) => new SettleSend(ok))),
];

describe("PBT-U10-05: stepup", () => {
  it("toda secuencia de eventos cumple las cinco invariantes", async () => {
    const options = pbtOptions("PBT-U10-05");
    await fc.assert(
      fc.asyncProperty(fc.commands(commands, { maxCommands: 40 }), async (cmds) => {
        const setup = (): { model: Model; real: Real } => {
          const world = harness<Body>();
          return {
            model: { starts: [], validMessages: 0, okExchanges: 0, hrefAtStart: window.location.href },
            real: { world, flow: new StepUpFlow<Body>(world.deps), lastState: null },
          };
        };
        await fc.asyncModelRun(setup, cmds);
      }),
      options,
    );
  });
});
