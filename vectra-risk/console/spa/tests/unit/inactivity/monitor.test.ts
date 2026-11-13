// @vitest-environment jsdom
// BR-U10-20; NFR-U10-40, 41: el contador de inactividad de la SESION, con reloj simulado (ninguna prueba duerme de verdad).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACTIVITY_BROADCAST_SECONDS, IDLE_LOGOUT_SECONDS, IDLE_WARNING_SECONDS } from "../../../src/config/constants";
import { ACTIVITY_EVENTS, attachActivity, CHANNEL_NAME, InactivityMonitor } from "../../../src/inactivity/monitor";
import { Bus } from "../../support/bus";

const MIN = 60_000;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

/** Una «pestana»: su monitor, los avisos y los logouts que recibio. */
function tab(bus: Bus) {
  const log = { warnings: 0, resumes: 0, logouts: 0 };
  const monitor = new InactivityMonitor({
    now: () => Date.now(),
    setTimeout: (handler, ms) => setTimeout(handler, ms),
    clearTimeout: (handle) => {
      clearTimeout(handle as ReturnType<typeof setTimeout>);
    },
    channel: bus.channel(),
    onWarning: () => (log.warnings += 1),
    onResume: () => (log.resumes += 1),
    onLogout: () => (log.logouts += 1),
  });
  return { monitor, log };
}

describe("aviso a los 25 min y logout a los 30", () => {
  it("24 min sin actividad: sin aviso; 25 min: aviso; 30 min: logout", () => {
    const { log } = tab(new Bus());
    vi.advanceTimersByTime(24 * MIN);
    expect(log).toEqual({ warnings: 0, resumes: 0, logouts: 0 });
    vi.advanceTimersByTime(1 * MIN);
    expect(log).toEqual({ warnings: 1, resumes: 0, logouts: 0 });
    vi.advanceTimersByTime(5 * MIN);
    expect(log).toEqual({ warnings: 1, resumes: 0, logouts: 1 });
    expect(IDLE_WARNING_SECONDS).toBe(25 * 60);
    expect(IDLE_LOGOUT_SECONDS).toBe(30 * 60);
  });

  it("«seguir» durante el aviso reinicia el contador y cierra el aviso", () => {
    const { monitor, log } = tab(new Bus());
    vi.advanceTimersByTime(26 * MIN);
    expect(log.warnings).toBe(1);
    monitor.activity(); // «seguir»
    expect(log.resumes).toBe(1);
    vi.advanceTimersByTime(24 * MIN);
    expect(log).toEqual({ warnings: 1, resumes: 1, logouts: 0 });
    vi.advanceTimersByTime(1 * MIN);
    expect(log.warnings).toBe(2); // 25 min despues del «seguir»
  });

  it("un formulario sin enviar no evita el cierre: solo cuenta la actividad", () => {
    const { log } = tab(new Bus());
    document.body.innerHTML = '<form><textarea name="justificacion">texto escrito hace mucho</textarea></form>';
    expect(document.querySelector("textarea")?.value).toBe("texto escrito hace mucho"); // el formulario esta ahi, sin enviar
    vi.advanceTimersByTime(30 * MIN);
    expect(log.logouts).toBe(1);
  });

  it("el temporizador se vuelve a armar si despierta antes de tiempo", () => {
    const { monitor, log } = tab(new Bus());
    vi.advanceTimersByTime(20 * MIN);
    monitor.activity();
    vi.advanceTimersByTime(24 * MIN);
    expect(log.warnings).toBe(0);
  });
});

