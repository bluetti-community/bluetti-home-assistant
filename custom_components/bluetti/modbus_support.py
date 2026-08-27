"""Model-to-Modbus-device-type mapping for the optional local Modbus data source."""

from __future__ import annotations

# Matches bluetti_modbus_lib.devices.getter.get_device()'s recognized device
# types. "smeter" is deliberately excluded - it's a standalone smart-meter
# accessory, never a power station's own `UserProduct.model` value.
MODBUS_CAPABLE_DEV_TYPES = {"balco260", "ep2000"}


def modbus_dev_type_for_model(model: str | None) -> str | None:
    """Return the bluetti_modbus_lib device type for a cloud model string, or None."""
    normalized = (model or "").strip().lower()
    return normalized if normalized in MODBUS_CAPABLE_DEV_TYPES else None
