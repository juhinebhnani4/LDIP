"""Shared utilities for Celery worker tasks."""

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def _is_gevent_patched() -> bool:
    """Check if gevent has monkey-patched the threading module."""
    try:
        from gevent import monkey
        return monkey.is_module_patched("threading")
    except ImportError:
        return False


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async coroutine in sync context for Celery tasks.

    This function safely executes async code from synchronous Celery tasks,
    handling both regular and gevent-patched environments.

    Strategy:
    - If NO event loop is running: use asyncio.run() directly (fastest)
    - If event loop IS running (gevent context): spawn a real OS thread
      to run the coroutine, avoiding gevent greenlet conflicts.

    The key insight: gevent's monkey-patching makes ThreadPoolExecutor
    use greenlets instead of real threads, which can cause deadlocks.
    We use threading.Thread directly with daemon=True to ensure we get
    a real OS thread even in gevent environments.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Raises:
        Any exception raised by the coroutine.
    """
    # Fast path: no event loop running - just use asyncio.run()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)

    # Slow path: event loop already running (likely gevent)
    # Run in a real OS thread to avoid greenlet deadlocks
    result_container: dict[str, Any] = {}
    exception_container: dict[str, BaseException] = {}

    def _run_in_thread() -> None:
        try:
            # Create a fresh event loop in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # CRITICAL: Clear the global running loop marker
            # Gevent's threading patch may share asyncio state across greenlets,
            # causing `_get_running_loop()` to return non-None even in new "threads".
            # We must clear this before run_until_complete() which checks it.
            try:
                from asyncio import events as asyncio_events

                old_running_loop = asyncio_events._get_running_loop()
                asyncio_events._set_running_loop(None)
            except (ImportError, AttributeError):
                old_running_loop = None

            try:
                result_container["value"] = loop.run_until_complete(coro)
            finally:
                # Restore the running loop marker
                try:
                    asyncio_events._set_running_loop(old_running_loop)
                except (NameError, AttributeError):
                    pass
                loop.close()
        except BaseException as e:
            exception_container["error"] = e

    # Use threading.Thread directly - gevent may not patch this as aggressively
    # as ThreadPoolExecutor, and daemon=True ensures cleanup on process exit
    thread = threading.Thread(target=_run_in_thread, daemon=True)
    thread.start()
    thread.join(timeout=300)  # 5 minute timeout as safety

    if thread.is_alive():
        # Thread didn't complete in time - this is a serious issue
        raise TimeoutError(
            f"Async operation timed out after 300 seconds. "
            f"Coroutine: {coro.__qualname__ if hasattr(coro, '__qualname__') else coro}"
        )

    if "error" in exception_container:
        raise exception_container["error"]

    return result_container.get("value")  # type: ignore[return-value]
