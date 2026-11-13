// `ApplicationView` (BR-U10-11; US-109): la solicitud **sin** etiquetas de monitoreo (`sex`, `socioeconomic_stratum`: el contrato de la
// vista no las trae). `free_text` es texto plano: React lo escapa, y ESLint prohibe el HTML sin sanear en toda la SPA (`react/no-danger`).
import type { CaseDetail } from "../../api/endpoints";
import { channelText, safeDecimal, formatMoney, label, ui } from "../../i18n";

type Application = CaseDetail["application"];

export function ApplicationView({ application }: { readonly application: Application }) {
  const rows: [string, string][] = [
    [ui("application_channel"), channelText(application.channel)],
    [ui("application_income"), formatMoney(application.monthly_income)],
    [ui("application_other_income"), formatMoney(application.other_income)],
    [ui("application_obligations"), formatMoney(application.monthly_obligations)],
    [ui("application_requested"), formatMoney(application.requested_amount)],
    [ui("application_term"), String(application.term_months)],
    [ui("application_rate"), safeDecimal(application.proposed_rate_ea)],
    [ui("application_property_value"), formatMoney(application.property_value)],
    [ui("application_property_condition"), label("PROPERTY_CONDITIONS", application.property_condition)],
    [ui("application_employment"), label("EMPLOYMENT_TYPES", application.employment_type)],
    [ui("application_employment_months"), String(application.employment_months)],
    [ui("application_days_past_due"), String(application.max_days_past_due_12m)],
    [ui("application_department"), application.department_code],
  ];
  return (
    <section aria-labelledby="application-title">
      <h3 id="application-title">{ui("application_title")}</h3>
      <dl>
        {rows.map(([term, value]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{value}</dd>
          </div>
        ))}
        {application.free_text == null ? null : (
          <div>
            <dt>{ui("application_free_text")}</dt>
            <dd className="free-text">{application.free_text}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
