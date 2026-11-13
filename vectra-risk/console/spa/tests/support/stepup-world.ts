// Mundo de dobles del step-up (solo pruebas): una ventana emergente falsa, un backend OIDC con resultados controlados por la prueba,
// temporizadores manuales y la recoleccion de lo que el flujo hace (ventanas abiertas, canjes, reenvios, estado en memoria).
import type { FlowDeps, PopupLike, SigninRequestRef, StepUpBackend, Timers } from "../../src/stepup/flow";

export const OWN = "https://console.test";
export const CALLBACK = `${OWN}/stepup-callback`;

export class FakePopup implements PopupLike {
  closed = false;
  navigated: string[] = [];
  readonly location = {
    replace: (url: string) => {
      this.navigated.push(url);
    },
  };
  close(): void {
    this.closed = true;
  }
}

export interface Deferred<T> {
  promise: Promise<T>;
  resolve(value: T): void;
  reject(error: unknown): void;
}

export function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

type Handle = { id: number; handler: () => void; kind: "timeout" | "interval"; ms: number };

export class ManualTimers implements Timers {
  handles: Handle[] = [];
  private next = 1;
  setTimeout(handler: () => void, ms: number): unknown {
    const handle: Handle = { id: this.next++, handler, kind: "timeout", ms };
    this.handles.push(handle);
    return handle.id;
  }
  setInterval(handler: () => void, ms: number): unknown {
    const handle: Handle = { id: this.next++, handler, kind: "interval", ms };
    this.handles.push(handle);
    return handle.id;
  }
  clearTimeout(id: unknown): void {
    this.handles = this.handles.filter((h) => h.id !== id);
  }
  clearInterval(id: unknown): void {
    this.handles = this.handles.filter((h) => h.id !== id);
  }
  /** Dispara el temporizador del vencimiento si sigue armado. */
  fireTimeout(): void {
    this.handles.find((h) => h.kind === "timeout")?.handler();
  }
  /** Dispara la comprobacion periodica de «la ventana se cerro». */
  fireInterval(): void {
    this.handles.find((h) => h.kind === "interval")?.handler();
  }
}

export type ExchangeOutcome = "ok" | "failed" | "no_mfa";

/** El backend falso: cada llamada queda pendiente hasta que la prueba la resuelve. El `secrets` es lo que vive en memoria. */
export class FakeBackend implements StepUpBackend {
  secrets = new Set<string>();
  created = 0;
  requests: Deferred<SigninRequestRef>[] = [];
  exchanges: { url: string; result: Deferred<ExchangeOutcome> }[] = [];
  /** Cuantas veces se pidio un canje (todos, resueltos o no). */
  exchangeCalls = 0;
  removed: string[] = [];

  createRequest(): Promise<SigninRequestRef> {
    const pending = deferred<SigninRequestRef>();
    this.requests.push(pending);
    return pending.promise;
  }
  exchange(url: string): Promise<ExchangeOutcome> {
    this.exchangeCalls += 1;
    const result = deferred<ExchangeOutcome>();
    this.exchanges.push({ url, result });
    return result.promise;
  }
  removeState(id: string): Promise<void> {
    this.secrets.delete(id);
    this.removed.push(id);
    return Promise.resolve();
  }
  /** Resuelve la solicitud pendiente mas antigua con un `state` nuevo (que queda «en memoria»). */
  resolveRequest(): string {
    const pending = this.requests.shift();
    if (pending === undefined) return "";
    const id = `state-${++this.created}`;
    this.secrets.add(id);
    pending.resolve({ url: `${OWN}/auth?state=${id}`, id });
    return id;
  }
  rejectRequest(): void {
    this.requests.shift()?.reject(new Error("fallo"));
  }
  resolveExchange(outcome: ExchangeOutcome): void {
    this.exchanges.shift()?.result.resolve(outcome);
  }
  rejectExchange(): void {
    this.exchanges.shift()?.result.reject(new Error("fallo"));
  }
}

export interface Harness<B> {
  deps: FlowDeps<B>;
  backend: FakeBackend;
  timers: ManualTimers;
  popups: FakePopup[];
  sends: { body: B; result: Deferred<boolean>; settled: boolean }[];
  announcements: string[];
  focusRestored: number;
  failuresReported: number;
  blockNextOpen: boolean;
}

export function harness<B>(): Harness<B> {
  const backend = new FakeBackend();
  const timers = new ManualTimers();
  const world = {
    backend,
    timers,
    popups: [] as FakePopup[],
    sends: [] as { body: B; result: Deferred<boolean>; settled: boolean }[],
    announcements: [] as string[],
    focusRestored: 0,
    failuresReported: 0,
    blockNextOpen: false,
  } as Harness<B>;
  world.deps = {
    ownOrigin: OWN,
    stepupRedirectUri: CALLBACK,
    backend,
    openWindow: () => {
      if (world.blockNextOpen) return null;
      const popup = new FakePopup();
      world.popups.push(popup);
      return popup;
    },
    send: (body) => {
      const result = deferred<boolean>();
      world.sends.push({ body, result, settled: false });
      return result.promise;
    },
    timers,
    announce: (announcement) => {
      world.announcements.push(announcement);
    },
    restoreFocus: () => {
      world.focusRestored += 1;
    },
    reportFailure: () => {
      world.failuresReported += 1;
    },
  };
  return world;
}

/** Deja correr las promesas ya resueltas. */
export const flush = async (): Promise<void> => {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
};
