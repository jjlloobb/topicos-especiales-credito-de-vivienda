// @vitest-environment jsdom
// BR-U10-06; NFR-U10-52; los ejemplos del FD (business-logic-model §3): `StepUpProvider`, `StepUpButton` y `StepUpDialog` con un
// formulario de prueba. Con `ResolveFrozenDialog` y en el navegador real lo prueba U10-T04.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type ReactNode, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApi, MfaRequiredError, request } from "../../../src/api/client";
import type { SessionInfo } from "../../../src/api/endpoints";
import { ui } from "../../../src/i18n";
import { StepUpButton } from "../../../src/stepup/StepUpButton";
import { type ConfirmResult, StepUpProvider, type StepUpEnv, useStepUp } from "../../../src/stepup/StepUpProvider";
import { flush, harness, OWN, CALLBACK } from "../../support/stepup-world";

afterEach(cleanup);

const NOW = Date.parse("2026-11-12T15:00:00Z");
const session = (over: Partial<SessionInfo> = {}): SessionInfo => ({
  role: "cumplimiento",
  mfa: true,
  auth_time: new Date(NOW - 60_000).toISOString(),
  locale: "es-CO",
  ...over,
});
const STALE = session({ auth_time: new Date(NOW - 1000_000).toISOString() });

interface Body {
  readonly justification: string;
}

type Setup = ReturnType<typeof setupWorld>;

function setupWorld() {
  const world = harness<Body>();
  const listeners = new Set<(event: MessageEvent) => void>();
  const messageTarget = {
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.add(listener as (event: MessageEvent) => void);
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.delete(listener as (event: MessageEvent) => void);
    },
  };
  const opens: number[] = [];
  const env: StepUpEnv = {
    ownOrigin: OWN,
    stepupRedirectUri: CALLBACK,
    backend: world.deps.backend,
    openWindow: () => {
      opens.push(1);
      return world.deps.openWindow();
    },
    timers: world.timers,
    reportFailure: world.deps.reportFailure,
    now: () => NOW,
    messageTarget,
  };
  /** Entrega un `postMessage` a la ventana principal. */
  const post = (over: Partial<{ origin: string; source: unknown; data: unknown }> = {}) => {
    for (const listener of listeners) {
      listener({ origin: OWN, source: world.popups[0], data: { code: "c", state: "state-1" }, ...over } as MessageEvent);
    }
  };
  return { world, env, opens, post, listeners };
}

/** Un formulario de prueba: el cuerpo (la justificacion) vive en el estado del componente, como en `ResolveFrozenDialog`. */
function Form({ send }: { send: (body: Body) => Promise<ConfirmResult> }): ReactNode {
  const [justification, setJustification] = useState("");
  return (
    <form>
      <label htmlFor="justificacion">{ui("stepup_dialog_title")}</label>
      <textarea id="justificacion" value={justification} onChange={(e) => setJustification(e.target.value)} />
      <StepUpButton body={{ justification }} send={send} label="Confirmar accion" isDisabled={false} />
    </form>
  );
}

function renderForm(setup: Setup, sess: SessionInfo | null, send: (body: Body) => Promise<ConfirmResult>) {
  return render(
    <StepUpProvider session={sess} env={setup.env}>
      <Form send={send} />
    </StepUpProvider>,
  );
}

const type = (text: string) => fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });

