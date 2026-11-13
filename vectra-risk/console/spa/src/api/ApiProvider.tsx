// El cliente de la API para las vistas: se crea una vez en `wiring` (con el token en memoria) y las vistas lo leen con `useApi`.
import { createContext, type ReactNode, useContext } from "react";
import type { ApiClient } from "./client";

const Context = createContext<ApiClient | null>(null);

export function ApiProvider({ api, children }: { readonly api: ApiClient; readonly children: ReactNode }) {
  return <Context.Provider value={api}>{children}</Context.Provider>;
}

export function useApi(): ApiClient {
  const api = useContext(Context);
  if (api === null) throw new Error("useApi fuera de ApiProvider");
  return api;
}
