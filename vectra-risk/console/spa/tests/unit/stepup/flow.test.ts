// @vitest-environment jsdom
// BR-U10-06; P-U10-07; NFR-U10-40, 52: `StepUpFlow` con la ventana, el backend y los temporizadores falsos.
import { describe, expect, it } from "vitest";
import { STEPUP_TIMEOUT_SECONDS } from "../../../src/config/constants";
import { browserTimers, CLOSE_POLL_MS, StepUpFlow } from "../../../src/stepup/flow";
import { flush, harness, OWN } from "../../support/stepup-world";

type B = { justification: string };
const BODY: B = { justification: "porque si" };

function setup() {
  const world = harness<B>();
  const flow = new StepUpFlow<B>(world.deps);
  return { world, flow };
}

/** Un intento hasta quedar esperando el mensaje; devuelve el `state` de la solicitud. */
async function toWaiting(world: ReturnType<typeof harness<B>>, flow: StepUpFlow<B>): Promise<string> {
  flow.start(BODY);
  const id = world.backend.resolveRequest();
  await flush();
  expect(flow.state.phase).toBe("waiting");
  return id;
}

const message = (world: ReturnType<typeof harness<B>>, state: string, over: Record<string, unknown> = {}) => ({
  origin: OWN,
  source: world.popups[0],
  data: { code: "codigo", state },
  ...over,
});

describe("start", () => {
  it("abre la ventana de forma sincrona, antes de pedir la solicitud, y anuncia", () => {
    const { world, flow } = setup();
    flow.start(BODY);
    expect(world.popups).toHaveLength(1); // ya abierta: ningun await entre start() y window.open
    expect(world.backend.requests).toHaveLength(1);
    expect(world.announcements).toEqual(["opened"]);
    expect(flow.state.phase).toBe("opening");
  });

  it("la ventana bloqueada termina el intento sin pedir nada", () => {
    const { world, flow } = setup();
    world.blockNextOpen = true;
    flow.start(BODY);
    expect(flow.state).toEqual({ phase: "failed", failure: "blocked" });
    expect(world.backend.requests).toHaveLength(0);
    expect(world.announcements).toEqual(["blocked"]);
    expect(world.focusRestored).toBe(1);
    expect(world.failuresReported).toBe(1);
  });

  it("con un intento en curso no abre otra ventana", () => {
    const { world, flow } = setup();
    flow.start(BODY);
    flow.start({ justification: "otra" });
    expect(world.popups).toHaveLength(1);
  });
});

describe("la solicitud", () => {
  it("la ventana abierta navega a la URL de autorizacion y el flujo espera el mensaje", async () => {
    const { world, flow } = setup();
    const id = await toWaiting(world, flow);
    expect(world.popups[0]?.navigated).toEqual([`${OWN}/auth?state=${id}`]);
  });

  it("si la solicitud falla: `request`, ventana cerrada y reporte", async () => {
    const { world, flow } = setup();
    flow.start(BODY);
    world.backend.rejectRequest();
    await flush();
    expect(flow.state).toEqual({ phase: "failed", failure: "request" });
    expect(world.popups[0]?.closed).toBe(true);
    expect(world.failuresReported).toBe(1);
  });

  it("si el intento termino antes de que llegue la solicitud, su state se borra de inmediato", async () => {
    const { world, flow } = setup();
    flow.start(BODY);
    world.popups[0]!.closed = true;
    world.timers.fireInterval(); // la ventana se cerro mientras se creaba la solicitud
    expect(flow.state).toEqual({ phase: "failed", failure: "closed" });
    const id = world.backend.resolveRequest();
    await flush();
    expect(world.backend.secrets.has(id)).toBe(false);
    expect(world.popups[0]?.navigated).toEqual([]); // y no se navega
  });
});

describe("el mensaje y el canje", () => {
  it("un mensaje valido canjea el codigo con la URL del callback y despues reenvia UNA vez el mismo cuerpo", async () => {
    const { world, flow } = setup();
    const id = await toWaiting(world, flow);
    flow.handleMessage(message(world, id));
    expect(world.backend.exchanges[0]?.url).toBe(`${OWN}/stepup-callback?code=codigo&state=${id}`);
    world.backend.resolveExchange("ok");
    await flush();
    expect(world.sends).toHaveLength(1);
    expect(world.sends[0]?.body).toBe(BODY);
    world.sends[0]?.result.resolve(true);
    await flush();
    expect(flow.state).toEqual({ phase: "done" });
    expect(world.announcements).toEqual(["opened", "done"]);
    expect(world.focusRestored).toBe(1);
    expect(world.failuresReported).toBe(0);
    expect(world.backend.secrets.size).toBe(0);
    expect(world.popups[0]?.closed).toBe(true);
  });

  it.each([
    ["otro origen", (_w: unknown, id: string) => ({ origin: "https://evil.test", data: { code: "x", state: id } })],
    ["otra ventana", () => ({ source: { otra: true } })],
    ["otro state", () => ({ data: { code: "x", state: "otro" } })],
  ])("%s: se ignora, sin canje ni reenvio", async (_name, build) => {
    const { world, flow } = setup();
    const id = await toWaiting(world, flow);
    flow.handleMessage(message(world, id, build(world, id)));
    expect(world.backend.exchanges).toHaveLength(0);
    expect(world.sends).toHaveLength(0);
    expect(flow.state.phase).toBe("waiting");
  });

  it("un mensaje antes de abrir ninguna ventana no coincide con ninguna", () => {
    const { world, flow } = setup();
    flow.handleMessage({ origin: OWN, source: null, data: { code: "c", state: "s" } });
    expect(world.backend.exchanges).toHaveLength(0);
  });

  it("canje fallido, que lanza o sin acr = mfa: termina sin reenviar", async () => {
    for (const settle of [
      (w: ReturnType<typeof harness<B>>) => {
        w.backend.resolveExchange("failed");
      },
      (w: ReturnType<typeof harness<B>>) => {
        w.backend.rejectExchange();
      },
      (w: ReturnType<typeof harness<B>>) => {
        w.backend.resolveExchange("no_mfa");
      },
    ]) {
      const { world, flow } = setup();
      const id = await toWaiting(world, flow);
      flow.handleMessage(message(world, id));
      settle(world);
      await flush();
      expect(flow.state.phase).toBe("failed");
      expect(world.sends).toHaveLength(0);
      expect(world.backend.secrets.size).toBe(0);
      expect(world.failuresReported).toBe(1);
    }
  });

  it("el reenvio rechazado (otro 403) termina con `retry` sin tercero y sin reporte de step-up", async () => {
    const { world, flow } = setup();
    const id = await toWaiting(world, flow);
    flow.handleMessage(message(world, id));
    world.backend.resolveExchange("ok");
    await flush();
    world.sends[0]?.result.resolve(false);
    await flush();
    expect(flow.state).toEqual({ phase: "failed", failure: "retry" });
    expect(world.sends).toHaveLength(1);
    expect(world.failuresReported).toBe(0);
    expect(world.announcements.at(-1)).toBe("retry");
  });
});