describe("token sin MFA reciente: «Verificar y confirmar»", () => {
  it("el boton lo dice y window.open se llama de forma sincrona en ese clic, antes de enviar", async () => {
    const setup = setupWorld();
    const send = vi.fn(async (_body: Body): Promise<ConfirmResult> => "ok");
    renderForm(setup, STALE, send);
    type("porque aplica");
    const button = screen.getByRole("button", { name: ui("verify_and_confirm") });
    fireEvent.click(button);
    expect(setup.opens).toHaveLength(1); // sin esperar nada: abierta dentro del clic
    expect(send).not.toHaveBeenCalled(); // y la accion todavia no se envio
    expect(screen.getByRole("status").textContent).toBe(ui("stepup_opened")); // aria-live al abrir
    expect(button.hasAttribute("disabled")).toBe(true); // un intento a la vez
    // el usuario termina la verificacion en la ventana
    setup.world.backend.resolveRequest();
    await flush();
    setup.post();
    setup.world.backend.resolveExchange("ok");
    await flush();
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send).toHaveBeenCalledWith({ justification: "porque aplica" }); // el envio tras verificar: una vez, con el cuerpo del formulario
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(ui("stepup_done")));
  });

  it("con MFA reciente el boton dice el texto de la accion y envia ya, sin abrir ventana", async () => {
    const setup = setupWorld();
    const send = vi.fn(async (_body: Body): Promise<ConfirmResult> => "ok");
    renderForm(setup, session(), send);
    type("justificacion");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar accion" }));
    await flush();
    expect(send).toHaveBeenCalledWith({ justification: "justificacion" });
    expect(setup.opens).toHaveLength(0);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sin sesion (aun no hay get_me) no pide verificar", () => {
    const setup = setupWorld();
    renderForm(setup, null, async () => "ok");
    expect(screen.getByRole("button", { name: "Confirmar accion" })).toBeTruthy();
  });
});

