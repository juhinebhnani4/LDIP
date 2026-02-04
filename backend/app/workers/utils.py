"""Shared utilities for Celery worker tasks."""

import asyncio
import concurrent.futures


def run_async(coro):
    """Run async coroutine in sync context for Celery tasks.

    Handles gevent compatibility: when gevent is patching the event loop,
    asyncio.run() fails with 'Cannot run the event loop while another loop
    is running'. In that case, we run the coroutine in a separate thread
    where no event loop exists.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.
    """
    try:
        asyncio.get_running_loop()
        # Event loop already running (gevent) — run in a thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)
