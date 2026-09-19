"""DataUpdateCoordinator for the BLUETTI integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pybluetti import ApplicationRuntimeException, HttpStatusException

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


class BluettiDeviceCoordinator(DataUpdateCoordinator[BluettiDevice]):
    """Coordinate REST polling and websocket-triggered refreshes for one device."""

    def __init__(self, hass: HomeAssistant, entry: BluettiConfigEntry, device: BluettiDevice) -> None:
        """Initialize the coordinator for a single BLUETTI device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-{device.device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        device.coordinator = self

    async def _async_update_data(self) -> BluettiDevice:
        """
        Fetch the latest state for the device from the BLUETTI cloud API.

        The error message names the cause - "HTTP 504 Gateway Timeout" rather
        than the client's generic text - so a user can tell BLUETTI's side
        from their own setup.
        """
        try:
            await self._async_refresh_retrying_once()
        except ApplicationRuntimeException as err:
            if err.msgCode in AUTH_ERROR_CODES:
                raise ConfigEntryAuthFailed("BLUETTI authentication expired") from err
            raise UpdateFailed(f"BLUETTI cloud answered {err.message} (code {err.msgCode})") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with BLUETTI cloud: {err}") from err
        return self.device

    async def _async_refresh_retrying_once(self) -> None:
        """
        Refresh, retrying once immediately on a transient failure.

        A lone gateway error (HTTP 502/503/504) or a network timeout, with
        the next poll succeeding, marked every entity of the device
        unavailable for a whole 30 s interval and logged an ERROR (#53) - the
        same reasoning as the Modbus coordinator's own single immediate
        retry. A second failure of the same kind propagates; anything else
        (an API msgCode, an auth error, a 404) is not retried at all.
        """
        try:
            await self.device.async_refresh_from_api()
        except (HttpStatusException, TimeoutError, aiohttp.ClientError) as err:
            if isinstance(err, HttpStatusException) and not err.is_transient:
                raise
            _LOGGER.debug("BLUETTI cloud request failed (%s), retrying once", err)
            await self.device.async_refresh_from_api()
