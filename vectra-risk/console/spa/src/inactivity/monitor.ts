// Contador de inactividad de la SESION, no de la pestana (BR-U10-20; NFR-U10-40, 41). Cinco eventos cuentan como actividad
// (`keydown`, `pointerdown`, `focusin`, `wheel`, `scroll`); el refresco automatico y las respuestas del BFF NO: este modulo no mira la
// red. Cada pestana difunde `{type: "activity"}` por `BroadcastChannel("vectra-console")` como maximo cada `ACTIVITY_BROADCAST_SECONDS`
// y todas reinician su contador; a `IDLE_WARNING_SECONDS` sin actividad en ninguna hay aviso, y a `IDLE_LOGOUT_SECONDS` logout en todas
// con `{type: "logout"}` (sin datos). Un formulario sin enviar no evita el cierre: solo cuenta la actividad.
import { ACTIVITY_BROADCAST_SECONDS, IDLE_LOGOUT_SECONDS, IDLE_WARNING_SECONDS } from "../config/constants";

export const CHANNEL_NAME = "vectra-console";
export const ACTIVITY_EVENTS = ["keydown", "pointerdown", "focusin", "wheel", "scroll"] as const;

export interface ChannelLike {
  postMessage(message: { readonly type: "activity" | "logout" }): void;
  addEventListener(type: "message", listener: (event: { readonly data: unknown }) => void): void;
  removeEventListener(type: "message", listener: (event: { readonly data: unknown }) => void): void;
  close(): void;
}

export interface MonitorDeps {
  readonly now: () => number;
  readonly setTimeout: (handler: () => void, ms: number) => unknown;
  readonly clearTimeout: (handle: unknown) => void;
  readonly channel: ChannelLike;
  /** A los 25 min sin actividad en ninguna pestana. */
  readonly onWarning: () => void;
  /** Hubo actividad mientras el aviso estaba abierto: se cierra el aviso. */
  readonly onResume: () => void;
  /** A los 30 min (o `logout` de otra pestana): borra la memoria y va al `end_session_endpoint`. */
  readonly onLogout: () => void;
}

function typeOf(data: unknown): unknown {
  return typeof data === "object" && data !== null ? (data as { type?: unknown }).type : undefined;
}

export class InactivityMonitor {
  private last: number;
  private lastBroadcast = Number.NEGATIVE_INFINITY;
  private warned = false;
  private stopped = false;
  private handle: unknown = null;
  private readonly listener = (event: { readonly data: unknown }): void => {
    const type = typeOf(event.data);
    if (type === "activity") this.reset();
    else if (type === "logout") this.logout(false);
  };

  constructor(private readonly deps: MonitorDeps) {
    this.last = deps.now();
    deps.channel.addEventListener("message", this.listener);
    this.schedule();
  }

  /** Actividad de esta pestana (uno de los cinco eventos, o «seguir»). */
  activity(): void {
    if (this.stopped) return;
    this.reset();
    const now = this.deps.now();
    if (now - this.lastBroadcast >= ACTIVITY_BROADCAST_SECONDS * 1000) {
      this.lastBroadcast = now;
      this.deps.channel.postMessage({ type: "activity" });
    }
  }

  dispose(): void {
    this.stopped = true;
    this.deps.clearTimeout(this.handle);
    this.deps.channel.removeEventListener("message", this.listener);
  }

  private reset(): void {
    if (this.stopped) return;
    this.last = this.deps.now();
    if (this.warned) {
      this.warned = false;
      this.deps.onResume();
    }
    this.schedule();
  }

  private schedule(): void {
    this.deps.clearTimeout(this.handle);
    const limit = (this.warned ? IDLE_LOGOUT_SECONDS : IDLE_WARNING_SECONDS) * 1000;
    this.handle = this.deps.setTimeout(() => {
      this.tick();
    }, Math.max(0, this.last + limit - this.deps.now()));
  }

  private tick(): void {
    const idle = this.deps.now() - this.last;
    if (idle >= IDLE_LOGOUT_SECONDS * 1000) this.logout(true);
    else if (idle >= IDLE_WARNING_SECONDS * 1000) {
      this.warned = true;
      this.deps.onWarning();
      this.schedule();
    } else this.schedule();
  }

  private logout(broadcast: boolean): void {
    if (broadcast) this.deps.channel.postMessage({ type: "logout" });
    this.dispose();
    this.deps.onLogout();
  }
}

/** Engancha los cinco eventos de actividad (en captura: `scroll` no burbujea). Devuelve la funcion que los suelta. */
export function attachActivity(
  target: Pick<EventTarget, "addEventListener" | "removeEventListener">,
  monitor: Pick<InactivityMonitor, "activity">,
): () => void {
  const handler = (): void => {
    monitor.activity();
  };
  for (const type of ACTIVITY_EVENTS) target.addEventListener(type, handler, { capture: true, passive: true });
  return () => {
    for (const type of ACTIVITY_EVENTS) target.removeEventListener(type, handler, { capture: true });
  };
}
