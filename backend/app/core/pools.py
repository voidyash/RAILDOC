"""Thread pools shared by the API layer.

Endpoints declared ``async def`` run on the event loop, so any blocking or
CPU-bound call inside them stalls every concurrent request. The measured
consequence (20-client stress run): p95 spikes to ~20 s driven by
CPU-heavy jobs (inference, solving, orchestration) contending with the
loop thread under the GIL, plus ``async def`` endpoints that blocked the
loop directly on synchronous DB calls.

Two helpers fix this:

* ``run_heavy`` — a small bounded pool for CPU-bound work (YOLO inference,
  OR-Tools solving, agent orchestration). Bounded on purpose: every extra
  concurrent job fights for the GIL and makes *all* requests slower, so
  excess jobs queue instead of piling onto threads.
* ``run_io`` — a wider pool for synchronous DB/HTTP calls made from
  ``async def`` endpoints.

``run_async`` adapts a coroutine-returning callable for use inside either
pool (blocking orchestration code that needs to call async internals).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import os
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Sizing rationale: each heavy job internally spawns threads (CP-SAT uses
# NUM_WORKERS=4; torch uses its own pool), so the default caps concurrent
# heavy jobs at roughly cores/4 — full machine saturation without
# oversubscription. Measured on a 16-core box: 2 starves throughput
# (heavy ops queue too long), 4 saturates cleanly. HEAVY_POOL_SIZE is
# tunable per deployment; small/2-core VMs should set it back to 2.
_DEFAULT_HEAVY = min(4, max(2, (os.cpu_count() or 4) // 4))
HEAVY_POOL_SIZE = max(1, int(os.getenv("HEAVY_POOL_SIZE", str(_DEFAULT_HEAVY))))
IO_POOL_SIZE = max(4, int(os.getenv("IO_POOL_SIZE", "8")))

_heavy_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=HEAVY_POOL_SIZE, thread_name_prefix="heavy"
)
_io_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=IO_POOL_SIZE, thread_name_prefix="io"
)


async def run_heavy(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Await a CPU-bound callable on the bounded heavy pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _heavy_pool, functools.partial(fn, *args, **kwargs)
    )


async def run_io(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Await a blocking I/O callable (sync DB/HTTP clients) off the loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _io_pool, functools.partial(fn, *args, **kwargs)
    )


def run_async(coro_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an async callable from synchronous (pool-thread) code."""
    return asyncio.run(coro_fn(*args, **kwargs))
