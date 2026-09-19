"""Tests for BluettiDeviceCoordinator."""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pybluetti import ApplicationRuntimeException, HttpStatusException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.models import BluettiDevice


def _make_device() -> BluettiDevice:
    return BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")


async def test_coordinator_links_itself_to_the_device(hass):
    device = _make_device()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)

    assert device.coordinator is coordinator
    assert coordinator.device is device


async def test_coordinator_update_success(hass):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    data = await coordinator._async_update_data()

    assert data is device
    device.async_refresh_from_api.assert_awaited_once()


async def test_coordinator_raises_update_failed_on_generic_error(hass):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(side_effect=RuntimeError("boom"))
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_update_failed_on_non_auth_api_error(hass):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=ApplicationRuntimeException(msgCode=500, errMessage="server error")
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize("msg_code", [401, 805])
async def test_coordinator_raises_auth_failed_on_auth_error_codes(hass, msg_code):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=ApplicationRuntimeException(msgCode=msg_code, errMessage="unauthorized")
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_a_lone_transient_gateway_error_is_retried_once(hass):
    # #53: a single HTTP 504 after ~10 s, with the next poll succeeding,
    # failed the whole poll - every entity unavailable for 30 s and an ERROR
    # in the log. One immediate retry absorbs it.
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=[HttpStatusException(504, "Gateway Timeout"), None]
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    data = await coordinator._async_update_data()

    assert data is device
    assert device.async_refresh_from_api.await_count == 2


async def test_a_second_transient_failure_fails_the_poll_naming_the_cause(hass):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=HttpStatusException(504, "Gateway Timeout", data="<html>")
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed, match=r"HTTP 504 Gateway Timeout \(code 504\)"):
        await coordinator._async_update_data()

    assert device.async_refresh_from_api.await_count == 2


@pytest.mark.parametrize("err", [TimeoutError(), aiohttp.ClientConnectionError("reset")])
async def test_a_timeout_or_connection_error_is_retried_once(hass, err):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(side_effect=[err, None])
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    data = await coordinator._async_update_data()

    assert data is device
    assert device.async_refresh_from_api.await_count == 2


async def test_a_non_transient_http_error_is_not_retried(hass):
    # A 404 (or any 4xx but the auth codes) is not a gateway hiccup.
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(side_effect=HttpStatusException(404, "Not Found"))
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed, match="HTTP 404 Not Found"):
        await coordinator._async_update_data()

    assert device.async_refresh_from_api.await_count == 1


async def test_an_api_msg_code_is_not_retried(hass):
    # An API-level failure (HTTP 200, non-zero msgCode in the body) is not a
    # gateway error, even when the code happens to look like one.
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=ApplicationRuntimeException(msgCode=504, errMessage="server says no")
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed, match=r"server says no \(code 504\)"):
        await coordinator._async_update_data()

    assert device.async_refresh_from_api.await_count == 1


async def test_an_auth_error_on_the_http_layer_is_still_reauth(hass):
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(side_effect=HttpStatusException(401, "Unauthorized"))
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
