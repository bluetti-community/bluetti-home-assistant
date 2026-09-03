"""Writable Bluetti Modbus registers, e.g. battery SOC thresholds."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BluettiConfigEntry
from .modbus_entity import BluettiModbusEntity
from .models import BluettiData

# Writes go straight to the device over Modbus TCP - serialize them, the
# same reasoning select.py/switch.py already apply to cloud writes.
PARALLEL_UPDATES = 1

# b_soc_low/b_soc_high (57016/57017): battery empty/full SOC thresholds,
# 0-100% - genuinely user-configurable settings, not readings. Only created
# where bluetti_modbus_lib actually marks the field writable (currently
# Balco260 - see that library's import.py); sensor.py's own Modbus loop
# falls back to its normal read-only handling everywhere else, so nothing
# is lost on a device where it isn't (e.g. EP2000 today).
MODBUS_FIELDS_SHOWN_VIA_NUMBER = {"b_soc_low", "b_soc_high"}

_MIN_VALUE = 0
_MAX_VALUE = 100


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Bluetti number entities from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices
    entities: list[BluettiModbusNumber] = []

    for device_id, modbus_coordinator in config_entry.runtime_data.modbus_coordinators.items():
        modbus_device = bluetti_devices.get_device_by_sn(device_id)
        if modbus_device is None:
            continue
        for field_name in MODBUS_FIELDS_SHOWN_VIA_NUMBER:
            field = modbus_coordinator.device.get_field(field_name)
            if field is not None and field.writable:
                entities.append(
                    BluettiModbusNumber(modbus_device, modbus_coordinator, field_name)
                )

    if entities:
        async_add_entities(entities)

    return True


class BluettiModbusNumber(BluettiModbusEntity, NumberEntity):
    """A writable register sourced from a device's optional local Modbus connection."""

    _attr_native_min_value = _MIN_VALUE
    _attr_native_max_value = _MAX_VALUE
    _attr_native_step = 1

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the device."""
        # No optimistic update - native_value always reads live from
        # coordinator.data below, same as BluettiModbusSensor and every
        # other entity in this integration (e.g. BluettiSwitch.is_on).
        # The next poll reflects whatever the device actually accepted.
        await self.coordinator.device.write(self._field_name, int(value))

    @property
    def native_value(self) -> float | None:
        field = (self.coordinator.data or {}).get(self._field_name)
        return field.value if field else None
