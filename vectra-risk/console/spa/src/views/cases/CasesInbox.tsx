// `CasesInbox` (BR-U10-10, 11; US-107): la bandeja. Los filtros de `CaseFilter` viven en la URL (sin datos del solicitante); por omision,
// todos los estados menos `vencido`. Se vuelve a pedir cada 15 s mientras la pestana esta visible. El solicitante se identifica solo con
// `applicant_display`. «Ir al caso» abre el detalle por `case_id`. Encima de la tabla van el total de casos de la consulta (`total`, que ya
// trae la API) y los chips de un estado; debajo, la paginacion («Pagina X de Y», primera y ultima). Los chips no llevan numero: la API no da
// el total por estado.
import { Button } from "react-aria-components";
import { Link, useSearchParams } from "react-router";
import { useCases } from "../../api/hooks";
import { channelText, formatCount, formatDate, label, safeDecimal, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";
import { TableScroll } from "../shared/TableScroll";
import { CaseFilters } from "./CaseFilters";
import { CaseStateBadge } from "./CaseStateBadge";
import { type InboxFilter, MAX_PAGE, PAGE_SIZE, parseFilter, toQuery, toSearchParams } from "./filters";
import { GoToCase } from "./GoToCase";
import { QuickStates } from "./QuickStates";

export function CasesInbox() {
  const [params, setParams] = useSearchParams();
  const filter = parseFilter(params);
  const query = useCases(toQuery(filter));
  const change = (next: InboxFilter): void => {
    setParams(toSearchParams(next));
  };
  const total = query.data?.total ?? null;
  const hasNext = query.data !== undefined && (total === null ? query.data.items.length === PAGE_SIZE : filter.page * PAGE_SIZE < total);
  // Cuantas paginas hay: sale de `total` (la API) y del tamano de pagina; sin `total` no se sabe y solo se dice la pagina actual.
  const pages = total === null ? null : Math.min(MAX_PAGE, Math.max(1, Math.ceil(total / PAGE_SIZE)));
  const shown = query.data?.items.length ?? 0;
  const first = (filter.page - 1) * PAGE_SIZE + 1;
  // `aria-busy` solo en la carga inicial y al cambiar de filtro o de pagina (`isPending`: la consulta nueva aun no tiene datos); el refresco
  // de 15 s en segundo plano (`isFetching` con datos) no lo pone, para que no parpadee.
  return (
    <section aria-busy={query.isPending ? true : undefined}>
      <h2>{ui("view_cases")}</h2>
      <p className="hint">{ui("inbox_hint")}</p>
      <GoToCase />
      <QuickStates filter={filter} onChange={change} />
      <CaseFilters filter={filter} onChange={change} />
      {query.isPending ? <p className="loading" role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined || total === null ? null : (
        <div className="result-bar">
          <p className="result-total">{ui("inbox_total", { total: formatCount(total) })}</p>
          {shown === 0 ? null : <p className="hint">{ui("inbox_range", { from: formatCount(first), to: formatCount(first + shown - 1) })}</p>}
        </div>
      )}
      {query.data === undefined ? null : query.data.items.length === 0 ? (
        <p className="empty">{ui("inbox_empty")}</p>
      ) : (
        <TableScroll name={ui("view_cases")} tall>
        <table>
          <caption className="visually-hidden">{ui("view_cases")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("col_applicant")}</th>
              <th scope="col">{ui("col_state")}</th>
              <th scope="col">{ui("col_channel")}</th>
              <th scope="col">{ui("col_created")}</th>
              <th scope="col">{ui("col_outcome")}</th>
              <th scope="col" className="num">{ui("col_score")}</th>
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
                <td className="num">{item.score == null ? ui("no_score") : safeDecimal(item.score)}</td>
                <td>
                  <Link to={`/casos/${item.case_id}`} aria-label={ui("open_case", { applicant: item.applicant_display })}>
                    {ui("col_open")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableScroll>
      )}
      <nav className="pagination" aria-label={ui("pagination_label")}>
        <Button
          isDisabled={filter.page <= 1}
          onPress={() => {
            change({ ...filter, page: 1 });
          }}
        >
          {ui("page_first")}
        </Button>
        <Button
          isDisabled={filter.page <= 1}
          onPress={() => {
            change({ ...filter, page: filter.page - 1 });
          }}
        >
          {ui("page_previous")}
        </Button>
        <span className="pagination-current">
          {pages === null ? ui("page_current", { page: String(filter.page) }) : ui("page_of", { page: formatCount(filter.page), pages: formatCount(pages) })}
        </span>
        <Button
          isDisabled={!hasNext}
          onPress={() => {
            change({ ...filter, page: filter.page + 1 });
          }}
        >
          {ui("page_next")}
        </Button>
        <Button
          isDisabled={pages === null || filter.page >= pages}
          onPress={() => {
            if (pages !== null) change({ ...filter, page: pages });
          }}
        >
          {ui("page_last")}
        </Button>
      </nav>
    </section>
  );
}
