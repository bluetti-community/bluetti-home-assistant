"""Tests for async_setup_entry() in __init__.py."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN


def _entry(hass, *, products=None, devices=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": products or [],
        },
        options={"devices": devices or []},
    )
    entry.add_to_hass(hass)
    return entry


async def test_async_setup_entry_with_no_devices(hass, enable_custom_integrations):
    entry = _entry(hass)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bluetti_devices.devices == []
    assert entry.runtime_data.coordinators == {}
    mock_stomp_cls.return_value.connect.assert_called_once()


async def test_async_setup_entry_with_a_device(hass, enable_custom_integrations):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    devices = entry.runtime_data.bluetti_devices.devices
    assert len(devices) == 1
    assert devices[0].device_id == "SN1"
    assert "SN1" in entry.runtime_data.coordinators
    mock_stomp_cls.return_value.connect.assert_called_once()


async def test_async_setup_entry_with_multiple_devices_refreshes_concurrently(hass, enable_custom_integrations):
    # Each device's first refresh is run via asyncio.gather() instead of
    # sequentially, so setup time doesn't scale linearly with device count.
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient"), \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_product_cls.return_value.get_device_status = AsyncMock(side_effect=fake_get_device_status)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert set(coordinators.keys()) == {"SN1", "SN2"}
    assert all(c.last_update_success for c in coordinators.values())


async def test_async_setup_entry_reimports_missing_oauth_credential(hass, enable_custom_integrations):
    # If the Application Credential backing the OAuth2 implementation was
    # ever lost (e.g. a partial backup restore), async_get_config_entry_
    # implementation raises ValueError("Implementation not available").
    # Setup should re-import the default credential and retry once instead
    # of failing forever.
    entry = _entry(hass)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(side_effect=[ValueError("Implementation not available"), MagicMock()]),
         ) as mock_get_impl, \
         patch(
             "custom_components.bluetti.async_ensure_default_credential",
             AsyncMock(),
         ) as mock_ensure_credential, \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_ensure_credential.assert_awaited_once_with(hass)
    assert mock_get_impl.await_count == 2
    mock_stomp_cls.return_value.connect.assert_called_once()


async def test_async_setup_entry_retries_on_failure(hass, enable_custom_integrations):
    entry = _entry(hass)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(side_effect=RuntimeError("boom")),
         ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_retries_when_credential_stays_missing(hass, enable_custom_integrations):
    # Re-importing the default credential doesn't help if the underlying
    # cause isn't a missing credential (e.g. the application_credentials
    # component itself isn't ready yet) - setup should still fall back to
    # Home Assistant's normal ConfigEntryNotReady retry instead of raising.
    entry = _entry(hass)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(side_effect=ValueError("Implementation not available")),
         ), \
         patch(
             "custom_components.bluetti.async_ensure_default_credential",
             AsyncMock(),
         ) as mock_ensure_credential:
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_ensure_credential.assert_awaited_once_with(hass)
