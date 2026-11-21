// La tabla de celdas de disparidad que comparten el paquete de contexto de un congelamiento y, cuando entre, el dashboard (BR-U10-15):
// una celda con «muestra insuficiente» se muestra asi, **nunca** como 0 ni vacia, y su tasa no se calcula en el cliente (la tasa es la
// cadena del servidor, formateada con `Intl`). `BiasDashboard` y `GrafanaEmbed` no se crean (diferidos, P-14).
// En una ventana, las tablas por grupo y banda van plegadas (`<details>`): el resumen por atributo esta en la tabla comparativa del paquete.
import type { AttributeResult, DisparityResult } from "../../api/endpoints";
import { formatDay, label, safeDecimal, ui } from "../../i18n";
import { TableScroll } from "../shared/TableScroll";

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
      <TableScroll name={label("ATTRIBUTES", attribute.attribute)}>
      <table>
        <caption>{label("ATTRIBUTES", attribute.attribute)}</caption>
        <thead>
          <tr>
            <th scope="col">{ui("disparity_col_group")}</th>
            <th scope="col">{ui("disparity_col_band")}</th>
            <th scope="col" className="num">{ui("disparity_col_n")}</th>
            <th scope="col" className="num">{ui("disparity_col_rate")}</th>
          </tr>
        </thead>
        <tbody>
          {attribute.cells.map((cell) => (
            <tr key={`${cell.group}|${cell.band}`}>
              <td>{cell.group}</td>
              <td>{label("BANDS", cell.band)}</td>
              <td className="num">{cell.n}</td>
              <td className={cell.status === "muestra_insuficiente" ? "num cell-insufficient" : "num"}>{cellText(cell)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </TableScroll>
    </section>
  );
}

interface WindowProps {
  readonly title: string;
  readonly result: DisparityResult | "sin_datos";
  /** Una frase que explica por que la ventana puede no tener datos (se muestra junto a «sin datos»). */
  readonly emptyReason?: string;
  /** `true`: el detalle por grupo y banda empieza desplegado. */
  readonly defaultOpen?: boolean;
}

/** Una ventana de disparidad (`before`, `after`, `last_7_days`) o «sin datos» cuando el servidor no la tiene. */
export function DisparityWindow({ title, result, emptyReason, defaultOpen = false }: WindowProps) {
  return (
    <section>
      <h4>{title}</h4>
      {result === "sin_datos" ? (
        <>
          <p>{ui("freeze_no_data")}</p>
          {emptyReason === undefined ? null : <p className="hint">{emptyReason}</p>}
        </>
      ) : (
        <>
          <p>{ui("freeze_window_range", { from: formatDay(result.window_from), to: formatDay(result.window_to) })}</p>
          <details open={defaultOpen}>
            <summary>{ui("disparity_detail_toggle")}</summary>
            {result.attributes.map((attribute) => (
              <AttributeTable key={attribute.attribute} attribute={attribute} />
            ))}
          </details>
        </>
      )}
    </section>
  );
}