describe("403 mfa_required inesperado: StepUpDialog", () => {
  it("muestra el dialogo y la ventana se abre en el clic de «Verificar identidad»; el reintento es unico y lleva la misma justificacion", async () => {
    const setup = setupWorld();
    const results: ConfirmResult[] = ["mfa_required", "ok"];
    const bodies: Body[] = [];
    const send = async (body: Body): Promise<ConfirmResult> => {
      bodies.push(body);
      return results.shift() ?? "failed";
    };
    renderForm(setup, session(), send);
    type("la misma justificacion");
    const confirm = screen.getByRole("button", { name: "Confirmar accion" });
    confirm.focus();
    fireEvent.click(confirm);
    const verify = await screen.findByRole("button", { name: ui("verify_identity") });
    expect(setup.opens).toHaveLength(0); // el 403 no abrio ninguna ventana por si solo
    fireEvent.click(verify);
    expect(setup.opens).toHaveLength(1); // se abre en el clic del dialogo
    setup.world.backend.resolveRequest();
    await flush();
    setup.post();
    setup.world.backend.resolveExchange("ok");
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies).toEqual([{ justification: "la misma justificacion" }, { justification: "la misma justificacion" }]); // 403 y luego 200
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(ui("stepup_done")));
    expect(document.activeElement).toBe(confirm); // el foco vuelve al control que abrio la ventana (NFR-U10-52)
    expect(setup.world.popups[0]?.closed).toBe(true);
  });

  it("cancelar el dialogo lo cierra, no abre ventana y devuelve el foco", async () => {
    const setup = setupWorld();
    renderForm(setup, session(), async () => "mfa_required");
    const confirm = screen.getByRole("button", { name: "Confirmar accion" });
    fireEvent.click(confirm);
    fireEvent.click(await screen.findByRole("button", { name: ui("stepup_dialog_cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(setup.opens).toHaveLength(0);
    expect(document.activeElement).toBe(confirm);
  });

  it("un resultado distinto de mfa_required no abre el dialogo", async () => {
    const setup = setupWorld();
    renderForm(setup, session(), async () => "failed");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar accion" }));
    await flush();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("la verificacion no termina: sin reintento, formulario intacto, aviso «vuelve a confirmar»", () => {
  it.each([
    ["ventana bloqueada", (s: Setup) => { s.world.blockNextOpen = true; }, () => undefined],
    ["ventana cerrada sin terminar", () => undefined, (s: Setup) => { s.world.popups[0]!.closed = true; s.world.timers.fireInterval(); }],
    ["vencimiento de 5 min", () => undefined, (s: Setup) => { s.world.timers.fireTimeout(); }],
  ])("%s", async (_name, before, after) => {
    const setup = setupWorld();
    const send = vi.fn(async (_body: Body): Promise<ConfirmResult> => "ok");
    renderForm(setup, STALE, send);
    type("texto largo de la justificacion");
    before(setup);
    fireEvent.click(screen.getByRole("button", { name: ui("verify_and_confirm") }));
    if (setup.world.popups.length > 0) {
      setup.world.backend.resolveRequest();
      await flush();
    }
    after(setup);
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(ui("stepup_incomplete")));
    expect(send).not.toHaveBeenCalled(); // sin reintento
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("texto largo de la justificacion"); // formulario intacto
    expect(setup.world.backend.secrets.size).toBe(0);
  });

  it("un postMessage de otro origen, de otra ventana o con otro state se ignora: sin canje ni reintento", async () => {
    const setup = setupWorld();
    const send = vi.fn(async (_body: Body): Promise<ConfirmResult> => "ok");
    renderForm(setup, STALE, send);
    fireEvent.click(screen.getByRole("button", { name: ui("verify_and_confirm") }));
    setup.world.backend.resolveRequest();
    await flush();
    setup.post({ origin: "https://evil.test" });
    setup.post({ source: { otra: true } });
    setup.post({ data: { code: "c", state: "otro-state" } });
    await flush();
    expect(setup.world.backend.exchangeCalls).toBe(0);
    expect(send).not.toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toBe(ui("stepup_opened"));
  });

  it("el segundo 403 muestra el error y no hay tercero", async () => {
    const setup = setupWorld();
    const send = vi.fn(async (_body: Body): Promise<ConfirmResult> => "mfa_required");
    renderForm(setup, STALE, send);
    fireEvent.click(screen.getByRole("button", { name: ui("verify_and_confirm") }));
    setup.world.backend.resolveRequest();
    await flush();
    setup.post();
    setup.world.backend.resolveExchange("ok");
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(ui("stepup_retry_failed")));
    expect(send).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("un aprobador sin MFA reciente confirma (ejemplo del FD: 403 mfa_required, ventana y reintento unico -> 200)", () => {
  it("con el cliente de la API: el primer envio da 403 mfa_required; el reintento lleva la misma justificacion y da 200", async () => {
    const setup = setupWorld();
    const seen: unknown[] = [];
    let calls = 0;
    const fetchImpl = vi.fn(async (input: Request | string | URL) => {
      const requestObject = input as Request;
      seen.push(await requestObject.clone().json());
      calls += 1;
      return calls === 1
        ? new Response(JSON.stringify({ code: "mfa_required", correlation_id: "a".repeat(32) }), {
            status: 403,
            headers: { "content-type": "application/problem+json" },
          })
        : new Response(null, { status: 204 });
    });
    const api = createApi({ baseUrl: OWN, getToken: () => "tok", fetchImpl: fetchImpl as unknown as typeof fetch });
    const send = async (body: Body): Promise<ConfirmResult> => {
      try {
        await request(api.POST("/api/console/client-errors", { body: { error_code: "render_error", route_template: body.justification, app_version: "0.1.0", correlation_id: null } }));
        return "ok";
      } catch (error) {
        return error instanceof MfaRequiredError ? "mfa_required" : "failed";
      }
    };
    renderForm(setup, session(), send);
    type("justif");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar accion" }));
    fireEvent.click(await screen.findByRole("button", { name: ui("verify_identity") }));
    setup.world.backend.resolveRequest();
    await flush();
    setup.post();
    setup.world.backend.resolveExchange("ok");
    await waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(2));
    expect(seen[0]).toEqual(seen[1]); // exactamente el cuerpo original
    expect((seen[1] as { route_template: string }).route_template).toBe("justif");
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(ui("stepup_done")));
  });
});

describe("el proveedor", () => {
  it("useStepUp fuera del proveedor falla con un mensaje claro", () => {
    const Probe = () => {
      useStepUp();
      return null;
    };
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow("useStepUp fuera de StepUpProvider");
    quiet.mockRestore();
  });

  it("suelta el oyente de `message` al desmontarse", () => {
    const setup = setupWorld();
    const { unmount } = renderForm(setup, session(), async () => "ok");
    expect(setup.listeners.size).toBe(1);
    unmount();
    expect(setup.listeners.size).toBe(0);
  });
});
