// El esqueleto de una tabla mientras llega su primera respuesta (`isPending`): unas filas grises, decorativas (`aria-hidden`). Quien usa un
// lector de pantalla oye el «Cargando…» de `role="status"` que la vista muestra al lado; el esqueleto no anade texto.
const ROWS = [0, 1, 2, 3, 4] as const;

export function TableSkeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      {ROWS.map((row) => (
        <div key={row} className="skeleton-row" />
      ))}
    </div>
  );
}
