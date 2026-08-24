"""The BLUETTI integration."""
# from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, storage
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.bluetti import APPLICATION_PROFILE
from .api.product_client import ProductClient
from .api.websocket import StompClient
from .application_credentials import async_ensure_default_credential
from .const import DOMAIN
from .coordinator import BluettiDeviceCoordinator
from .model.product import UserProduct
from .models import BluettiData
from .oauth import AsyncConfigEntryAuth, AuthTokenRefresh

__LOGGER__ = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.SELECT]


@dataclass
class BluettiRuntimeData:
    """Runtime data stored on a BLUETTI config entry."""

    auth: AsyncConfigEntryAuth
    bluetti_devices: BluettiData
    stomp_client: StompClient
    coordinators: dict[str, BluettiDeviceCoordinator]


type BluettiConfigEntry = ConfigEntry[BluettiRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    try:
        await APPLICATION_PROFILE.load_config(hass)

        enabled_devices = entry.options.get("devices", [])
        all_products_data: list[dict] = entry.data.get("products", [])
        all_products: list[UserProduct] = [
            UserProduct.model_validate(p) if isinstance(p, dict) else p
            for p in all_products_data
        ]

        """OAUTH2: get the access token."""
        try:
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
        except ValueError:
            # The OAuth2 implementation is resolved from the BLUETTI
            # Application Credential in HA storage. If that credential was
            # ever lost (e.g. a partial backup restore, or an entry that was
            # created without going through the config flow), setup would
            # otherwise fail with this same error forever. Re-import the
            # credential (a no-op if it's already there) and retry once
            # before giving up.
            __LOGGER__.warning(
                "BLUETTI OAuth implementation not found, re-importing the "
                "default credential and retrying"
            )
            await async_ensure_default_credential(hass)
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
        __LOGGER__.debug("OAuth implementation is: %s", implementation.__class__)

        httpSession = async_get_clientsession(hass)
        oAuth2Session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
        auth = AsyncConfigEntryAuth(httpSession, oAuth2Session)

        authTokenRefresh = AuthTokenRefresh(hass,entry,oAuth2Session)
        authTokenRefresh.start_token_check()

        # await oAuth2Session.async_ensure_token_valid()
        access_token = oAuth2Session.token["access_token"]
        product_client = ProductClient(httpSession, access_token,hass)
        # products = await product_client.get_user_products()
        # print(products.data[0].__class__)
        # print(products.data)
    except Exception as err:
        raise ConfigEntryNotReady(f"BLUETTI setup failed: {err}") from err

    selected_products = [p for p in all_products if p.sn in enabled_devices]

    bluetti_devices = BluettiData(hass, selected_products)

    # Register WebSocket
    stomp_client = StompClient(APPLICATION_PROFILE.config["server"]["wss"], access_token, bluetti_devices.web_socket_message_handler,hass)
    stomp_client.connect()

    coordinators: dict[str, BluettiDeviceCoordinator] = {}
    for device in bluetti_devices.devices:
        device._api_client = product_client
        device.name = device.sn
        device._hass = hass
        device._entry = entry
        device._entry_id = entry.entry_id
        coordinators[device.device_id] = BluettiDeviceCoordinator(hass, entry, device)

    # Each device's first refresh is an independent network round-trip, so
    # run them concurrently instead of one-by-one - otherwise setup time
    # scales linearly with the number of devices on the account.
    await asyncio.gather(
        *(coordinator.async_config_entry_first_refresh() for coordinator in coordinators.values())
    )

    entry.runtime_data = BluettiRuntimeData(
        auth=auth,
        bluetti_devices=bluetti_devices,
        stomp_client=stomp_client,
        coordinators=coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Reload the entry when the options flow adds more devices.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    __LOGGER__.info("bluetti init ok")

    return True


async def _async_update_listener(hass: HomeAssistant, entry: BluettiConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BluettiConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    runtime_data = getattr(entry, "runtime_data", None)
    if unloaded and runtime_data:
        try:
            runtime_data.stomp_client.disconnect()
        except Exception as e:
            __LOGGER__.warning("Error while disconnecting websocket: %s", e)
    return unloaded

async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: BluettiConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """
    Allow removing a single BLUETTI device from an existing entry.

    Home Assistant calls this when the user clicks "Delete" on a device's
    page; returning True lets it sever the device<->entry link (and cascade
    to that device's entities) on its own. This only needs to stop polling
    the device and drop it from the enabled-devices list, so a reload
    doesn't recreate it - the same bookkeeping BluettiDevice._handle_unbind
    does when the cloud reports the device unbound, minus the registry
    cleanup and reload that HA already handles for a user-initiated removal.
    """
    device_ids = {
        identifier for domain, identifier in device_entry.identifiers if domain == DOMAIN
    }
    if not device_ids:
        return False

    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data:
        runtime_data.bluetti_devices.devices = [
            d for d in runtime_data.bluetti_devices.devices if d.device_id not in device_ids
        ]
        for device_id in device_ids:
            coordinator = runtime_data.coordinators.pop(device_id, None)
            if coordinator:
                await coordinator.async_shutdown()

    current_devices = entry.options.get("devices", [])
    new_devices = [d for d in current_devices if d not in device_ids]
    if new_devices != current_devices:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "devices": new_devices}
        )

    return True


async def async_remove_entry(hass, entry: BluettiConfigEntry):
    """Handle removal of an entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data:
        try:
            runtime_data.stomp_client.disconnect()
        except Exception as e:
            __LOGGER__.warning("Error while disconnecting websocket: %s", e)

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        device_registry.async_remove_device(device.id)

    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        entity_registry.async_remove(entity.entity_id)

    store = storage.Store(hass, 1, f"{DOMAIN}_data_{entry.entry_id}.json")
    await store.async_remove()
