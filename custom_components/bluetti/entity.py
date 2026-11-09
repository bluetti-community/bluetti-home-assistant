"""Base entity for the BLUETTI integration."""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TRANSLATED_FN_CODES
from .coordinator import BluettiDeviceCoordinator
from .models import BluettiDevice, BluettiState


def device_info(device: BluettiDevice) -> DeviceInfo:
    """The device registry entry every entity of a BLUETTI device attaches to."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id)},
        name=device.name,
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.sn,
    )


class BluettiEntity(CoordinatorEntity[BluettiDeviceCoordinator]):
    """
    Common behavior shared by all BLUETTI entities.

    Subclasses name the entity after calling super().__init__(), through
    _set_cloud_name(): a translated name for the fn_codes in
    TRANSLATED_FN_CODES, the cloud's own (or a static label) otherwise.
    """

    _attr_has_entity_name = True

    def __init__(self, device: BluettiDevice, state: BluettiState) -> None:
        assert device.coordinator is not None, (  # noqa: S101 - a real invariant, not test-only theater
            "entities must be created after the device's coordinator is wired up"
        )
        super().__init__(device.coordinator)
        self._device = device
        self._state_obj = state

        self._attr_unique_id = f"{device.device_id}_{state.fn_code}"
        # fn_code doubles as the icon translation key (see icons.json); it's
        # a stable, bounded identifier already used for unique_id above.
        # Lowercased because translation keys must match hassfest's
        # [a-z0-9-_]+ pattern, but the cloud's fn_code values are mixed-case
        # (e.g. "SOC", "SetCtrlAc") - icons.json's keys are lowercased to
        # match.
        self._attr_translation_key = state.fn_code.lower()
        self._attr_device_info = device_info(device)

    def _set_cloud_name(self, name: str, platform: str) -> None:
        """Use the cloud's name, unless this fn_code has a translated one."""
        if self._attr_translation_key not in TRANSLATED_FN_CODES.get(platform, ()):
            self._attr_name = name

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        # The power switch itself should stay controllable even if the
        # device otherwise reports as offline.
        if self._state_obj.fn_code == "SetCtrlPowerOn":
            return True
        return self._device.online


class BluettiCloudHealthEntity(Entity):
    """
    How the cloud answered a device's polls, on that device.

    Not a BluettiEntity: there is no cloud state behind it, and it has to
    stay available exactly when the cloud fails - unavailable only before
    the first poll. Updated after every poll through the coordinator's poll
    listener, failed ones included. Disabled by default: it is for
    troubleshooting, and would otherwise fill every recorder.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, device: BluettiDevice, key: str) -> None:
        assert device.coordinator is not None, (  # noqa: S101 - a real invariant, not test-only theater
            "entities must be created after the device's coordinator is wired up"
        )
        self._device = device
        self._coordinator = device.coordinator
        # The prefix keeps it clear of every cloud fn_code (see
        # BluettiEntity's unique_id).
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(device)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_poll_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._coordinator.last_poll is not None
