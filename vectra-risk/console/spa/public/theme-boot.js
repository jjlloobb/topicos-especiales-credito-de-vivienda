// El tema elegido, ANTES de la primera pintura (enmienda del 2026-11-21 a NFR-U10-51). Es un guion clasico del mismo origen, cargado en el
// <head> de `index.html` sin `defer` ni `async`: el navegador lo ejecuta antes de pintar nada, asi que quien eligio «Oscuro» no ve un instante
// en claro (ni al reves). La CSP de U2 (`script-src 'self'`) no admite el guion en linea que se usa habitualmente para esto; este archivo si.
// Solo lee UNA clave del almacenamiento local y pone `data-theme` en <html> si vale «light» u «dark»: la misma clave y los mismos valores que
// `src/preferences/storage.ts` (una prueba los ata). No escribe nada. `src/theme/theme.ts` toma el relevo cuando arranca la aplicacion.
(function () {
  try {
    var theme = window.localStorage.getItem("vectra.console.theme");
    if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
  } catch (error) {
    // Sin almacenamiento (modo privado, bloqueado): queda el tema del sistema.
  }
})();
