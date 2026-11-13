// `CasesInbox` (BR-U10-10, 11; US-107): la bandeja. Los filtros de `CaseFilter` viven en la URL (sin datos del solicitante); por omision,
// todos los estados menos `vencido`. Se vuelve a pedir cada 15 s mientras la pestana esta visible. El solicitante se identifica solo con
// `applicant_display`. «Ir al caso» abre el detalle por `case_id`.
import { Button } from "react-aria-components";
import { Link, useSearchParams } from "react-router";
import { useCases } from "../../api/hooks";
import { channelText, formatDate, label, safeDecimal, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";
import { CaseFilters } from "./CaseFilters";
import { CaseStateBadge } from "./CaseStateBadge";
import { type InboxFilter, PAGE_SIZE, parseFilter, toQuery, toSearchParams } from "./filters";
import { GoToCase } from "./GoToCase";

export function CasesInbox() {
  const [params, setParams] = useSearchParams();
  const filter = parseFilter(params);
  const query = useCases(toQuery(filter));
  const change = (next: InboxFilter): void => {
    setParams(toSearchParams(next));
  };
  const total = query.data?.total ?? null;
  const hasNext = query.data !== undefined && (total === null ? query.data.items.length === PAGE_SIZE : filter.page * PAGE_SIZE < total);
  return (
    <section>
      <h2>{ui("view_cases")}</h2>
      <p>{ui("inbox_hint")}</p>
      <GoToCase />
      <CaseFilters filter={filter} onChange={change} />
      {query.isPending ? <p role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined ? null : query.data.items.length === 0 ? (
        <p>{ui("inbox_empty")}</p>
      ) : (
        <table>
          <caption>{ui("view_cases")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("col_applicant")}</th>
              <th scope="col">{ui("col_state")}</th>
              <th scope="col">{ui("col_channel")}</th>
              <th scope="col">{ui("col_created")}</th>
              <th scope="col">{ui("col_outcome")}</th>
              <th scope="col">{ui("col_score")}</th>
              <th scope="col">{ui("col_open")}</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((item) => (
              <tr key={item.case_id}>
                <td>{item.applicant_display}</td>
                <td>
                  <CaseStateBadge state={item.state} />
                </td>
                <td>{channelText(item.channel)}</td>
                <td>{formatDate(item.created_at)}</td>
                <td>{item.outcome == null ? ui("no_outcome") : label("OUTCOMES", item.outcome)}</td>
                <td>{item.score == null ? ui("no_score") : safeDecimal(item.score)}</td>
                <td>
                  <Link to={`/casos/${item.case_id}`} aria-label={ui("open_case", { applicant: item.applicant_display })}>
                    {ui("col_open")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <nav aria-label={ui("pagination_label")}>
        <Button
          isDisabled={filter.page <= 1}
          onPress={() => {
            change({ ...filter, page: filter.page - 1 });
          }}
        >
          {ui("page_previous")}
        </Button>
        <span>{ui("page_current", { page: String(filter.page) })}</span>
        <Button
          isDisabled={!hasNext}
          onPress={() => {
            change({ ...filter, page: filter.page + 1 });
          }}
        >
          {ui("page_next")}
        </Button>
      </nav>
    </section>
  );
}
