"""One immediate retry for a transient BLUETTI cloud failure."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import aiohttp
from pybluetti import HttpStatusException

_LOGGER = logging.getLogger(__name__)


class CloudUnreachableError(Exception):
    """A cloud call failed for a reason that says nothing about the credentials."""


def is_transient_failure(err: BaseException) -> bool:
    """
    Whether a failed cloud call leaves the credentials unjudged.

    A refused connection, a DNS failure or a timeout says the cloud could
    not be reached; a 5xx (or a 408/429) says it was reached and would not
    answer. Neither tells us anything about the token. A 4xx does: Home
    Assistant's OAuth helper calls raise_for_status(), so every status at
    or above 400 arrives as ClientResponseError, and a refresh token the
    SSO no longer honours comes back as 400 - that one has to reach the
    user as a sign-in request rather than be retried forever.
    """
    if isinstance(err, HttpStatusException):
        return err.is_transient
    if isinstance(err, aiohttp.ClientResponseError):
        return err.status >= 500 or err.status in (408, 429)
    return isinstance(err, (TimeoutError, aiohttp.ClientError))


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
