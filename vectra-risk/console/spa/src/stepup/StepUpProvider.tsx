// `StepUpProvider` (BR-U10-06; P-U10-07): une `StepUpFlow` con React. Las vistas piden confirmar una accion con `confirm` (o con
// `StepUpButton`) **dentro del manejador de un clic**: si la sesion no tiene MFA reciente la ventana se abre en ese mismo clic y la
// accion se envia al terminar la verificacion; si la tiene, se envia ya y, solo si el BFF responde 403 `mfa_required`, sale el dialogo.
import { createContext, type ReactNode, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { SessionInfo } from "../api/endpoints";
import { type UiKey, ui } from "../i18n";
import { type Announcement, type FlowDeps, StepUpFlow } from "./flow";
import { recentMfa } from "./mfa";
import { StepUpDialog } from "./StepUpDialog";

/** `ok`: la accion se hizo; `mfa_required`: el BFF pidio MFA (sale el dialogo); `failed`: cualquier otro resultado. */
export type ConfirmResult = "ok" | "mfa_required" | "failed";

export interface StepUpAction<B> {
  /** El cuerpo original (justificacion y datos): el reintento lleva exactamente este. */
  readonly body: B;
  readonly send: (body: B) => Promise<ConfirmResult>;
}

export interface StepUpEnv {
  readonly ownOrigin: string;
  readonly stepupRedirectUri: string;
  readonly backend: FlowDeps<unknown>["backend"];
  readonly openWindow: FlowDeps<unknown>["openWindow"];
  readonly timers: FlowDeps<unknown>["timers"];
  readonly reportFailure: () => void;
  readonly now: () => number;
  readonly messageTarget: Pick<Window, "addEventListener" | "removeEventListener">;
}

export interface StepUpApi {
  /** La sesion no tiene MFA reciente: el boton de confirmacion dice «Verificar y confirmar». */
  readonly needsStepUp: boolean;
  /** Hay una verificacion en curso. */
  readonly busy: boolean;
  /** Llamar **dentro del manejador del clic**; `trigger` es el control al que vuelve el foco. */
  readonly confirm: <B>(action: StepUpAction<B>, trigger: HTMLElement) => void;
}

const ANNOUNCEMENTS: Record<Announcement, UiKey> = {
  opened: "stepup_opened",
  done: "stepup_done",
  blocked: "stepup_incomplete",
  request: "stepup_incomplete",
  closed: "stepup_incomplete",
  timeout: "stepup_incomplete",
  exchange: "stepup_incomplete",
  no_mfa: "stepup_incomplete",
  retry: "stepup_retry_failed",
};

const Context = createContext<StepUpApi | null>(null);

export function useStepUp(): StepUpApi {
  const api = useContext(Context);
  if (api === null) throw new Error("useStepUp fuera de StepUpProvider");
  return api;
}

interface Props {
  readonly session: SessionInfo | null;
  readonly env: StepUpEnv;
  readonly children: ReactNode;
}

export function StepUpProvider({ session, env, children }: Props) {
  const pending = useRef<StepUpAction<unknown> | null>(null);
  const trigger = useRef<HTMLElement>(document.body);
  const focusPending = useRef(false);
  const [announcement, setAnnouncement] = useState<UiKey | null>(null);
  const [dialog, setDialog] = useState(false);
  const flowRef = useRef<StepUpFlow<unknown> | null>(null);
  flowRef.current ??= new StepUpFlow<unknown>({
    ownOrigin: env.ownOrigin,
    stepupRedirectUri: env.stepupRedirectUri,
    backend: env.backend,
    openWindow: env.openWindow,
    timers: env.timers,
    reportFailure: env.reportFailure,
    announce: (announced) => {
      setAnnouncement(ANNOUNCEMENTS[announced]);
    },
    // El control sigue deshabilitado hasta que React pinta el estado terminal: el foco vuelve en el efecto de abajo (NFR-U10-52).
    restoreFocus: () => {
      focusPending.current = true;
    },
    send: async (body) => (await (pending.current as StepUpAction<unknown>).send(body)) === "ok",
  });
  const flow = flowRef.current;
  const state = useSyncExternalStore(
    (listener) => flow.subscribe(listener),
    () => flow.state,
  );

  useEffect(() => {
    if (focusPending.current) {
      focusPending.current = false;
      trigger.current.focus();
    }
  });

  useEffect(() => {
    const onMessage = (event: Event): void => {
      flow.handleMessage(event as MessageEvent);
    };
    env.messageTarget.addEventListener("message", onMessage);
    return () => {
      env.messageTarget.removeEventListener("message", onMessage);
    };
  }, [flow, env.messageTarget]);

  const needsStepUp = session !== null && !recentMfa(session, env.now());
  const busy = state.phase === "opening" || state.phase === "waiting" || state.phase === "exchanging" || state.phase === "sending";

  const api: StepUpApi = {
    needsStepUp,
    busy,
    confirm: (action, element) => {
      pending.current = action as StepUpAction<unknown>;
      trigger.current = element;
      setAnnouncement(null);
      if (needsStepUp) {
        flow.start(action.body); // sincrono, dentro del clic: la ventana se abre aqui
        return;
      }
      void action.send(action.body).then((result) => {
        if (result === "mfa_required") setDialog(true);
      });
    },
  };

  return (
    <Context.Provider value={api}>
      {children}
      <p role="status" aria-live="polite">
        {announcement === null ? null : ui(announcement)}
      </p>
      <StepUpDialog
        open={dialog}
        onVerify={() => {
          setDialog(false);
          flow.start((pending.current as StepUpAction<unknown>).body); // sincrono, dentro del clic de «Verificar identidad»
        }}
        onCancel={() => {
          setDialog(false);
          trigger.current.focus();
        }}
      />
    </Context.Provider>
  );
}
