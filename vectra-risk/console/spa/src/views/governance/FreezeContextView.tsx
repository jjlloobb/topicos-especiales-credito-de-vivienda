// `FreezeContextView` (BR-U10-13, 15; US-304, US-305): el paquete de contexto completo de un congelamiento (antes, despues, ultimos 7 dias,
// atributo disparador, grupos y bandas implicados, fuentes de datos, disparidad de validacion e historial de resoluciones) y, para resolverlo,
// `ResolveFrozenDialog`. Siempre lleva el `disclaimer` «mide y alerta, no certifica» (P-4 (a): un texto propio del catalogo, igual a
// `DISCLAIMER` de U9), tambien con `before = "sin_datos"`, cargando o con error. Solo `cumplimiento` (C03).
// Orden de lectura: primero el estado («Resolucion pendiente»), el resumen y la accion de resolver; despues la tabla comparativa por atributo
// (con el disparador resaltado y su limite) y los grupos y bandas implicados; y el detalle por grupo y banda de cada ventana, plegado.
import { useState } from "react";
import { Button } from "react-aria-components";
import { Link, useParams } from "react-router";
import type { FreezeRecord } from "../../api/endpoints";
import { useFreeze } from "../../api/hooks";
import { formatDate, formatDay, groupText, label, labelOrRaw, safeDecimal, ui } from "../../i18n";
import { AttributeTable, DisparityWindow } from "../bias/DisparityTables";
import { Coded } from "../shared/Coded";
import { IconBack, IconSuccess } from "../shared/icons";
import { ProblemMessage } from "../shared/ProblemMessage";
import { TableScroll } from "../shared/TableScroll";
import { AttributeComparison } from "./AttributeComparison";
import { ResolveFrozenDialog } from "./ResolveFrozenDialog";

interface Implicated {
  readonly attribute: string;
  readonly limit: string;
  /** `pair`: los dos grupos entre los que esta la diferencia (`extreme_pair`), si el paquete los trae con esa forma. */
  readonly bands: readonly { readonly band: string; readonly difference: string; readonly pair: readonly [string, string] | null }[];
}

const pairOf = (value: unknown): readonly [string, string] | null =>
  Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && typeof value[1] === "string" ? [value[0], value[1]] : null;

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** Un elemento de `implicated` (BR-U9-15): atributo, limite y bandas. Si no tiene esa forma se muestra como JSON, nunca se descarta. */
export function readImplicated(value: unknown): Implicated | null {
  if (!isRecord(value) || typeof value["attribute"] !== "string" || typeof value["freeze_lower_limit"] !== "string" || !Array.isArray(value["bands"])) return null;
  const bands: { band: string; difference: string; pair: readonly [string, string] | null }[] = [];
  for (const raw of value["bands"] as unknown[]) {
    if (!isRecord(raw) || typeof raw["band"] !== "string" || typeof raw["difference"] !== "string") return null;
    bands.push({ band: raw["band"], difference: raw["difference"], pair: pairOf(raw["extreme_pair"]) });
  }
  return { attribute: value["attribute"], limit: value["freeze_lower_limit"], bands };
}

type Resolution = FreezeRecord["resolutions"][number];

/** La ultima resolucion registrada (la de `recorded_at` mas reciente; el orden en que llegan no se da por supuesto), o `null` si no hay. */
export function latestResolution(resolutions: readonly Resolution[]): Resolution | null {
  return resolutions.reduce<Resolution | null>((latest, candidate) => (latest === null || Date.parse(candidate.recorded_at) >= Date.parse(latest.recorded_at) ? candidate : latest), null);
}

