// `AttributeComparison`: la tabla comparativa del paquete de contexto de un congelamiento. Una fila por atributo y una columna por momento
// (validacion, antes, despues, ultimos 7 dias) con la disparidad agregada que YA trae el paquete (`aggregate` de cada atributo): aqui no se
// calcula ni se compara nada, solo se ponen lado a lado las cadenas del servidor. La fila del atributo disparador va primero, resaltada y
// con una insignia de texto, y muestra su limite de congelamiento (el de `implicated`). Una ventana en `sin_datos` dice «Sin datos», y un
// atributo sin agregado dice «Sin dato»: nunca un 0 ni una celda vacia (BR-U10-15).
import type { AttributeResult, FreezeRecord } from "../../api/endpoints";
import { labelOrRaw, safeDecimal, ui } from "../../i18n";
import { TableScroll } from "../shared/TableScroll";

type Context = FreezeRecord["context_package"];
type Moment = readonly AttributeResult[] | "sin_datos";

interface Props {
  readonly context: Context;
  /** El limite de congelamiento de cada atributo implicado (`freeze_lower_limit`), por nombre de atributo. */
  readonly limits: ReadonlyMap<string, string>;
}

const attributesOf = (moment: Context["before"]): Moment => (moment === "sin_datos" ? "sin_datos" : moment.attributes);

/** Los atributos que aparecen en algun momento, sin repetir: el disparador primero y los demas en el orden en que llegan. */
export function comparedAttributes(moments: readonly Moment[], trigger: string): string[] {
  const seen: string[] = [];
  for (const moment of moments) {
    if (moment === "sin_datos") continue;
    for (const attribute of moment) if (!seen.includes(attribute.attribute)) seen.push(attribute.attribute);
  }
  return seen.includes(trigger) ? [trigger, ...seen.filter((attribute) => attribute !== trigger)] : seen;
}

function MomentCell({ moment, attribute }: { readonly moment: Moment; readonly attribute: string }) {
  if (moment === "sin_datos") return <td className="num cell-missing">{ui("freeze_compare_window_missing")}</td>;
  const aggregate = moment.find((candidate) => candidate.attribute === attribute)?.aggregate ?? null;
  return aggregate === null ? <td className="num cell-missing">{ui("no_value")}</td> : <td className="num">{safeDecimal(aggregate)}</td>;
}

export function AttributeComparison({ context, limits }: Props) {
  const moments: readonly Moment[] = [context.initial_disparity.attributes, attributesOf(context.before), attributesOf(context.after), attributesOf(context.last_7_days)];
  const trigger: string = context.trigger_attribute;
  const attributes = comparedAttributes(moments, trigger);
  if (attributes.length === 0) return <p>{ui("freeze_no_data")}</p>;
  return (
    <>
      <TableScroll name={ui("freeze_compare_title")}>
        <table>
          <caption>{ui("freeze_compare_caption")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("freeze_compare_col_attribute")}</th>
              <th scope="col" className="num">{ui("freeze_compare_col_validation")}</th>
              <th scope="col" className="num">{ui("freeze_section_before")}</th>
              <th scope="col" className="num">{ui("freeze_section_after")}</th>
              <th scope="col" className="num">{ui("freeze_section_last7")}</th>
              <th scope="col" className="num">{ui("freeze_compare_col_limit")}</th>
            </tr>
          </thead>
          <tbody>
            {attributes.map((attribute) => {
              const limit = limits.get(attribute);
              return (
                <tr key={attribute} className={attribute === trigger ? "row-trigger" : undefined}>
                  <th scope="row">
                    <span className="row-head">
                      {labelOrRaw("ATTRIBUTES", attribute)}
                      {attribute === trigger ? <span className="badge badge-warn">{ui("col_trigger")}</span> : null}
                    </span>
                  </th>
                  {moments.map((moment, index) => (
                    <MomentCell key={index} moment={moment} attribute={attribute} />
                  ))}
                  {limit === undefined ? <td className="num cell-missing">{ui("no_value")}</td> : <td className="num">{safeDecimal(limit)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
      <p className="hint">{ui("freeze_compare_hint")}</p>
    </>
  );
}
