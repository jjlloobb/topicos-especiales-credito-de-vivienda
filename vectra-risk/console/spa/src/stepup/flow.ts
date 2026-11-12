// El flujo del step-up en el navegador (BR-U10-06; P-U10-07): une la maquina pura (`machine.ts`) con la ventana, los temporizadores y
// el cliente OIDC, que llegan por inyeccion.
//
// Punto clave (Paso 10 del plan): `window.open` se llama **dentro del clic y de forma sincrona**, con una pagina vacia, antes de
// cualquier `await`. Despues `createSigninRequest` (asincrono) genera `state`, `nonce` y el PKCE en memoria y la ventana ya
// abierta navega a la URL de autorizacion. Asi la activacion del usuario cubre la apertura y la pagina principal no se recarga.
import { STEPUP_TIMEOUT_SECONDS } from "../config/constants";
import { type Failure, IDLE, type StepUpState, busy, step, type StepUpEffect, type StepUpEvent } from "./machine";

/** Cada cuanto se mira si la ventana se cerro (el navegador no avisa del cierre de otra ventana). */
export const CLOSE_POLL_MS = 500;

export interface PopupLike {
  readonly closed: boolean;
  close(): void;
  readonly location: { replace(url: string): void };
}

export interface SigninRequestRef {
  readonly url: string;
  readonly id: string;
}

/** Lo que el flujo necesita del cliente OIDC (`oidc.ts` lo arma con `OidcClient`). */
export interface StepUpBackend {
  /** `createSigninRequest` con `prompt=login`, `max_age=0`, `acr_values=mfa` y el `redirect_uri` de `/stepup-callback`. */
  createRequest(): Promise<SigninRequestRef>;
  /** Canjea el codigo (valida `nonce`) y comprueba `acr = mfa`; en exito entrega los tokens a quien corresponda. */
  exchange(callbackUrl: string): Promise<"ok" | "failed" | "no_mfa">;
  /** Borra el `state`, el `nonce` y el `code_verifier` de ese intento. */
  removeState(id: string): Promise<void>;
}

export interface Timers {
  setTimeout(handler: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
  setInterval(handler: () => void, ms: number): unknown;
  clearInterval(handle: unknown): void;
}

/** Los temporizadores del navegador (la maquina y las pruebas inyectan otros). */
export const browserTimers: Timers = {
  setTimeout: (handler, ms) => window.setTimeout(handler, ms),
  clearTimeout: (handle) => {
    window.clearTimeout(handle as number);
  },
  setInterval: (handler, ms) => window.setInterval(handler, ms),
  clearInterval: (handle) => {
    window.clearInterval(handle as number);
  },
};

export type Announcement = "opened" | "done" | Failure;

export interface FlowDeps<B> {
  readonly ownOrigin: string;
  readonly stepupRedirectUri: string;
  readonly backend: StepUpBackend;
  /** `window.open("", nombre)`: debe llamarse en el manejador del clic. */
  readonly openWindow: () => PopupLike | null;
  /** Reenvia la accion con su cuerpo original; `true` si el servidor la acepto. */
  readonly send: (body: B) => Promise<boolean>;
  readonly timers: Timers;
  readonly announce: (announcement: Announcement) => void;
  /** Devuelve el foco al control que abrio la ventana. */
  readonly restoreFocus: () => void;
  /** Reporte `stepup_failed` (P-3 de U10-T03) cuando el intento no termina. */
  readonly reportFailure: () => void;
}

export interface MessageLike {
  readonly origin: string;
  readonly source: unknown;
  readonly data: unknown;
}

const NO_REPORT: ReadonlySet<string> = new Set(["done", "retry"]);

export class StepUpFlow<B> {
  private current: StepUpState<B> = IDLE;
  private popup: PopupLike | null = null;
  private stateId: string | null = null;
  /** Numero del intento en curso: una solicitud que llega tarde de un intento anterior no se mezcla con el actual. */
  private attempt = 0;
  private timeout: unknown = null;
  private poll: unknown = null;
  private readonly listeners = new Set<(state: StepUpState<B>) => void>();

  constructor(private readonly deps: FlowDeps<B>) {}

  get state(): StepUpState<B> {
    return this.current;
  }

  subscribe(listener: (state: StepUpState<B>) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Se llama **en el manejador del clic**: `window.open` sale antes de cualquier `await`. */
  start(body: B): void {
    if (busy(this.current)) return;
    this.popup = this.deps.openWindow();
    this.dispatch({ type: "start", body, opened: this.popup !== null });
  }

  /** El `message` de la ventana principal. La maquina decide si el origen, la ventana y el `state` sirven. */
  handleMessage(event: MessageLike): void {
    this.dispatch({
      type: "message",
      origin: event.origin,
      fromPopup: this.popup !== null && event.source === this.popup,
      data: event.data,
    });
  }

  private dispatch(event: StepUpEvent<B>): void {
    const transition = step(this.current, event, this.deps.ownOrigin);
    this.current = transition.state;
    for (const effect of transition.effects) this.run(effect);
    for (const listener of [...this.listeners]) listener(this.current);
  }

  private run(effect: StepUpEffect<B>): void {
    switch (effect.type) {
      case "create_request":
        this.deps.announce("opened");
        this.attempt += 1;
        void this.createRequest(this.attempt);
        return;
      case "watch":
        this.watch();
        return;
      case "exchange":
        void this.exchange(effect.code, effect.state);
        return;
      case "send":
        void this.deps.send(effect.body).then((ok) => {
          this.dispatch({ type: "sent", ok });
        });
        return;
      case "finish":
        this.finish(effect.outcome);
        return;
    }
  }

  private watch(): void {
    const { timers } = this.deps;
    const popup = this.popup as PopupLike;
    this.timeout = timers.setTimeout(() => {
      this.dispatch({ type: "timeout" });
    }, STEPUP_TIMEOUT_SECONDS * 1000);
    this.poll = timers.setInterval(() => {
      if (popup.closed) this.dispatch({ type: "closed" });
    }, CLOSE_POLL_MS);
  }

  private async createRequest(attempt: number): Promise<void> {
    let request: SigninRequestRef;
    try {
      request = await this.deps.backend.createRequest();
    } catch {
      this.dispatch({ type: "request_failed" });
      return;
    }
    if (this.attempt !== attempt || this.current.phase !== "opening") {
      await this.deps.backend.removeState(request.id); // el intento termino (o ya hay otro): no queda nada en memoria
      return;
    }
    this.stateId = request.id;
    (this.popup as PopupLike).location.replace(request.url);
    this.dispatch({ type: "request_ready", state: request.id });
  }

  private async exchange(code: string, state: string): Promise<void> {
    const query = new URLSearchParams({ code, state });
    const outcome = await this.deps.backend.exchange(`${this.deps.stepupRedirectUri}?${query.toString()}`).catch(
      () => "failed" as const,
    );
    this.dispatch({ type: "exchanged", outcome });
  }

  private finish(outcome: "done" | Failure): void {
    const { timers, backend } = this.deps;
    timers.clearTimeout(this.timeout);
    timers.clearInterval(this.poll);
    const id = this.stateId;
    this.stateId = null;
    if (id !== null) void backend.removeState(id);
    this.popup?.close();
    this.popup = null;
    this.deps.announce(outcome);
    this.deps.restoreFocus();
    if (!NO_REPORT.has(outcome)) this.deps.reportFailure();
  }
}
