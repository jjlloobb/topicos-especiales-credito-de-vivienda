// `ErrorBoundary` (BR-U10-22): un error de renderizado se reporta como `render_error` y la pantalla muestra el catalogo, no el error.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { ui } from "../i18n";

interface Props {
  readonly onError: () => void;
  readonly children: ReactNode;
}

export class ErrorBoundary extends Component<Props, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  override componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Ni el mensaje ni la traza salen del navegador: solo el codigo del catalogo.
    this.props.onError();
  }

  override render(): ReactNode {
    return this.state.failed ? (
      <div role="alert">
        <h1>{ui("error_boundary_title")}</h1>
        <p>{ui("error_boundary_body")}</p>
      </div>
    ) : (
      this.props.children
    );
  }
}
