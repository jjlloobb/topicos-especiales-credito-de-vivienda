// PoC del Paso 10: una pagina de OTRO origen (`localhost` frente a `127.0.0.1`) que tiene `window.opener` y envia un mensaje con el
// `state` y el `code` que le pasa la prueba. Sin la comprobacion de `event.origin`, la ventana principal lo aceptaria.
const query = new URL(location.href).searchParams;
(window.opener as Window).postMessage({ code: query.get("code"), state: query.get("state") }, "*");
