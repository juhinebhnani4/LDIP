"""Shared utilities for Celery worker tasks."""

import asyncio
from typing import Any, Coroutine, TypeVar

import nest_asyncio

# Apply nest_asyncio to allow nested event loops
# This is required because gevent+asyncio can have overlapping loop contexts,
# and asyncio.to_thread() inside async code needs proper loop handling.
nest_asyncio.apply()

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async coroutine in sync context for Celery tasks.

    This function safely executes async code from synchronous Celery tasks.
    Uses nest_asyncio to handle nested event loop scenarios that occur with
    gevent pool workers.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Raises:
        Any exception raised by the coroutine.
    """
    # With nest_asyncio applied, we can safely run coroutines
    # even if there's already a running loop (gevent context)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop - just use asyncio.run()
        return asyncio.run(coro)
    else:
        # Running loop exists (gevent context) - nest_asyncio allows this
        return loop.run_until_complete(coro)
