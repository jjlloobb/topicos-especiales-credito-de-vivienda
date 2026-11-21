// `QuickStates`: un chip por estado para ver, con un clic, solo los casos de ese estado (por ejemplo, los «No disponible», que entre miles
// de casos no aparecen en la primera pagina). Es otra forma de escribir el mismo filtro `states` de la URL que las casillas de `CaseFilters`:
// no pide nada distinto a la API. Los chips no llevan numero porque `list_cases` no devuelve el total por estado. El chip elegido lleva
// `aria-pressed` y cada uno dice su estado con texto (el punto de color es decorativo).
import { CASE_STATES } from "@vectra/contracts";
import { Button } from "react-aria-components";
import { label, ui } from "../../i18n";
import type { InboxFilter } from "./filters";

interface Props {
  readonly filter: InboxFilter;
  readonly onChange: (filter: InboxFilter) => void;
}

export function QuickStates({ filter, onChange }: Props) {
  const only = filter.states !== null && filter.states.length === 1 ? (filter.states[0] ?? null) : null;
  return (
    <div className="chips" role="group" aria-labelledby="quick-states-label">
      <p className="chips-label" id="quick-states-label">
        {ui("quick_states_label")}
      </p>
      <Button
        className="chip"
        aria-pressed={filter.states === null}
        onPress={() => {
          onChange({ ...filter, states: null, page: 1 });
        }}
      >
        {ui("quick_states_default")}
      </Button>
      {CASE_STATES.map((state) => (
        <Button
          key={state}
          className="chip"
          aria-pressed={only === state}
          onPress={() => {
            onChange({ ...filter, states: [state], page: 1 });
          }}
        >
          <span className={`dot dot-${state}`} aria-hidden="true" />
          {label("CASE_STATES", state)}
        </Button>
      ))}
    </div>
  );
}
