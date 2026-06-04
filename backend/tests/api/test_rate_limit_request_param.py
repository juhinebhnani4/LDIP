"""Structural guard for the slowapi rate-limiter `request` parameter contract.

Why this test exists (2026-06-04):
    Four summary endpoints (verify_summary_section, add_summary_note,
    save_section_edit, regenerate_section) named their Starlette ``Request``
    parameter ``http_request`` and used ``request`` for the Pydantic *body*
    model. slowapi's ``@limiter.limit`` locates the request object by the
    LITERAL parameter name ``request`` (slowapi/extension.py:709, :723).  It
    therefore grabbed the Pydantic body, ``isinstance(body, Request)`` was
    False, and every call raised before the handler ran -> HTTP 500 on every
    request to those endpoints, in production, for months.

    The rename fixed the four endpoints, but the underlying hazard is a
    "remember to name your Request param `request`" convention (the ARCH-003
    sticky-note-where-a-wall-belongs shape).  This test is the wall: it makes
    the convention an enforced, build-breaking invariant for the WHOLE app, so
    the next endpoint that misnames its Request param fails in CI instead of in
    production.

The invariant:
    For every route registered on the app, any parameter annotated as a
    Starlette/FastAPI ``Request`` MUST be named exactly ``request``.  (A
    ``Request`` param named anything else is invisible to slowapi; a body param
    named ``request`` would shadow it.  Forbidding the former prevents both.)
"""

import inspect

from starlette.requests import Request as StarletteRequest

from app.main import app


def _is_request_annotation(annotation: object) -> bool:
    """True if the annotation refers to a Starlette/FastAPI Request type.

    Handles both real class annotations and string annotations (modules that
    use ``from __future__ import annotations``).
    """
    if annotation is inspect.Parameter.empty:
        return False
    if isinstance(annotation, type) and issubclass(annotation, StarletteRequest):
        return True
    if isinstance(annotation, str):
        # e.g. "Request", "fastapi.Request", "starlette.requests.Request"
        return annotation.split("[")[0].split(".")[-1] == "Request"
    return False


def test_request_params_are_named_request() -> None:
    """Any Request-typed route parameter must be named ``request``.

    slowapi binds its rate limiter to the parameter literally named
    ``request``; a Request param under any other name is a latent 500 the
    moment ``@limiter.limit`` is added to that route.
    """
    offenders: list[str] = []

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue

        # inspect.signature follows functools.wraps (__wrapped__), so this
        # returns the ORIGINAL handler signature even for slowapi-wrapped
        # endpoints.
        try:
            sig = inspect.signature(endpoint)
        except (ValueError, TypeError):
            continue

        for name, param in sig.parameters.items():
            if _is_request_annotation(param.annotation) and name != "request":
                path = getattr(route, "path", "<unknown>")
                offenders.append(
                    f"{path} -> {endpoint.__name__}(): Request param named "
                    f"'{name}' (must be 'request' so slowapi can find it)"
                )

    assert not offenders, (
        "Request-typed route parameters must be named 'request' "
        "(slowapi locates the rate-limit target by that literal name). "
        "Offenders:\n  " + "\n  ".join(offenders)
    )
