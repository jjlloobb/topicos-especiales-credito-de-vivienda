// La tabla de celdas de disparidad que comparten el paquete de contexto de un congelamiento y, cuando entre, el dashboard (BR-U10-15):
// una celda con «muestra insuficiente» se muestra asi, **nunca** como 0 ni vacia, y su tasa no se calcula en el cliente (la tasa es la
// cadena del servidor, formateada con `Intl`). `BiasDashboard` y `GrafanaEmbed` no se crean (diferidos, P-14).
import type { AttributeResult, DisparityResult } from "../../api/endpoints";
import { formatDay, label, safeDecimal, ui } from "../../i18n";

type Cell = AttributeResult["cells"][number];

/** El texto de una celda: «muestra insuficiente» sin tasa, o la tasa del servidor. */
export function cellText(cell: Cell): string {
  if (cell.status === "muestra_insuficiente") return ui("cell_insufficient");
  return cell.rate == null ? ui("cell_no_rate") : safeDecimal(cell.rate);
}

export function AttributeTable({ attribute }: { readonly attribute: AttributeResult }) {
  return (
    <section>
      <h5>{ui("disparity_attribute", { attribute: label("ATTRIBUTES", attribute.attribute) })}</h5>
      {attribute.aggregate == null ? null : <p>{ui("disparity_aggregate", { value: safeDecimal(attribute.aggregate) })}</p>}
      <table>
        <caption>{label("ATTRIBUTES", attribute.attribute)}</caption>
        <thead>
          <tr>
            <th scope="col">{ui("disparity_col_group")}</th>
            <th scope="col">{ui("disparity_col_band")}</th>
            <th scope="col">{ui("disparity_col_n")}</th>
            <th scope="col">{ui("disparity_col_rate")}</th>
          </tr>
        </thead>
        <tbody>
          {attribute.cells.map((cell) => (
            <tr key={`${cell.group}|${cell.band}`}>
              <td>{cell.group}</td>
              <td>{label("BANDS", cell.band)}</td>
              <td>{cell.n}</td>
              <td className={cell.status === "muestra_insuficiente" ? "cell-insufficient" : undefined}>{cellText(cell)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Una ventana de disparidad (`before`, `after`, `last_7_days`) o «sin datos» cuando el servidor no la tiene. */
export function DisparityWindow({ title, result }: { readonly title: string; readonly result: DisparityResult | "sin_datos" }) {
  return (
    <section>
      <h4>{title}</h4>
      {result === "sin_datos" ? (
        <p>{ui("freeze_no_data")}</p>
      ) : (
        <>
          <p>{ui("freeze_window_range", { from: formatDay(result.window_from), to: formatDay(result.window_to) })}</p>
          {result.attributes.map((attribute) => (
            <AttributeTable key={attribute.attribute} attribute={attribute} />
          ))}
        </>
      )}
    </section>
  );
}
