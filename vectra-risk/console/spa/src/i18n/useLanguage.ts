// El idioma dentro de React: el componente que lo usa se vuelve a pintar cuando cambia. `App` lo usa en la raiz, y con eso todo el arbol
// se repinta en el idioma nuevo SIN desmontarse (el estado de cada pantalla, los formularios y la sesion se conservan).
import { useSyncExternalStore } from "react";
import { getLanguage, type Language, subscribeLanguage } from "./language";

export function useLanguage(): Language {
  return useSyncExternalStore(subscribeLanguage, getLanguage);
}
