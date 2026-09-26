"""DataUpdateCoordinator for the BLUETTI integration."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pybluetti import ApplicationRuntimeException

from .cloud_retry import async_call_retrying_once
from .models import BluettiDevice

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
# tolerated failures keep the last values for at most 90 s; after that the
# entities do go unavailable, because by then it is not a blip. An auth
# failure is never ridden out - it needs the sign-in path immediately.
POLL_FAILURES_TOLERATED = 2


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
        device.coordinator = self

    async def _async_update_data(self) -> BluettiDevice:
        """
        Fetch the latest state for the device from the BLUETTI cloud API.

        The error message names the cause - "HTTP 504 Gateway Timeout" rather
        than the client's generic text - so a user can tell BLUETTI's side
        from their own setup.
        """
        try:
            await async_call_retrying_once(self.device.async_refresh_from_api)
        except ApplicationRuntimeException as err:
            message = f"BLUETTI cloud answered {err.message} (code {err.msgCode})"
            if err.msgCode in AUTH_ERROR_CODES:
                await self._async_handle_auth_rejected(err)
                raise UpdateFailed(message) from err
            if (kept := self._ride_out(err)) is not None:
                return kept
            raise UpdateFailed(message) from err
        except Exception as err:
            if (kept := self._ride_out(err)) is not None:
                return kept
            raise UpdateFailed(f"Error communicating with BLUETTI cloud: {err}") from err
        self._failed_polls = 0
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

    async def _async_handle_auth_rejected(self, err: ApplicationRuntimeException) -> None:
        """
        Try to refresh a rejected access token before asking for a sign-in.

        The cloud has been seen rejecting a token (msgCode 805) that its own
        SSO had issued for 31 days, less than 3 days later - with a refresh
        token at hand and expires_at still far in the future, so Home
        Assistant's own expiry-driven refresh never fired. A refresh-token
        grant is tried first; only when that fails too is the user sent
        through reauthentication. Raises ConfigEntryAuthFailed in that
        case; returns when a new token was stored (the entry reloads on its
        own, this poll's UpdateFailed is moot).
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
        if self._on_auth_rejected is not None and await self._on_auth_rejected():
            _LOGGER.info("BLUETTI access token refreshed after the cloud rejected it")
            return
        raise ConfigEntryAuthFailed("BLUETTI authentication expired") from err
