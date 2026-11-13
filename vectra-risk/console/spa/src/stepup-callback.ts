// Callback del step-up (BR-U10-06; P-U10-07): NO canjea el codigo, NO guarda nada y NO pide `config.json`. Solo entrega
// `{code, state}` a la ventana que la abrio, con `postMessage(msg, location.origin)`, y se cierra. Sin ventana de origen (la pagina
// se abrio suelta) no hace nada. Si la respuesta es un error (sin `code`), solo se cierra: la ventana principal ve el cierre.
export function runStepUpCallback(win: Window = window): void {
  const opener = win.opener as Window | null;
  if (opener === null) return;
  const query = new URL(win.location.href).searchParams;
  const code = query.get("code");
  const state = query.get("state");
  if (code !== null && state !== null) opener.postMessage({ code, state }, win.location.origin);
  win.close();
}
