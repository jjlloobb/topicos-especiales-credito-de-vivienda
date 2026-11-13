// `FreezeContextView` (BR-U10-13, 15; US-304, US-305): el paquete de contexto completo de un congelamiento (antes, despues, ultimos 7 dias,
// atributo disparador, grupos y bandas implicados, fuentes de datos, disparidad de validacion e historial de resoluciones) y, para resolverlo,
// `ResolveFrozenDialog`. Siempre lleva el `disclaimer` «mide y alerta, no certifica» (P-4 (a): un texto propio del catalogo, igual a
// `DISCLAIMER` de U9), tambien con `before = "sin_datos"`, cargando o con error. Solo `cumplimiento` (C03).
import { useState } from "react";
import { Button } from "react-aria-components";
import { Link, useParams } from "react-router";
import { useFreeze } from "../../api/hooks";
import { formatDate, formatDay, label, labelOrRaw, safeDecimal, ui } from "../../i18n";
import { AttributeTable, DisparityWindow } from "../bias/DisparityTables";
import { ProblemMessage } from "../shared/ProblemMessage";
import { ResolveFrozenDialog } from "./ResolveFrozenDialog";

interface Implicated {
  readonly attribute: string;
  readonly limit: string;
  readonly bands: readonly { readonly band: string; readonly difference: string }[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** Un elemento de `implicated` (BR-U9-15): atributo, limite y bandas. Si no tiene esa forma se muestra como JSON, nunca se descarta. */
export function readImplicated(value: unknown): Implicated | null {
  if (!isRecord(value) || typeof value["attribute"] !== "string" || typeof value["freeze_lower_limit"] !== "string" || !Array.isArray(value["bands"])) return null;
  const bands: { band: string; difference: string }[] = [];
  for (const raw of value["bands"] as unknown[]) {
    if (!isRecord(raw) || typeof raw["band"] !== "string" || typeof raw["difference"] !== "string") return null;
    bands.push({ band: raw["band"], difference: raw["difference"] });
  }
  return { attribute: value["attribute"], limit: value["freeze_lower_limit"], bands };
}

export function FreezeContextView() {
  const { freezeId } = useParams();
  const query = useFreeze(freezeId ?? "");
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState(false);
  const record = query.data;
  const context = record?.context_package;
  return (
    <section>
      <h2>{ui("freeze_context_title")}</h2>
      <p className="disclaimer">{ui("bias_disclaimer")}</p>
      <Link to="/congelamientos">{ui("view_freezes")}</Link>
      {query.isPending ? <p role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {record === undefined || context === undefined ? null : (
        <>
          <ul>
            <li>{ui("freeze_summary_model", { id: record.model_version_id })}</li>
            <li>{ui("freeze_summary_frozen", { at: formatDate(record.frozen_at) })}</li>
            <li>{ui("freeze_summary_trigger", { attribute: label("ATTRIBUTES", context.trigger_attribute) })}</li>
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
            {context.truncated ? <li>{ui("freeze_truncated")}</li> : null}
          </ul>
          <DisparityWindow title={ui("freeze_section_before")} result={context.before} />
          <DisparityWindow title={ui("freeze_section_after")} result={context.after} />
          <DisparityWindow title={ui("freeze_section_last7")} result={context.last_7_days} />
          <section>
            <h4>{ui("freeze_section_implicated")}</h4>
            {context.implicated.length === 0 ? (
              <p>{ui("freeze_list_empty")}</p>
            ) : (
              <ul>
                {context.implicated.map((raw, index) => {
                  const item = readImplicated(raw);
                  return (
                    <li key={index}>
                      {item === null ? (
                        <code>{JSON.stringify(raw)}</code>
                      ) : (
                        <>
                          {ui("freeze_implicated_item", { attribute: labelOrRaw("ATTRIBUTES", item.attribute), limit: safeDecimal(item.limit) })}
                          <ul>
                            {item.bands.map((band) => (
                              <li key={band.band}>{ui("freeze_implicated_band", { band: labelOrRaw("BANDS", band.band), difference: safeDecimal(band.difference) })}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
          <section>
            <h4>{ui("freeze_section_sources")}</h4>
            {context.data_sources.length === 0 ? (
              <p>{ui("freeze_list_empty")}</p>
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
            <h4>{ui("freeze_section_initial")}</h4>
            {context.initial_disparity.attributes.length === 0 ? (
              <p>{ui("freeze_no_data")}</p>
            ) : (
              context.initial_disparity.attributes.map((attribute) => <AttributeTable key={attribute.attribute} attribute={attribute} />)
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
          {resolved ? <p role="status">{ui("freeze_resolution_done")}</p> : null}
          <Button
            onPress={() => {
              setResolved(false); // el aviso de la resolucion anterior no vale para la nueva
              setResolving(true);
            }}
          >
            {ui("resolve_open")}
          </Button>
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
