"""Tests for the BLUETTI Home Assistant integration."""

def devices_with_identifier(device_registry, identifier):
    """
    Devices carrying ``identifier``, on every Home Assistant the suite runs on.

    2026.9 deprecates ``async_get_device`` and mapping-style access to
    ``devices`` in favour of ``async_get_devices``; the release CI tests
    against does not have the new lookup yet.
    """
    if hasattr(device_registry, "async_get_devices"):
        return device_registry.async_get_devices(identifiers={identifier})
    device = device_registry.async_get_device(identifiers={identifier})
    return [device] if device is not None else []
