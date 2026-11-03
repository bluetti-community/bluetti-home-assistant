"""Diagnostics support for the BLUETTI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BluettiConfigEntry
from .coordinator import BluettiDeviceCoordinator
from .poll_history import failure_windows

TO_REDACT = {"token", "access_token", "refresh_token", "products"}

# Polls listed one by one; the failure windows still cover the whole history.
RECENT_POLLS = 200


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BluettiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    # device_id is the device's real BLUETTI serial number, tied to
    # ownership/warranty - it shouldn't be exposed in a diagnostics dump any
    # more than a token would be. Alias it to a stable per-dump "device_N"
    # instead of blanking it outright, so multiple devices in one dump can
    # still be told apart and cross-referenced against "coordinators" below.
    aliases = {
        device.device_id: f"device_{i + 1}"
        for i, device in enumerate(runtime_data.bluetti_devices.devices)
    }

    devices = [
        {
            "device_id": aliases[device.device_id],
            "model": device.model,
            "online": device.online,
            "states": [
                {
                    "fn_code": state.fn_code,
                    "fn_type": state.fn_type,
                    "fn_value": state.fn_value,
                    # Shows whether a SENSOR-type state was actually turned
                    # into an entity, or silently skipped because its
                    # sensorType isn't recognized (see sensor.SENSOR_MAP) -
                    # otherwise that's only visible in the logs.
                    "sensor_info": state.sensor_info or None,
                }
                for state in device.states
            ],
        }
        for device in runtime_data.bluetti_devices.devices
    ]

    coordinators = {
        aliases.get(device_id, device_id): {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            **_poll_diagnostics(coordinator),
        }
        for device_id, coordinator in runtime_data.coordinators.items()
    }

    entry_options = dict(entry.options)
    if "devices" in entry_options:
        # Same real serial numbers as above (the enabled-devices list), so
        # alias them the same way rather than leaving them in the clear here.
        entry_options["devices"] = [
            aliases.get(sn, sn) for sn in entry_options["devices"]
        ]

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": entry_options,
        "devices": devices,
        "coordinators": coordinators,
    }


def _poll_diagnostics(coordinator: BluettiDeviceCoordinator) -> dict[str, Any]:
    """
    What the cloud answered each poll, before any ride-out, in UTC.

    The records carry no device id: the coordinator they sit under is
    already keyed by its alias.
    """
    history = coordinator.poll_history()
    last_poll = coordinator.last_poll
    return {
        "history_since": history[0].started.isoformat() if history else None,
        "last_poll": last_poll.as_dict() if last_poll is not None else None,
        "recent_polls": [record.as_dict() for record in history[-RECENT_POLLS:]],
        "failure_windows": failure_windows(history),
    }
