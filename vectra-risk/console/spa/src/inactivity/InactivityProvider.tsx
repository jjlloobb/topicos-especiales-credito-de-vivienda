// `InactivityProvider` (BR-U10-20): un contador de la sesion compartido entre pestanas y su aviso. `onLogout` es el logout de `auth`.
import { type ReactNode, useEffect, useRef, useState } from "react";
import { InactivityDialog } from "./InactivityDialog";
import { attachActivity, CHANNEL_NAME, type ChannelLike, InactivityMonitor, type MonitorDeps } from "./monitor";

export interface InactivityEnv {
  readonly now: MonitorDeps["now"];
  readonly setTimeout: MonitorDeps["setTimeout"];
  readonly clearTimeout: MonitorDeps["clearTimeout"];
  readonly createChannel: () => ChannelLike;
  readonly target: Pick<EventTarget, "addEventListener" | "removeEventListener">;
}

export const browserInactivityEnv: InactivityEnv = {
  now: () => Date.now(),
  setTimeout: (handler, ms) => window.setTimeout(handler, ms),
  clearTimeout: (handle) => {
    window.clearTimeout(handle as number);
  },
  createChannel: () => new BroadcastChannel(CHANNEL_NAME),
  target: document,
};

interface Props {
  readonly env: InactivityEnv;
  readonly onLogout: () => void;
  readonly children: ReactNode;
}

export function InactivityProvider({ env, onLogout, children }: Props) {
  const [warning, setWarning] = useState(false);
  const monitor = useRef<InactivityMonitor | null>(null);
  const logout = useRef(onLogout);
  logout.current = onLogout;

  useEffect(() => {
    const channel = env.createChannel();
    const created = new InactivityMonitor({
      now: env.now,
      setTimeout: env.setTimeout,
      clearTimeout: env.clearTimeout,
      channel,
      onWarning: () => {
        setWarning(true);
      },
      onResume: () => {
        setWarning(false);
      },
      onLogout: () => {
        setWarning(false);
        logout.current();
      },
    });
    monitor.current = created;
    const detach = attachActivity(env.target, created);
    return () => {
      detach();
      created.dispose();
      channel.close();
    };
  }, [env]);

  return (
    <>
      {children}
      <InactivityDialog
        open={warning}
        onContinue={() => {
          (monitor.current as InactivityMonitor).activity();
        }}
      />
    </>
  );
}
