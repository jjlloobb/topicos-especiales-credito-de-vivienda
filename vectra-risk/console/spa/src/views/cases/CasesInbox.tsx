// `CasesInbox` (BR-U10-10, 11; US-107): la bandeja. Los filtros de `CaseFilter` viven en la URL (sin datos del solicitante); por omision,
// todos los estados menos `vencido`. Se vuelve a pedir cada 15 s mientras la pestana esta visible. El solicitante se identifica solo con
// `applicant_display`. «Ir al caso» abre el detalle por `case_id`. Encima de la tabla van el total de casos de la consulta (`total`, que ya
// trae la API) y los chips de un estado; debajo, la paginacion («Pagina X de Y», primera y ultima). Los chips no llevan numero: la API no da
// el total por estado.
import { useState } from "react";
import { Button } from "react-aria-components";
import { Link, useSearchParams } from "react-router";
import { useCases } from "../../api/hooks";
import { channelText, formatCount, formatDate, label, safeDecimal, ui } from "../../i18n";
import { IconFilter, IconFirst, IconLast, IconNext, IconOpen, IconPrevious } from "../shared/icons";
import { CopyButton } from "../shared/CopyButton";
import { ProblemMessage } from "../shared/ProblemMessage";
import { TableScroll } from "../shared/TableScroll";
import { TableSkeleton } from "../shared/TableSkeleton";
import { CaseFilters } from "./CaseFilters";
import { CaseStateBadge } from "./CaseStateBadge";
import { EMPTY_FILTER, type InboxFilter, MAX_PAGE, PAGE_SIZE, parseFilter, shortCaseId, toQuery, toSearchParams } from "./filters";
import { GoToCase } from "./GoToCase";
import { QuickStates } from "./QuickStates";

/** Un filtro «avanzado» (los de «Mas filtros») esta activo: canal, fechas, «solo congelados» o una combinacion de estados que no es un chip. */
export function hasAdvancedFilter(filter: InboxFilter): boolean {
  return filter.channel !== null || filter.createdFrom !== null || filter.createdTo !== null || filter.frozenAfter || (filter.states !== null && filter.states.length !== 1);
}

/** Cuantos filtros avanzados hay activos (lo que «Mas filtros» dice cuando esta cerrado): canal, cada fecha, «solo congelados» y una combinacion de estados. */
export function advancedFilterCount(filter: InboxFilter): number {
  return [filter.channel !== null, filter.createdFrom !== null, filter.createdTo !== null, filter.frozenAfter, filter.states !== null && filter.states.length !== 1].filter(Boolean).length;
}

/** Hay algun filtro puesto (un chip de estado cuenta): «Quitar los filtros» tiene algo que quitar. */
export function hasAnyFilter(filter: InboxFilter): boolean {
  return filter.states !== null || advancedFilterCount(filter) > 0;
}

/** Con mas paginas que estas, la paginacion ofrece «Ir a la pagina» (con pocas, los cuatro botones bastan y el campo solo estorba). */
export const PAGE_JUMP_FROM = 6;

/** «Ir a la pagina»: un numero entre 1 y `pages`. Solo cambia `page` del filtro (la misma consulta que «Pagina siguiente»). */
function PageJump({ pages, onGo }: { readonly pages: number; readonly onGo: (page: number) => void }) {
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  return (
    <form
      className="page-jump"
      onSubmit={(event) => {
        event.preventDefault();
        const text = value.trim();
        const page = /^\d{1,5}$/.test(text) ? parseInt(text, 10) : 0;
        if (page >= 1 && page <= pages) {
          setValue("");
          onGo(page);
        } else setInvalid(true);
      }}
    >
      <label htmlFor="page-jump">{ui("page_jump_label")}</label>
      <input
        id="page-jump"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={value}
        aria-invalid={invalid}
        aria-describedby={invalid ? "page-jump-error" : undefined}
        onChange={(event) => {
          setValue(event.target.value);
          setInvalid(false);
        }}
      />
      <Button type="submit">{ui("page_jump_button")}</Button>
      {invalid ? (
        <p className="field-error" role="alert" id="page-jump-error">
          {ui("page_jump_invalid", { pages: formatCount(pages) })}
        </p>
      ) : null}
    </form>
  );
}

