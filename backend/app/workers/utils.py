"""Shared utilities for Celery worker tasks."""

import asyncio
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

# Flag to track if nest_asyncio has been applied
_nest_asyncio_applied = False


def _ensure_nest_asyncio() -> bool:
    """Apply nest_asyncio if not already applied and not using uvloop.

    Returns True if nest_asyncio is available for use, False otherwise.
    """
    global _nest_asyncio_applied

    if _nest_asyncio_applied:
        return True

    try:
        # Check if current loop is uvloop (which can't be patched)
        try:
            loop = asyncio.get_event_loop()
            loop_type = type(loop).__name__
            if "uvloop" in loop_type.lower():
                # uvloop can't be patched - skip nest_asyncio
                return False
        except RuntimeError:
            # No loop yet - safe to apply
            pass

        import nest_asyncio

        nest_asyncio.apply()
        _nest_asyncio_applied = True
        return True
    except (ImportError, ValueError) as e:
        # nest_asyncio not available or can't patch this loop type
        import structlog

        logger = structlog.get_logger(__name__)
        logger.debug("nest_asyncio_not_applied", reason=str(e))
        return False


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async coroutine in sync context for Celery tasks.

    This function safely executes async code from synchronous Celery tasks.
    Uses nest_asyncio (when available) to handle nested event loop scenarios
    that occur with gevent pool workers.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Raises:
        Any exception raised by the coroutine.
    """
    # Try to apply nest_asyncio for nested loop support
    _ensure_nest_asyncio()

    # Check if there's a running loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop - just use asyncio.run()
        return asyncio.run(coro)
    else:
        # Running loop exists - use run_until_complete if nest_asyncio is active
        if _nest_asyncio_applied:
            return loop.run_until_complete(coro)
        else:
            # Fallback: create new loop in thread (slower but works without nest_asyncio)
            import threading

            result_container: dict[str, Any] = {}
            exception_container: dict[str, BaseException] = {}

            def _run_in_thread() -> None:
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result_container["value"] = new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                except BaseException as e:
                    exception_container["error"] = e

            thread = threading.Thread(target=_run_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=300)

            if thread.is_alive():
                raise TimeoutError("Async operation timed out after 300 seconds")

            if "error" in exception_container:
                raise exception_container["error"]

            return result_container.get("value")  # type: ignore[return-value]
