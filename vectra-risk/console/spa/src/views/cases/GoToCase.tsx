// «Ir al caso» (BR-U10-10): un `case_id` (UUID, que no es un dato personal) abre el detalle. No hay busqueda por nombre: pondria el nombre
// en la URL, el historial y los logs de acceso (revision del FD de U10, A3).
import { useState } from "react";
import { Button } from "react-aria-components";
import { useNavigate } from "react-router";
import { ui } from "../../i18n";
import { isCaseId } from "./filters";

export function GoToCase() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const id = value.trim();
        if (isCaseId(id)) void navigate(`/casos/${id.toLowerCase()}`);
        else setInvalid(true);
      }}
    >
      <label htmlFor="go-to-case">{ui("go_to_case_label")}</label>
      <input
        id="go-to-case"
        type="text"
        value={value}
        aria-invalid={invalid}
        aria-describedby={invalid ? "go-to-case-error" : undefined}
        autoComplete="off"
        onChange={(event) => {
          setValue(event.target.value);
          setInvalid(false);
        }}
      />
      <Button type="submit">{ui("go_to_case_button")}</Button>
      {invalid ? (
        <p role="alert" id="go-to-case-error">
          {ui("go_to_case_invalid")}
        </p>
      ) : null}
    </form>
  );
}