export function CasesInbox() {
  const [params, setParams] = useSearchParams();
  const filter = parseFilter(params);
  // «Mas filtros» empieza abierto solo si la URL ya trae un filtro avanzado; despues manda la persona (no se cierra solo al quitar el filtro).
  const [moreOpen, setMoreOpen] = useState(() => hasAdvancedFilter(filter));
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
  // `aria-busy` solo en la carga inicial (`isPending`) y al cambiar de filtro o de pagina (`isPlaceholderData`: aun se ve la pagina
  // anterior); el refresco de 15 s en segundo plano (`isFetching` con datos propios) no lo pone, para que no parpadee.
  const changing = query.isPlaceholderData;
  const advanced = advancedFilterCount(filter);
  // Una pagina mas alla de la ultima (un enlace viejo, o la lista se acorto): no es «sin resultados», y se dice a donde ir.
  const beyond = pages !== null && filter.page > pages;
  return (
    <section aria-busy={query.isPending || changing ? true : undefined}>
      <h2>{ui("view_cases")}</h2>
      <p className="hint">{ui("inbox_hint")}</p>
      <GoToCase />
      <QuickStates filter={filter} onChange={change} />
      <details
        className="more-filters"
        open={moreOpen}
        onToggle={(event) => {
          setMoreOpen(event.currentTarget.open);
        }}
      >
        <summary>
          <IconFilter />
          {ui("filters_more")}
          {advanced === 0 ? null : <span className="badge badge-info">{advanced === 1 ? ui("filters_active_one") : ui("filters_active", { count: formatCount(advanced) })}</span>}
        </summary>
        <CaseFilters filter={filter} onChange={change} />
      </details>
      {query.isPending ? (
        <>
          <p className="loading" role="status">{ui("loading")}</p>
          <TableSkeleton />
        </>
      ) : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined || total === null ? null : (
        <div className="result-bar">
          <p className="result-total">{ui("inbox_total", { total: formatCount(total) })}</p>
          {shown === 0 ? null : <p className="hint">{ui("inbox_range", { from: formatCount(first), to: formatCount(first + shown - 1) })}</p>}
        </div>
      )}
      {query.data === undefined ? null : query.data.items.length === 0 ? (
        <div className="empty">
          <p>{beyond ? ui("inbox_page_beyond", { pages: formatCount(pages) }) : ui("inbox_empty")}</p>
          {beyond ? (
            <Button
              onPress={() => {
                change({ ...filter, page: pages });
              }}
            >
              {ui("inbox_page_beyond_go")}
            </Button>
          ) : hasAnyFilter(filter) ? (
            <Button
              onPress={() => {
                change(EMPTY_FILTER);
              }}
            >
              {ui("inbox_empty_clear")}
            </Button>
          ) : null}
        </div>
      ) : (
        <TableScroll name={ui("view_cases")} tall busy={changing}>
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
              <th scope="col" className="col-case-id">{ui("col_case_id")}</th>
              <th scope="col">{ui("col_open")}</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((item) => (
              <tr key={item.case_id}>
                <td data-label={ui("col_applicant")}>{item.applicant_display}</td>
                <td data-label={ui("col_state")}>
                  <CaseStateBadge state={item.state} />
                </td>
                <td data-label={ui("col_channel")}>{channelText(item.channel)}</td>
                <td data-label={ui("col_created")}>{formatDate(item.created_at)}</td>
                <td data-label={ui("col_outcome")}>{item.outcome == null ? ui("no_outcome") : label("OUTCOMES", item.outcome)}</td>
                <td className="num" data-label={ui("col_score")}>{item.score == null ? ui("no_score") : safeDecimal(item.score)}</td>
                <td className="col-case-id" data-label={ui("col_case_id")}>
                  <span className="case-id-short">
                    <code title={item.case_id}>{shortCaseId(item.case_id)}</code>
                    <CopyButton value={item.case_id} label={ui("case_id_copy_of", { applicant: item.applicant_display })} />
                  </span>
                </td>
                <td className="cell-action">
                  <Link to={`/casos/${item.case_id}`} aria-label={ui("open_case", { applicant: item.applicant_display })}>
                    {ui("col_open")}
                    <IconOpen />
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
          <IconFirst />
          {ui("page_first")}
        </Button>
        <Button
          isDisabled={filter.page <= 1}
          onPress={() => {
            change({ ...filter, page: filter.page - 1 });
          }}
        >
          <IconPrevious />
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
          <IconNext />
        </Button>
        <Button
          isDisabled={pages === null || filter.page >= pages}
          onPress={() => {
            if (pages !== null) change({ ...filter, page: pages });
          }}
        >
          {ui("page_last")}
          <IconLast />
        </Button>
        {pages !== null && pages >= PAGE_JUMP_FROM ? (
          <PageJump
            pages={pages}
            onGo={(page) => {
              change({ ...filter, page });
            }}
          />
        ) : null}
      </nav>
    </section>
  );
}
