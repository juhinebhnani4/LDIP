"""Shared utilities for Celery worker tasks."""

import asyncio
import sys
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

# Flag to track if nest_asyncio has been applied
_nest_asyncio_applied = False


def _is_gevent_worker() -> bool:
    """Check if we're running in a gevent worker context.

    Gevent workers have known issues with asyncio event loop management,
    particularly the "attached to a different loop" error that occurs when
    async objects created on one loop are used on another.

    When detected, we use thread-based execution for reliability.

    Returns:
        True if running in a gevent greenlet context.
    """
    try:
        if "gevent" not in sys.modules:
            return False

        # Check if we're actually in a spawned greenlet (not just gevent imported)
        from greenlet import getcurrent

        current = getcurrent()
        # If parent is not None, we're in a spawned greenlet (gevent worker)
        return current.parent is not None
    except Exception:
        return False


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

    Strategy:
    1. In gevent worker context: Always use thread-based execution for reliability.
       This avoids asyncio/gevent event loop conflicts entirely ("attached to
       a different loop", "event loop is closed", etc.)
    2. In non-gevent context: Use nest_asyncio for nested event loop support.

    IMPORTANT: We do NOT fall back to thread execution after attempting
    run_until_complete, because a coroutine cannot be reused once it has
    started executing. This would cause "cannot reuse already awaited coroutine".

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Raises:
        Any exception raised by the coroutine.
    """
    # In gevent worker context, always use thread-based execution
    # This creates a completely isolated event loop per call, avoiding all
    # the asyncio/gevent conflicts that cause "attached to a different loop" errors
    if _is_gevent_worker():
        return _run_in_thread(coro)

    # For non-gevent contexts, try nest_asyncio approach
    _ensure_nest_asyncio()

    # Check if there's a running loop that's still open
    loop = None
    try:
        loop = asyncio.get_running_loop()
        # Check if the loop is closed
        if loop.is_closed():
            loop = None
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop or loop is closed - create a fresh event loop
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            # Don't close the loop - keep it available for subsequent calls
            pass
    else:
        # Running loop exists and is open - use run_until_complete if nest_asyncio is active
        if _nest_asyncio_applied:
            return loop.run_until_complete(coro)
        else:
            # No nest_asyncio available - use thread (before consuming coro)
            return _run_in_thread(coro)


def _run_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    """Run coroutine in a separate thread with its own event loop."""
    import threading

    result_container: dict[str, Any] = {}
    exception_container: dict[str, BaseException] = {}

    def _thread_target() -> None:
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container["value"] = new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        except BaseException as e:
            exception_container["error"] = e

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    thread.join(timeout=300)

    if thread.is_alive():
        raise TimeoutError("Async operation timed out after 300 seconds")

    if "error" in exception_container:
        raise exception_container["error"]

    return result_container.get("value")  # type: ignore[return-value]
