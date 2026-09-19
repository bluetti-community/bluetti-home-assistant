"""One immediate retry for a transient BLUETTI cloud failure."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import aiohttp
from pybluetti import HttpStatusException

_LOGGER = logging.getLogger(__name__)


async def async_call_retrying_once[T](call: Callable[[], Awaitable[T]]) -> T:
    """
    Await call(), retrying it once immediately on a transient failure.

    A lone gateway error (HTTP 502/503/504) or a network timeout is what
    the BLUETTI cloud produces about one request in thirty on a bad day,
    gone on the next request - failing the whole operation on it marked
    every entity unavailable for a 30 s poll interval (#53) or aborted a
    reauthentication flow the user then had to redo. A second failure of
    the same kind propagates; anything else (an API msgCode, an auth
    error, a 404) is not retried at all.
    """
    try:
        return await call()
    except (HttpStatusException, TimeoutError, aiohttp.ClientError) as err:
        if isinstance(err, HttpStatusException) and not err.is_transient:
            raise
        _LOGGER.debug("BLUETTI cloud request failed (%s), retrying once", err)
        return await call()
