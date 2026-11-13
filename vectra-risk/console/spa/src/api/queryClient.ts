// TanStack Query sin reintentos y sin refresco al volver el foco (P-U10-04; BR-U10-20): el BFF no reintenta y la SPA tampoco; un `GET`
// se vuelve a pedir en su siguiente refresco. Un refresco de TanStack Query no cuenta como actividad (`inactivity` no lo mira).
import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false },
      mutations: { retry: false },
    },
  });
}