describe("la inactividad es de la sesion, no de la pestana (NFR-U10-41)", () => {
  it("actividad en A durante 40 min con B quieta: ninguna cierra la sesion", () => {
    const bus = new Bus();
    const a = tab(bus);
    const b = tab(bus);
    for (let minute = 0; minute < 40; minute += 1) {
      vi.advanceTimersByTime(MIN);
      a.monitor.activity();
    }
    expect(a.log).toEqual({ warnings: 0, resumes: 0, logouts: 0 });
    expect(b.log).toEqual({ warnings: 0, resumes: 0, logouts: 0 });
  });

  it("30 min sin actividad en ninguna: logout en las dos, con un mensaje sin datos", () => {
    const bus = new Bus();
    const a = tab(bus);
    const b = tab(bus);
    vi.advanceTimersByTime(30 * MIN);
    expect(a.log.logouts).toBe(1);
    expect(b.log.logouts).toBe(1);
    expect(bus.posted).toContainEqual({ type: "logout" });
  });

  it("la actividad de A cierra el aviso de B", () => {
    const bus = new Bus();
    const a = tab(bus);
    const b = tab(bus);
    vi.advanceTimersByTime(26 * MIN);
    expect([a.log.warnings, b.log.warnings]).toEqual([1, 1]);
    a.monitor.activity();
    expect([a.log.resumes, b.log.resumes]).toEqual([1, 1]);
  });

  it("difunde `activity` como maximo cada 30 s", () => {
    const bus = new Bus();
    const a = tab(bus);
    tab(bus);
    for (let second = 0; second < ACTIVITY_BROADCAST_SECONDS - 1; second += 1) {
      a.monitor.activity();
      vi.advanceTimersByTime(1000);
    }
    expect(bus.posted).toEqual([{ type: "activity" }]); // 29 eventos en 29 s: un solo mensaje
    vi.advanceTimersByTime(1000);
    a.monitor.activity();
    expect(bus.posted).toHaveLength(2);
  });

  it("ningun mensaje del canal lleva otra clave que `type`", () => {
    const bus = new Bus();
    const a = tab(bus);
    tab(bus);
    for (let i = 0; i < 80; i += 1) {
      vi.advanceTimersByTime(MIN);
      if (i % 2 === 0) a.monitor.activity();
    }
    expect(bus.posted.length).toBeGreaterThan(2);
    for (const message of bus.posted) expect(Object.keys(message as object)).toEqual(["type"]);
  });

  it("un mensaje desconocido o sin forma no cambia nada", () => {
    const bus = new Bus();
    const a = tab(bus);
    const stranger = bus.channel();
    stranger.postMessage({ type: "otra-cosa" } as never);
    stranger.postMessage(null as never);
    stranger.postMessage("hola" as never);
    expect(a.log).toEqual({ warnings: 0, resumes: 0, logouts: 0 });
  });

  it("tras el logout no reacciona mas, y dispose suelta el canal", () => {
    const bus = new Bus();
    const a = tab(bus);
    vi.advanceTimersByTime(30 * MIN);
    a.monitor.activity();
    vi.advanceTimersByTime(60 * MIN);
    expect(a.log.logouts).toBe(1);
    const b = tab(bus);
    b.monitor.dispose();
    bus.channel().postMessage({ type: "logout" });
    expect(b.log.logouts).toBe(0);
  });

  it("el nombre del canal es vectra-console", () => {
    expect(CHANNEL_NAME).toBe("vectra-console");
  });
});

describe("los cinco eventos cuentan; lo demas, no", () => {
  it.each(ACTIVITY_EVENTS)("%s cuenta como actividad", (type) => {
    const target = new EventTarget();
    const activity = vi.fn();
    const detach = attachActivity(target, { activity });
    target.dispatchEvent(new Event(type));
    expect(activity).toHaveBeenCalledOnce();
    detach();
    target.dispatchEvent(new Event(type));
    expect(activity).toHaveBeenCalledOnce();
  });

  it("wheel y scroll reinician el contador de verdad", () => {
    const bus = new Bus();
    const { monitor, log } = tab(bus);
    const target = new EventTarget();
    attachActivity(target, monitor);
    for (const type of ["wheel", "scroll"]) {
      vi.advanceTimersByTime(24 * MIN);
      target.dispatchEvent(new Event(type));
    }
    vi.advanceTimersByTime(24 * MIN);
    expect(log).toEqual({ warnings: 0, resumes: 0, logouts: 0 });
  });

  it("otros eventos (un mousemove, una respuesta de la red) no cuentan", () => {
    const target = new EventTarget();
    const activity = vi.fn();
    attachActivity(target, { activity });
    target.dispatchEvent(new Event("mousemove"));
    target.dispatchEvent(new Event("message"));
    expect(activity).not.toHaveBeenCalled();
  });
});
