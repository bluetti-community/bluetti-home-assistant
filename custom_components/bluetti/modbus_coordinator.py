"""DataUpdateCoordinator for the optional local Modbus data source."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from bluetti_modbus_lib.modbus.client import BluettiModbusClient, ClientReturnValue
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection.exceptions import ModbusError

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BluettiConfigEntry

_LOGGER = logging.getLogger(__name__)

# Matches the cloud coordinator's cadence. Bluetti's Modbus TCP stack is
# known to become unresponsive under connection/poll pressure - a rapid
# burst of connections during testing once required a factory reset to
# recover - so there is no reason to poll faster locally just because it's
# local. See hassio-bluetti-modbus's PollingCoordinator for the same
# reasoning applied there.
UPDATE_INTERVAL = timedelta(seconds=30)


class BluettiModbusCoordinator(DataUpdateCoordinator[dict[str, ClientReturnValue]]):
    """Coordinate polling of one device's optional local Modbus connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluettiConfigEntry,
        device_id: str,
        host: str,
        port: int,
        dev_type: str,
    ) -> None:
        """Initialize the coordinator for a single device's Modbus connection."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-modbus-{device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        # One persistent client for the lifetime of this coordinator, not one
        # per poll - a fresh connection on every poll is exactly the pattern
        # that has made the device's Modbus TCP stack unresponsive under load.
        self._client = BluettiModbusClient(host, port, dev_type)

    async def _async_update_data(self) -> dict[str, ClientReturnValue]:
        """Fetch the latest field values over Modbus."""
        try:
            fields = await self._client.read()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return {field.name: field for field in fields}

    async def async_shutdown(self) -> None:
        """Close the underlying Modbus connection and stop the coordinator."""
        await self._client.aclose()
        await super().async_shutdown()
