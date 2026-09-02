"""Base entity for BLUETTI's optional local Modbus data source."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .modbus_coordinator import BluettiModbusCoordinator
from .models import BluettiDevice


def _modbus_sw_version(coordinator: BluettiModbusCoordinator) -> str | None:
    """
    Firmware version string from the device's own Modbus-read d_ver_arm/d_ver_dsp.

    Not sensor entities (see sensor.py's MODBUS_FIELDS_SHOWN_VIA_DEVICE_INFO)
    - matches home-assistant/core's bluetti_modbus integration, which feeds
    these same two fields into DeviceInfo.sw_version instead of exposing
    them as sensors. None (both fields absent) before the coordinator's
    first successful refresh.
    """
    data = coordinator.data or {}
    arm = data.get("d_ver_arm")
    dsp = data.get("d_ver_dsp")
    if arm is None and dsp is None:
        return None
    return f"ARM {arm.value if arm else '?'}, DSP {dsp.value if dsp else '?'}"


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusCoordinator]):
    """
    Common behavior shared by BLUETTI entities sourced from local Modbus.

    Uses the same device identifier as BluettiEntity so Modbus-sourced
    entities group under the same Home Assistant device as their
    cloud-sourced siblings, rather than appearing as a separate device.
    """

    _attr_has_entity_name = True

    def __init__(
        self, device: BluettiDevice, coordinator: BluettiModbusCoordinator, field_name: str
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._field_name = field_name

        self._attr_unique_id = f"{device.device_id}_modbus_{field_name}"
        # Unlike BluettiEntity's fn_code (dynamic, cloud-supplied per
        # device/firmware), bluetti_modbus_lib field names are static and
        # known at development time, so a real translation_key applies here.
        self._attr_translation_key = field_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.sn,
            sw_version=_modbus_sw_version(coordinator),
            # The device's own local web server, the same one Modbus TCP has
            # to be enabled through in the first place. Port 80: the Modbus
            # port (coordinator.host's companion port) is a different,
            # unrelated service on the same device.
            configuration_url=f"http://{coordinator.host}",
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self._field_name in (self.coordinator.data or {})