export function FreezeContextView() {
  const { freezeId } = useParams();
  const query = useFreeze(freezeId ?? "");
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState(false);
  const record = query.data;
  const context = record?.context_package;
  // El limite de congelamiento de cada atributo implicado, para la tabla comparativa (los elementos sin la forma esperada no aportan limite).
  const limits = new Map<string, string>();
  for (const raw of context?.implicated ?? []) {
    const item = readImplicated(raw);
    if (item !== null) limits.set(item.attribute, item.limit);
  }
  const latest = latestResolution(record?.resolutions ?? []);
  return (
    <section>
      <h2>{ui("freeze_context_title")}</h2>
      <p className="disclaimer">{ui("bias_disclaimer")}</p>
      <Link to="/congelamientos">
        <IconBack />
        {ui("view_freezes")}
      </Link>
      {query.isPending ? <p className="loading" role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {record === undefined || context === undefined ? null : (
        <>
          <div className="card hero" aria-busy={query.isFetching ? true : undefined}>
            <p className="hero-status">
              <span className={latest === null ? "badge badge-pending" : "badge badge-ok"}>
                {latest === null ? ui("freeze_status_pending") : ui("freeze_status_resolved")}
              </span>
              {latest === null ? null : (
                <strong className="hero-latest">
                  {ui("freeze_last_resolution", { action: label("RESOLUTION_ACTIONS", latest.action), at: formatDate(latest.recorded_at) })}
                </strong>
              )}
            </p>
            <ul className="facts">
              <li>{ui("freeze_summary_model", { id: record.model_version_id })}</li>
              <li>{ui("freeze_summary_frozen", { at: formatDate(record.frozen_at) })}</li>
              <li className="fact-key">{ui("freeze_summary_trigger", { attribute: label("ATTRIBUTES", context.trigger_attribute) })}</li>
              <li>
                {ui("freeze_summary_window", {
                  days: String(context.window_days),
                  start: formatDay(context.window_start),
                  threshold: safeDecimal(context.threshold_pp),
                  n: String(context.n_min),
                })}
              </li>
              <li>
                {ui("freeze_summary_volume", { total: String(context.affected_volume.total), favorable: String(context.affected_volume.favorable) })}
              </li>
              {context.truncated ? <li className="fact-warn">{ui("freeze_truncated")}</li> : null}
            </ul>
            {resolved ? (
              <p className="notice-ok" role="status">
                <IconSuccess />
                {ui("freeze_resolution_done")}
              </p>
            ) : null}
            {latest === null ? null : (
              <p className="hint" id="resolve-again-hint">
                {ui("freeze_resolve_again_hint")}
              </p>
            )}
            <div className="actions actions-end">
              <Button
                className="button-primary"
                aria-describedby={latest === null ? undefined : "resolve-again-hint"}
                onPress={() => {
                  setResolved(false); // el aviso de la resolucion anterior no vale para la nueva
                  setResolving(true);
                }}
              >
                {ui("resolve_open")}
              </Button>
            </div>
          </div>
          <section>
            <h4>{ui("freeze_compare_title")}</h4>
            <AttributeComparison context={context} limits={limits} />
          </section>
          <section>
            <h4>{ui("freeze_section_implicated")}</h4>
            {context.implicated.length === 0 ? (
              <>
                <p>{ui("freeze_list_empty")}</p>
                <p className="hint">{ui("freeze_implicated_empty_why")}</p>
              </>
            ) : (
              context.implicated.map((raw, index) => {
                const item = readImplicated(raw);
                if (item === null) {
                  return (
                    <p key={index}>
                      <code>{JSON.stringify(raw)}</code>
                    </p>
                  );
                }
                const caption = ui("freeze_implicated_item", { attribute: labelOrRaw("ATTRIBUTES", item.attribute), limit: safeDecimal(item.limit) });
                return (
                  <TableScroll key={index} name={caption}>
                    <table>
                      <caption>{caption}</caption>
                      <thead>
                        <tr>
                          <th scope="col">{ui("disparity_col_band")}</th>
                          <th scope="col">{ui("freeze_implicated_col_groups")}</th>
                          <th scope="col" className="num">{ui("freeze_implicated_col_difference")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.bands.map((band) => (
                          <tr key={band.band}>
                            <th scope="row" data-label={ui("disparity_col_band")}>
                              <Coded text={labelOrRaw("BANDS", band.band)} code={band.band} />
                            </th>
                            {band.pair === null ? (
                              <td className="cell-missing" data-label={ui("freeze_implicated_col_groups")}>{ui("no_value")}</td>
                            ) : (
                              <td data-label={ui("freeze_implicated_col_groups")} title={band.pair.join(", ")}>
                                {ui("freeze_implicated_pair", { first: groupText(band.pair[0]), second: groupText(band.pair[1]) })}
                              </td>
                            )}
                            <td className="num" data-label={ui("freeze_implicated_col_difference")}>{safeDecimal(band.difference)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TableScroll>
                );
              })
            )}
          </section>
          <DisparityWindow title={ui("freeze_section_before")} result={context.before} emptyReason={ui("freeze_before_missing_why")} />
          <DisparityWindow title={ui("freeze_section_after")} result={context.after} emptyReason={ui("freeze_window_missing_why")} defaultOpen />
          <DisparityWindow title={ui("freeze_section_last7")} result={context.last_7_days} emptyReason={ui("freeze_window_missing_why")} />
          <section>
            <h4>{ui("freeze_section_initial")}</h4>
            {context.initial_disparity.attributes.length === 0 ? (
              <>
                <p>{ui("freeze_no_data")}</p>
                <p className="hint">{ui("freeze_initial_empty_why")}</p>
              </>
            ) : (
              <details>
                <summary>{ui("disparity_detail_toggle")}</summary>
                {context.initial_disparity.attributes.map((attribute) => (
                  <AttributeTable key={attribute.attribute} attribute={attribute} />
                ))}
              </details>
            )}
          </section>
          <section>
            <h4>{ui("freeze_section_sources")}</h4>
            {context.data_sources.length === 0 ? (
              <>
                <p>{ui("freeze_list_empty")}</p>
                <p className="hint">{ui("freeze_sources_empty_why")}</p>
              </>
            ) : (
              <ul>
                {context.data_sources.map((raw, index) => {
                  const source = isRecord(raw) && typeof raw["ds_id"] === "string" && typeof raw["name"] === "string" ? raw : null;
                  return (
                    <li key={index}>{source === null ? <code>{JSON.stringify(raw)}</code> : ui("freeze_source_item", { id: String(source["ds_id"]), name: String(source["name"]) })}</li>
                  );
                })}
              </ul>
            )}
          </section>
          <section>
            <h4>{ui("freeze_section_history")}</h4>
            {record.resolutions.length === 0 ? (
              <p>{ui("freeze_no_history")}</p>
            ) : (
              <ul>
                {record.resolutions.map((resolution) => (
                  <li key={`${resolution.action}|${resolution.recorded_at}`}>
                    {ui("freeze_history_item", { action: label("RESOLUTION_ACTIONS", resolution.action), at: formatDate(resolution.recorded_at) })}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <ResolveFrozenDialog
            modelVersionId={record.model_version_id}
            freezeId={record.freeze_id}
            isOpen={resolving}
            onClose={() => {
              setResolving(false);
            }}
            onResolved={() => {
              setResolved(true);
              setResolving(false);
            }}
          />
        </>
      )}
    </section>
  );
}
