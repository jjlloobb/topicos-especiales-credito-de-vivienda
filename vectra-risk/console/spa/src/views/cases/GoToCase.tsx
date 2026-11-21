// «Ir al caso» (BR-U10-10): un `case_id` (UUID, que no es un dato personal) abre el detalle. No hay busqueda por nombre: pondria el nombre
// en la URL, el historial y los logs de acceso (revision del FD de U10, A3).
import { useState } from "react";
import { Button } from "react-aria-components";
import { useNavigate } from "react-router";
import { ui } from "../../i18n";
import { extractCaseId } from "./filters";

export function GoToCase() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault();
        const id = extractCaseId(value); // el identificador, o la direccion del caso pegada entera
        if (id !== null) void navigate(`/casos/${id}`);
        else setInvalid(true);
      }}
    >
      <div className="field">
        <label htmlFor="go-to-case">{ui("go_to_case_label")}</label>
        <input
          id="go-to-case"
          type="text"
          value={value}
          aria-invalid={invalid}
          aria-describedby={invalid ? "go-to-case-hint go-to-case-error" : "go-to-case-hint"}
          spellCheck={false}
          autoComplete="off"
          onChange={(event) => {
            setValue(event.target.value);
            setInvalid(false);
          }}
        />
      </div>
      <Button type="submit">{ui("go_to_case_button")}</Button>
      <p className="hint" id="go-to-case-hint">
        {ui("go_to_case_hint")}
      </p>
      {invalid ? (
        <p className="field-error" role="alert" id="go-to-case-error">
          {ui("go_to_case_invalid")}
        </p>
      ) : null}
    </form>
  );
}
