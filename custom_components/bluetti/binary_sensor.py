from typing import Any

# Home Assistant 2026.10 re-exports the device class without declaring it.
from homeassistant.components.binary_sensor import (  # type: ignore[attr-defined,unused-ignore]
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BluettiConfigEntry
from .entity import BluettiCloudHealthEntity, BluettiEntity
from .models import BluettiData, BluettiDevice, BluettiState
from .poll_history import PollOutcome

# Entities only read from the coordinator and never poll or call the API
# themselves, so there is no need to limit concurrent updates.
PARALLEL_UPDATES = 0

BINARY_SENSOR_MAP: dict[str, dict[str, Any]] = {
    "onLine": {
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "name": "Online",
    }
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up BLUETTI binary sensors from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices
    entities: list[BinarySensorEntity] = []

    for device in bluetti_devices.devices:
        entities.extend(
            BluettiBinarySensor(device, state, BINARY_SENSOR_MAP[state.fn_code])
            for state in device.states
            if state.fn_type == "SENSOR" and state.fn_code in BINARY_SENSOR_MAP
        )
        entities.append(BluettiCloudApiBinarySensor(device))

    if entities:
        async_add_entities(entities)

    return True


class BluettiBinarySensor(BluettiEntity, BinarySensorEntity):
    """BLUETTI binary sensor for online/offline state."""

    def __init__(self, device: BluettiDevice, state: BluettiState, meta: dict[str, Any]) -> None:
        super().__init__(device, state)
        self._meta = meta

        self._attr_name = meta["name"]
        self._attr_device_class = meta.get("device_class")
        # Connectivity status is diagnostic information, not a primary
        # measurement.
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return self._state_obj.fn_value == "1"


class BluettiCloudApiBinarySensor(BluettiCloudHealthEntity, BinarySensorEntity):
    """
    Whether the device's latest poll got real readings from the cloud.

    Off for every failure, and for an answer with no readings in it: the
    cloud gave nothing usable.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, device: BluettiDevice) -> None:
        super().__init__(device, "cloud_health_api")

    @property
    def is_on(self) -> bool | None:
        last_poll = self._coordinator.last_poll
        return last_poll.outcome is PollOutcome.OK if last_poll is not None else None
