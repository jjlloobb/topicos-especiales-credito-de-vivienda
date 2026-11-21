// Las rutas de la SPA (BR-U10-12): todas las vistas de frontend-components §1 estan declaradas; las diferidas muestran el marcador. Una
// ruta a la que el rol no llega muestra «sin acceso» SIN montar la vista (que es lo que llamaria al BFF) y sin cargar su fragmento.
import { type ComponentType, type LazyExoticComponent, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router";
import { useAuth } from "../../auth/AuthProvider";
import { restorablePathFor } from "../../auth/returnTo";
import { Layout } from "./Layout";
import { lazyView } from "./lazyView";
import { LOADERS } from "./loaders";
import { NoAccess, UnknownRoute } from "./NoAccess";
import { NotAvailable } from "./NotAvailable";
import { homeFor, ROUTES, type RouteSpec } from "./routes";

type ViewElement = LazyExoticComponent<ComponentType> | null;

function View({ spec, lazyViews }: { readonly spec: RouteSpec; readonly lazyViews: ReadonlyMap<string, ViewElement> }) {
  const Lazy = lazyViews.get(spec.view) ?? null;
  return Lazy === null ? <NotAvailable title={spec.title} /> : <Lazy />;
}

function Guarded({ spec, lazyViews }: { readonly spec: RouteSpec; readonly lazyViews: ReadonlyMap<string, ViewElement> }) {
  const role = useAuth().session?.role;
  if (role === undefined || !spec.roles.includes(role)) return <NoAccess />;
  return <View spec={spec} lazyViews={lazyViews} />;
}

/**
 * `/` (y `/callback`, el retorno del login): lleva a la ruta que se pidio antes del login si es un destino interno al que el rol llega
 * (H-12: un enlace directo o una recarga conservan la ruta y sus filtros); si no, al inicio del rol. El destino se toma una sola vez.
 */
function Home() {
  const auth = useAuth();
  const role = auth.session?.role;
  const [requested] = useState(() => auth.takeReturnTo());
  if (role === undefined) return null;
  return <Navigate to={restorablePathFor(requested, role) ?? homeFor(role)} replace />;
}

export function AppRoutes({ onChunkFailure }: { readonly onChunkFailure: () => void }) {
  const lazyViews = useMemo(
    () =>
      new Map<string, ViewElement>(
        ROUTES.map((spec) => {
          const loader = spec.entry ? LOADERS[spec.view] : undefined;
          return [spec.view, loader === undefined ? null : lazyView(loader, onChunkFailure)];
        }),
      ),
    [onChunkFailure],
  );
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="callback" element={<Home />} />
        {ROUTES.map((spec) => (
          <Route key={spec.path} path={spec.path} element={<Guarded spec={spec} lazyViews={lazyViews} />} />
        ))}
        <Route path="*" element={<UnknownRoute />} />
      </Route>
    </Routes>
  );
}
