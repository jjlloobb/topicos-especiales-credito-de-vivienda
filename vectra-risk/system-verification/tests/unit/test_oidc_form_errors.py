"""F-03 (ronda 2): un fallo de TLS o de red durante el login, tambien al cerrar el contexto, termina en un `OidcError` con codigo estable; ni el mensaje ni la traza que salen del modulo traen `state`, `nonce`,
`code_challenge`, `code_verifier` ni la URL de autorizacion. Playwright es un doble (el rojo real, con Node sin la CA, esta en `integration/test_oidc_headless.py`)."""

import traceback
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError

from vectra_verification.clients.oidc import HeadlessForm, OidcError
from vectra_verification.credentials import Secret

STATE, NONCE, CHALLENGE, VERIFIER = (
    "ESTADO-SECRETO-1",
    "NONCE-SECRETO-2",
    "DESAFIO-SECRETO-3",
    "VERIFICADOR-SECRETO-4",
)
URL = f"https://127.0.0.1:1/auth/realms/vectra/protocol/openid-connect/auth?state={STATE}&nonce={NONCE}&code_challenge={CHALLENGE}&code_verifier={VERIFIER}"
REDIRECT = "https://127.0.0.1:1/callback"
TLS = PlaywrightError(
    f"BrowserContext.close: Route.fetch: self-signed certificate in certificate chain\nCall log:\n  - → GET {URL}"
)


class Locator:
    def __init__(self, count: int = 1) -> None:
        self._count = count
        self.first = self

    def count(self) -> int:
        return self._count

    def fill(self, value: str) -> None:
        return None

    def click(self, **kwargs: Any) -> None:
        return None

    def all(self) -> list[Any]:
        return []


class Request:
    url = "https://127.0.0.1:1/auth/realms/vectra/login-actions/authenticate"

    def is_navigation_request(self) -> bool:
        return True


class Response:
    status = 302
    headers = {"location": f"{REDIRECT}?code=CODIGO&state=s"}


class Route:
    request = Request()

    def fetch(self, **kwargs: Any) -> Response:
        return Response()

    def fulfill(self, **kwargs: Any) -> None:
        return None


class Page:
    def __init__(self, context: "Context", goto_error: Exception | None, form_count: int) -> None:
        self.context, self.goto_error, self.form_count = context, goto_error, form_count

    def goto(self, url: str, **kwargs: Any) -> None:
        if self.goto_error:
            raise self.goto_error

    def locator(self, selector: str) -> Locator:
        return Locator(self.form_count if "username" in selector else 0)

    def wait_for_timeout(self, ms: int) -> None:
        if self.context.handler is not None:
            self.context.handler(Route())  # Keycloak redirige al `redirect_uri`: el manejador toma `Location`


class Context:
    def __init__(self, close_error: Exception | None, goto_error: Exception | None, form_count: int) -> None:
        self.close_error, self.goto_error, self.form_count = close_error, goto_error, form_count
        self.handler: Any = None
        self.closed = False

    def route(self, pattern: str, handler: Any) -> None:
        self.handler = handler

    def on(self, event: str, handler: Any) -> None:
        return None

    def new_page(self) -> Page:
        return Page(self, self.goto_error, self.form_count)

    def close(self) -> None:
        self.closed = True
        if self.close_error:
            raise self.close_error


class Browser:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.contexts: list[Context] = []

    def new_context(self, **options: Any) -> Context:
        context = Context(**self.kwargs)
        self.contexts.append(context)
        return context


def _submit(**kwargs: Any) -> tuple[HeadlessForm, Browser]:
    form = HeadlessForm(None)
    browser = Browser(**{"close_error": None, "goto_error": None, "form_count": 1, **kwargs})
    form._browser = browser  # type: ignore[assignment]  # un doble: no se lanza Chromium
    form.submit(URL, REDIRECT, "analista-1", Secret("contrasena"), lambda: "123456")
    return form, browser


def _text(error: BaseException) -> str:
    return "".join(traceback.format_exception(error)) + str(error)


def _assert_clean(error: BaseException) -> None:
    text = _text(error)
    for secret in (STATE, NONCE, CHALLENGE, VERIFIER, "127.0.0.1", "openid-connect/auth?", "self-signed"):
        assert secret not in text, secret
    assert isinstance(error, OidcError) and str(error) in (
        "browser_error",
        "browser_close_error",
        "login_form_missing",
    )


def test_a_tls_failure_when_closing_the_context_after_a_successful_login_is_a_stable_error() -> None:
    with pytest.raises(OidcError) as error:
        _submit(close_error=TLS)
    _assert_clean(error.value)
    assert str(error.value) == "browser_close_error"


