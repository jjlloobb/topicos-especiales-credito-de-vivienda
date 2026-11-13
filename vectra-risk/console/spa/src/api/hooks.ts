// Un hook por lectura de las vistas (TanStack Query). Sin reintentos ni refresco al volver el foco (`queryClient.ts`): los refrescos
// de la bandeja (15 s) y del caso (3 s hasta 2 min) van con `refetchInterval` (BR-U10-10). Los datos del solicitante no se guardan en la
// cache despues de salir de la pantalla (`gcTime: 0`).
import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import { CASE_REFRESH_MAX_SECONDS, CASE_REFRESH_SECONDS, INBOX_REFRESH_SECONDS } from "../config/constants";
import { useApi } from "./ApiProvider";
import { type CaseQuery, getCase, getFreeze, getModel, listCases, listFreezes, listModels } from "./endpoints";

export function useCases(query: CaseQuery) {
  const api = useApi();
  return useQuery({
    queryKey: ["cases", query],
    queryFn: () => listCases(api, query),
    refetchInterval: INBOX_REFRESH_SECONDS * 1000, // TanStack Query lo detiene solo con la pestana oculta
    gcTime: 0,
  });
}

/** `en_evaluacion` y `en_sincronizacion` se vuelven a pedir cada 3 s, hasta 2 min desde que se abre la pantalla. */
export function useCase(caseId: string) {
  const api = useApi();
  // Abrir otro caso empieza otros 2 min.
  const opened = useRef({ caseId, at: Date.now() });
  if (opened.current.caseId !== caseId) opened.current = { caseId, at: Date.now() };
  const query = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(api, caseId),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state !== "en_evaluacion" && state !== "en_sincronizacion") return false;
      return Date.now() - opened.current.at >= CASE_REFRESH_MAX_SECONDS * 1000 ? false : CASE_REFRESH_SECONDS * 1000;
    },
    gcTime: 0,
  });
  // El refresco se detuvo (2 min): la pantalla lo dice.
  const refreshStopped = Date.now() - opened.current.at >= CASE_REFRESH_MAX_SECONDS * 1000;
  return { ...query, refreshStopped };
}

export function useModels() {
  const api = useApi();
  return useQuery({ queryKey: ["models"], queryFn: () => listModels(api) });
}

export function useModel(modelId: string) {
  const api = useApi();
  return useQuery({ queryKey: ["model", modelId], queryFn: () => getModel(api, modelId) });
}

export function useFreezes() {
  const api = useApi();
  return useQuery({ queryKey: ["freezes"], queryFn: () => listFreezes(api) });
}

export function useFreeze(freezeId: string) {
  const api = useApi();
  return useQuery({ queryKey: ["freeze", freezeId], queryFn: () => getFreeze(api, freezeId) });
}
