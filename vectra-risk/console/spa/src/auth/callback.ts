// `/callback` (BR-U10-05): la pagina de retorno del login. Segun quien la abrio entrega la respuesta a la ventana principal con el
// protocolo de `oidc-client-ts` (que valida origen y ventana): una ventana emergente (login interactivo) o un iframe (login
// silencioso, `prompt=none`). Abierta suelta, no hay nada que entregar: limpia la URL (sin `code` ni `state`).
export interface CallbackManager {
  signinPopupCallback(): Promise<void>;
  signinSilentCallback(): Promise<void>;
}

export type CallbackKind = "popup" | "silent" | "stray";

export async function handleAuthCallback(manager: CallbackManager, win: Window = window): Promise<CallbackKind> {
  if (win.opener !== null) {
    await manager.signinPopupCallback();
    return "popup";
  }
  if (win.parent !== win) {
    await manager.signinSilentCallback();
    return "silent";
  }
  win.history.replaceState(null, "", "/");
  return "stray";
}