def test_a_tls_failure_when_closing_does_not_hide_the_original_oidc_error() -> None:
    with pytest.raises(OidcError) as error:
        _submit(close_error=TLS, form_count=0)  # no hay formulario: `login_form_missing`
    _assert_clean(error.value)
    assert str(error.value) == "login_form_missing"


def test_a_network_failure_while_navigating_and_a_failing_close_are_one_stable_error() -> None:
    with pytest.raises(OidcError) as error:
        _submit(
            goto_error=PlaywrightError(f"Page.goto: net::ERR_CONNECTION_REFUSED at {URL}"), close_error=TLS
        )
    _assert_clean(error.value)
    assert str(error.value) == "browser_error"


def test_the_context_is_closed_and_counted_even_when_closing_fails() -> None:
    form = HeadlessForm(None)
    browser = Browser(close_error=TLS, goto_error=None, form_count=1)
    form._browser = browser  # type: ignore[assignment]
    with pytest.raises(OidcError):
        form.submit(URL, REDIRECT, "analista-1", Secret("contrasena"), lambda: "123456")
    assert form.contexts_opened == form.contexts_closed == 1 and browser.contexts[0].closed


def test_a_launch_failure_is_a_stable_error_without_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import vectra_verification.clients.oidc as module

    def boom() -> Any:
        raise PlaywrightError(f"Browser launch failed: {URL}")

    monkeypatch.setattr(module, "sync_playwright", boom)
    with pytest.raises(OidcError) as error:
        HeadlessForm(None).submit(URL, REDIRECT, "analista-1", Secret("contrasena"), lambda: "1")
    assert str(error.value) == "browser_launch_error" and STATE not in _text(error.value)


# --- U12-T04 (F-N1, F-N2 y F-N3 de la ronda 2 de U12-T02) -------------------------------------------------------------------------------------------------


def test_fn2_the_oidc_error_does_not_carry_the_playwright_error_in_its_context() -> None:
    with pytest.raises(OidcError) as error:
        _submit(goto_error=PlaywrightError(f"Page.goto: net::ERR_CONNECTION_REFUSED at {URL}"))
    assert str(error.value) == "browser_error"
    assert error.value.__cause__ is None and error.value.__context__ is None


@pytest.mark.parametrize("failing", ["route", "on", "new_page"])
def test_fn3_route_on_and_new_page_failures_are_a_stable_error_and_the_context_is_closed(
    monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise PlaywrightError(f"Context.{failing}: {URL}")

    monkeypatch.setattr(Context, failing, boom)
    form = HeadlessForm(None)
    browser = Browser(close_error=None, goto_error=None, form_count=1)
    form._browser = browser  # type: ignore[assignment]
    with pytest.raises(OidcError) as error:
        form.submit(URL, REDIRECT, "analista-1", Secret("contrasena"), lambda: "1")
    _assert_clean(error.value)
    assert str(error.value) == "browser_error" and error.value.__context__ is None
    assert form.contexts_opened == form.contexts_closed == 1 and browser.contexts[0].closed


def test_fn1_a_route_fetch_failure_stays_inside_the_handler_aborts_the_route_and_ends_in_a_stable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El manejador no deja salir el error de `route.fetch` (Playwright lo imprimiria en stderr con el `Call log`): aborta la ruta, anota el fallo y el login termina con `browser_error` sin esperar el plazo."""
    aborted: list[bool] = []
    raised: list[BaseException] = []

    class FailingRoute(Route):
        def fetch(self, **kwargs: Any) -> Response:
            raise PlaywrightError(f"Route.fetch: self-signed certificate\nCall log:\n  - → GET {URL}")

        def abort(self, **kwargs: Any) -> None:
            aborted.append(True)

    class FailingPage(Page):
        def wait_for_timeout(self, ms: int) -> None:
            try:
                assert self.context.handler is not None
                self.context.handler(FailingRoute())
            except BaseException as error:  # lo que Playwright imprimiria en stderr
                raised.append(error)
                raise

    monkeypatch.setattr(Context, "new_page", lambda self: FailingPage(self, None, 1))
    with pytest.raises(OidcError) as error:
        _submit()
    assert str(error.value) == "browser_error" and not raised and aborted == [True]
    _assert_clean(error.value)


def test_fn1_a_route_that_cannot_be_aborted_either_is_still_a_stable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DeadRoute(Route):
        def fetch(self, **kwargs: Any) -> Response:
            raise PlaywrightError(f"Route.fetch: {URL}")

        def abort(self, **kwargs: Any) -> None:
            raise PlaywrightError("Route is already handled")

    class DeadPage(Page):
        def wait_for_timeout(self, ms: int) -> None:
            assert self.context.handler is not None
            self.context.handler(DeadRoute())

    monkeypatch.setattr(Context, "new_page", lambda self: DeadPage(self, None, 1))
    with pytest.raises(OidcError) as error:
        _submit()
    assert str(error.value) == "browser_error"
