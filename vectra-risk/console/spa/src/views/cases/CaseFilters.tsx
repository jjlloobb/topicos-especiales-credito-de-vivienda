// `CaseFilters` (BR-U10-10): los campos de `CaseFilter` que van en la URL (estados, canal, fechas, «modelo congelado tras la
// recomendacion»). El valor de cada control sale de un conjunto cerrado; ninguno acepta texto libre.
import { CASE_STATES } from "@vectra/contracts";
import { Button } from "react-aria-components";
import type { CaseState } from "../../api/endpoints";
import { channelText, label, ui } from "../../i18n";
import { Choice } from "../shared/Choice";
import { DEFAULT_STATES, EMPTY_FILTER, type InboxFilter, KNOWN_CHANNELS } from "./filters";

interface Props {
  readonly filter: InboxFilter;
  readonly onChange: (filter: InboxFilter) => void;
}

export function CaseFilters({ filter, onChange }: Props) {
  const states = filter.states ?? DEFAULT_STATES;
  const change = (patch: Partial<InboxFilter>): void => {
    onChange({ ...filter, ...patch, page: 1 });
  };
  const toggle = (state: CaseState): void => {
    const next = states.includes(state) ? states.filter((s) => s !== state) : CASE_STATES.filter((s) => s === state || states.includes(s));
    const isDefault = next.length === DEFAULT_STATES.length && DEFAULT_STATES.every((s) => next.includes(s));
    change({ states: next.length === 0 || isDefault ? null : next });
  };
  return (
    <form
      aria-label={ui("filters_legend")}
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <fieldset>
        <legend>{ui("filter_states")}</legend>
        {CASE_STATES.map((state) => (
          <Choice
            key={state}
            type="checkbox"
            checked={states.includes(state)}
            onChange={() => {
              toggle(state);
            }}
            text={label("CASE_STATES", state)}
          />
        ))}
      </fieldset>
      <label htmlFor="filter-channel">{ui("filter_channel")}</label>
      <select
        id="filter-channel"
        value={filter.channel ?? ""}
        onChange={(event) => {
          change({ channel: event.target.value === "" ? null : event.target.value });
        }}
      >
        <option value="">{ui("filter_channel_all")}</option>
        {KNOWN_CHANNELS.map((channel) => (
          <option key={channel} value={channel}>
            {channelText(channel)}
          </option>
        ))}
      </select>
      <label htmlFor="filter-from">{ui("filter_created_from")}</label>
      <input
        id="filter-from"
        type="date"
        value={filter.createdFrom ?? ""}
        onChange={(event) => {
          change({ createdFrom: event.target.value === "" ? null : event.target.value });
        }}
      />
      <label htmlFor="filter-to">{ui("filter_created_to")}</label>
      <input
        id="filter-to"
        type="date"
        value={filter.createdTo ?? ""}
        onChange={(event) => {
          change({ createdTo: event.target.value === "" ? null : event.target.value });
        }}
      />
      <Choice
        type="checkbox"
        checked={filter.frozenAfter}
        onChange={(checked) => {
          change({ frozenAfter: checked });
        }}
        text={ui("filter_frozen")}
      />
      <Button
        onPress={() => {
          onChange(EMPTY_FILTER);
        }}
      >
        {ui("filter_clear")}
      </Button>
    </form>
  );
}