describe("el cierre y el vencimiento", () => {
  it("vigila la ventana cada 500 ms y vence a los 5 min", async () => {
    const { world, flow } = setup();
    await toWaiting(world, flow);
    expect(world.timers.handles.map((h) => [h.kind, h.ms])).toEqual([
      ["timeout", STEPUP_TIMEOUT_SECONDS * 1000],
      ["interval", CLOSE_POLL_MS],
    ]);
  });

  it("ventana viva: la comprobacion no hace nada; cerrada sin terminar: `closed` sin reintento", async () => {
    const { world, flow } = setup();
    await toWaiting(world, flow);
    world.timers.fireInterval();
    expect(flow.state.phase).toBe("waiting");
    world.popups[0]!.closed = true;
    world.timers.fireInterval();
    expect(flow.state).toEqual({ phase: "failed", failure: "closed" });
    expect(world.sends).toHaveLength(0);
    expect(world.timers.handles).toHaveLength(0); // los temporizadores se sueltan al terminar
  });

  it("a los 5 min sin respuesta: `timeout`, ventana cerrada y state borrado", async () => {
    const { world, flow } = setup();
    const id = await toWaiting(world, flow);
    world.timers.fireTimeout();
    expect(flow.state).toEqual({ phase: "failed", failure: "timeout" });
    expect(world.popups[0]?.closed).toBe(true);
    expect(world.backend.secrets.has(id)).toBe(false);
  });
});

describe("subscribe y los temporizadores del navegador", () => {
  it("avisa los cambios de estado y deja de avisar al darse de baja", () => {
    const { flow } = setup();
    const seen: string[] = [];
    const off = flow.subscribe((state) => seen.push(state.phase));
    flow.start(BODY);
    off();
    flow.handleMessage({ origin: OWN, source: null, data: null });
    expect(seen).toEqual(["opening"]);
  });

  it("browserTimers delega en window", () => {
    const fired: string[] = [];
    const timeout = browserTimers.setTimeout(() => fired.push("t"), 1_000_000);
    browserTimers.clearTimeout(timeout);
    const interval = browserTimers.setInterval(() => fired.push("i"), 1_000_000);
    browserTimers.clearInterval(interval);
    expect(fired).toEqual([]);
  });
});

describe("una solicitud tardia de un intento anterior", () => {
  it("no se mezcla con el intento nuevo: su state se borra y el actual sigue con el suyo", async () => {
    const { world, flow } = setup();
    flow.start(BODY); // intento 1: su solicitud queda pendiente
    world.popups[0]!.closed = true;
    world.timers.fireInterval(); // intento 1 termina (`closed`)
    flow.start(BODY); // intento 2 (otra ventana)
    expect(flow.state.phase).toBe("opening");
    const stale = world.backend.resolveRequest(); // llega la solicitud del intento 1
    await flush();
    expect(world.backend.secrets.has(stale)).toBe(false);
    expect(flow.state.phase).toBe("opening"); // sigue esperando la suya
    const own = world.backend.resolveRequest();
    await flush();
    expect(flow.state).toMatchObject({ phase: "waiting", expected: own });
    expect(world.popups[1]?.navigated).toEqual([`${OWN}/auth?state=${own}`]);
  });

  // Hallado por el modelo independiente de PBT-U10-05 (ronda 2): el fallo tardio de la solicitud del intento 1 mataba al intento 2.
  it("el FALLO tardio de la solicitud de un intento anterior tampoco toca al intento nuevo", async () => {
    const { world, flow } = setup();
    flow.start(BODY); // intento 1: su solicitud queda pendiente
    world.popups[0]!.closed = true;
    world.timers.fireInterval(); // intento 1 termina (`closed`)
    flow.start(BODY); // intento 2
    world.backend.rejectRequest(); // falla la solicitud del intento 1
    await flush();
    expect(flow.state.phase).toBe("opening"); // el intento 2 sigue vivo
    expect(world.failuresReported).toBe(1); // solo el `closed` del intento 1
    const own = world.backend.resolveRequest();
    await flush();
    expect(flow.state).toMatchObject({ phase: "waiting", expected: own });
  });
});
