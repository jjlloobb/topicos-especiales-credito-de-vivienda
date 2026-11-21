// La marca de la consola: una casa con una marca de verificacion (credito de vivienda). Es un SVG propio dentro del codigo (la CSP de U2 no
// deja cargar imagenes ni fuentes de otro origen) y decorativo: el nombre lo dice el texto de al lado, asi que va con `aria-hidden`.
export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <path d="M16 3.5 2.5 15h3.6v12.5a1 1 0 0 0 1 1h17.8a1 1 0 0 0 1-1V15h3.6L16 3.5Z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
      <path d="m11 18.2 3.6 3.6 6.6-7.2" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
