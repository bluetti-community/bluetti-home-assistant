"""DataUpdateCoordinator for the BLUETTI integration."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from pybluetti import ApplicationRuntimeException, HttpStatusException

from .cloud_retry import (
    RefreshNotJudged,
    async_call_retrying_once,
    describe_error,
    end_episode,
    first_in_episode,
)
from .models import BluettiDevice, EmptyStatusResponse
from .poll_history import PollHistory, PollOutcome, PollRecord

if TYPE_CHECKING:
    # Deliberately not a runtime import: __init__.py imports this module to
    # define BluettiConfigEntry in the first place, so importing it back
    # here would be circular. TYPE_CHECKING avoids that while still giving
    # mypy the precise type (matches the same pattern models.py already
    # uses for BluettiDeviceCoordinator).
    from . import BluettiConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

# msgCode values that mean the OAuth token is no longer valid.
AUTH_ERROR_CODES = {401, 805}

# How many polls in a row may fail before the entities go unavailable. The
# BLUETTI cloud drops out for a few seconds at a time - the official app
# loses the device at the same moment, showing "Device not found" (#63) -
# and the one retry inside a poll does not always outlast it. Failing at
# that point sent every entity to unavailable for a whole interval, so
# owners were guarding their automations with "for:" delays instead. Two
# tolerated failures keep the last values for about 90 s; after that the
# entities do go unavailable, because by then it is not a blip. A cloud that
# does not answer at all stretches this to 270 s at most: each failed poll
# then waits out pybluetti's 30 s request timeout twice (the call and its
# one retry) before the next interval starts. An auth failure is never
# ridden out - it needs the sign-in path immediately.
POLL_FAILURES_TOLERATED = 2


def classify_failure(err: Exception) -> tuple[PollOutcome, int | None, int | None]:
    """
    A failed poll's outcome, msgCode and HTTP status.

    Subclasses come before their bases: HttpStatusException is an
    ApplicationRuntimeException, ClientConnectorDNSError a
    ClientConnectorError, and aiohttp's ServerTimeoutError is both a
    ClientError and a TimeoutError - a timeout all the same.
    """
    if isinstance(err, HttpStatusException):
        return PollOutcome.HTTP_ERROR, None, err.status
    if isinstance(err, ApplicationRuntimeException):
        if err.msgCode in AUTH_ERROR_CODES:
            return PollOutcome.AUTH_REJECTED, err.msgCode, None
        return PollOutcome.API_ERROR, err.msgCode, None
    if isinstance(err, TimeoutError):
        return PollOutcome.TIMEOUT, None, None
    if isinstance(err, aiohttp.ClientConnectorDNSError):
        return PollOutcome.DNS_ERROR, None, None
    if isinstance(err, aiohttp.ClientConnectorError):
        return PollOutcome.CONNECT_ERROR, None, None
    if isinstance(err, aiohttp.ClientError):
        return PollOutcome.NETWORK_ERROR, None, None
    if isinstance(err, EmptyStatusResponse):
        return PollOutcome.EMPTY_RESPONSE, None, None
    return PollOutcome.ERROR, None, None


class BluettiDeviceCoordinator(DataUpdateCoordinator[BluettiDevice]):
    """Coordinate REST polling and websocket-triggered refreshes for one device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluettiConfigEntry,
        device: BluettiDevice,
        on_auth_rejected: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        """
        Initialize the coordinator for a single BLUETTI device.

        on_auth_rejected: awaited when the cloud rejects the access token;
        returns True when it obtained a new one (the entry then reloads on
        its own), False when the user has to sign in again.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-{device.device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        self._on_auth_rejected = on_auth_rejected
        self._failed_polls = 0
        self._poll_history = PollHistory()
        self._poll_listeners: list[CALLBACK_TYPE] = []
        device.coordinator = self

    @property
    def last_poll(self) -> PollRecord | None:
        """The latest poll, as the cloud answered it, or None before the first."""
        return self._poll_history.latest

    def poll_history(self) -> tuple[PollRecord, ...]:
        """Every poll kept, oldest first, ridden-out failures included."""
        return self._poll_history.snapshot()

    @callback
    def async_add_poll_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """
        Call update_callback after every poll, failed ones included.

        The coordinator's own listeners hear of a failed poll only when it
        flips last_update_success: Home Assistant skips them for the second
        failure in a row, which is the middle of an outage. Returns the
        function that removes the listener.
        """
        self._poll_listeners.append(update_callback)
        return lambda: self._poll_listeners.remove(update_callback)

    async def _async_update_data(self) -> BluettiDevice:
        """
        Fetch the latest state for the device from the BLUETTI cloud API.

        The error message names the cause - "HTTP 504 Gateway Timeout" rather
        than the client's generic text - so a user can tell BLUETTI's side
        from their own setup.

        Every poll goes into the poll history first, whatever triggered it
        and whatever the ride-out then makes of it.
        """
        started = dt_util.utcnow()
        start = time.monotonic()
        attempts = 0

        async def attempt() -> None:
            nonlocal attempts
            attempts += 1
            await self.device.async_refresh_from_api()

        def record(
            outcome: PollOutcome, msg_code: int | None = None, http_status: int | None = None
        ) -> None:
            self._poll_history.add(PollRecord(
                started=started,
                duration_ms=round((time.monotonic() - start) * 1000),
                outcome=outcome,
                attempts=attempts,
                msg_code=msg_code,
                http_status=http_status,
            ))
            for update_callback in list(self._poll_listeners):
                update_callback()

        try:
            await async_call_retrying_once(attempt)
        except ApplicationRuntimeException as err:
            record(*classify_failure(err))
            message = f"BLUETTI cloud answered {err.message} (code {err.msgCode})"
            if err.msgCode in AUTH_ERROR_CODES:
                if await self._async_handle_auth_rejected(err) and self.data is not None:
                    # A new token is stored and the entry reloads on its own:
                    # failing this poll would only log an ERROR right after
                    # the refresh that healed it. Not counted as a ridden-out
                    # failure; without a new token it still fails at once.
                    return self.data
                raise UpdateFailed(message) from err
            if (kept := self._ride_out(err)) is not None:
                return kept
            raise UpdateFailed(message) from err
        except Exception as err:
            record(*classify_failure(err))
            if (kept := self._ride_out(err)) is not None:
                return kept
            raise UpdateFailed(
                f"Error communicating with BLUETTI cloud: {describe_error(err)}"
            ) from err
        record(self.device.last_answer)
        self._failed_polls = 0
        if self.config_entry is not None:
            end_episode(self.config_entry.entry_id)
        return self.device

    def _ride_out(self, err: Exception) -> BluettiDevice | None:
        """
        The values already shown, when a failed poll is still inside the tolerance.

        Returns None once the run of failures passes POLL_FAILURES_TOLERATED,
        or on the very first poll, where there is nothing to keep - the
        caller then raises UpdateFailed and the entities go unavailable.
        """
        if self.data is None or self._failed_polls >= POLL_FAILURES_TOLERATED:
            return None
        self._failed_polls += 1
        _LOGGER.debug(
            "Poll failed (%d of %d tolerated), keeping the last values: %s",
            self._failed_polls,
            POLL_FAILURES_TOLERATED,
            err,
        )
        return self.data

    async def _async_handle_auth_rejected(self, err: ApplicationRuntimeException) -> bool:
        """
        Try to refresh a rejected access token before asking for a sign-in.

        The cloud has been seen rejecting a token (msgCode 805) that its own
        SSO had issued for 31 days, less than 3 days later - with a refresh
        token at hand and expires_at still far in the future, so Home
        Assistant's own expiry-driven refresh never fired. A refresh-token
        grant is tried first; only when that fails too is the user sent
        through reauthentication. Raises ConfigEntryAuthFailed in that
        case; returns True when a new token was stored (the entry reloads on
        its own, so the poll keeps the values already shown).

        A grant that never reached the cloud also returns, and so does one the
        floor declined to make: neither says anything about the credentials,
        and reporting either as expired authentication sent owners through a
        sign-in that fixed nothing - once while their DNS was failing, once
        while the cloud was dropping a token that still had 30 days to run
        (#65). Both return False: no new token, so the poll still fails and
        Home Assistant retries on its own.
        """
        # config_entry is always set here (passed to __init__), but typed
        # Optional on the base class.
        entry_data = self.config_entry.data if self.config_entry is not None else {}
        expires_at = entry_data.get("token", {}).get("expires_at")
        if isinstance(expires_at, (int, float)):
            _LOGGER.info(
                "BLUETTI cloud rejected the access token (code %s) %.1f days before its announced expiry",
                err.msgCode,
                (expires_at - time.time()) / 86400,
            )
        if self._on_auth_rejected is not None:
            try:
                refreshed = await self._on_auth_rejected()
            except RefreshNotJudged as refresh_err:
                # Once per episode at WARNING: the same decision repeats on
                # every poll until the cloud takes the token again, and it is
                # the decision working, not a new problem each time.
                entry_id = self.config_entry.entry_id if self.config_entry is not None else ""
                _LOGGER.log(
                    logging.WARNING if first_in_episode(entry_id, "not_refreshed") else logging.DEBUG,
                    "The rejected token was not refreshed (%s), keeping the sign-in and retrying",
                    refresh_err,
                )
                return False
            if refreshed:
                _LOGGER.info("BLUETTI access token refreshed after the cloud rejected it")
                return True
        raise ConfigEntryAuthFailed("BLUETTI authentication expired") from err
