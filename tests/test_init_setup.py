"""Tests for async_setup_entry() in __init__.py."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from modbus_connection.exceptions import ModbusConnectionError
from pybluetti import ApplicationRuntimeException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti import ISSUE_ID_WEBSOCKET_ERROR
from custom_components.bluetti.const import DOMAIN


def _entry(hass, *, products=None, devices=None, modbus=None) -> MockConfigEntry:
    options = {"devices": devices or []}
    if modbus is not None:
        options["modbus"] = modbus
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": products or [],
        },
        options=options,
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
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bluetti_devices.devices == []
    assert entry.runtime_data.coordinators == {}
    assert entry.runtime_data.modbus_coordinators == {}
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_websocket_on_error_creates_a_repair_issue(hass, enable_custom_integrations):
    entry = _entry(hass)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        on_error = mock_stomp_cls.call_args.kwargs["on_error"]
        on_error(ApplicationRuntimeException(msgCode=1042, errMessage="Upgrade required"))

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID_WEBSOCKET_ERROR)
    assert issue is not None
    assert issue.translation_key == "websocket_error"
    assert issue.translation_placeholders == {"error": "Upgrade required"}
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING


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
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
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
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_registers_binary_sensor_under_its_own_domain(hass, enable_custom_integrations):
    # Regression test: BluettiBinarySensor entities used to be appended to
    # the `entities` list handed to the sensor platform's async_add_entities,
    # so they were registered under sensor.* instead of binary_sensor.* -
    # entity_id domain is decided by which EntityPlatform.async_add_entities
    # call registers the entity, not by the entity class's own base class.
    state_list = [{"fnCode": "onLine", "fnName": "Online", "fnValue": "1", "fnType": "SENSOR"}]
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": state_list, "online": "1"}],
        devices=["SN1"],
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=state_list)

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, "SN1_onLine")
    assert entity_id is not None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "SN1_onLine") is None


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
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(side_effect=fake_get_device_status)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert set(coordinators.keys()) == {"SN1", "SN2"}
    assert all(c.last_update_success for c in coordinators.values())


async def test_one_device_failing_first_refresh_does_not_orphan_the_others(hass, enable_custom_integrations):
    # Regression test: asyncio.gather() without return_exceptions=True
    # propagates the first exception as soon as it happens, without waiting
    # for (or cancelling) the other coordinators' still-in-flight first
    # refreshes - they kept running as untracked background tasks that could
    # still mutate state after setup had already moved on to SETUP_RETRY.
    # SN2 fails immediately; SN1 is deliberately slower, so if it were left
    # running unawaited, hass.config_entries.async_setup() would return
    # before SN1's own refresh actually completed.
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    sn1_refresh_completed = asyncio.Event()

    async def fake_get_device_status(sn):
        if sn == "SN2":
            raise RuntimeError("boom")
        await asyncio.sleep(0.05)
        sn1_refresh_completed.set()
        return MagicMock(data=[MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])])

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(side_effect=fake_get_device_status)

        assert not await hass.config_entries.async_setup(entry.entry_id)

    # By the time async_setup() has returned, SN1's slower refresh must
    # have already completed too - not left running unawaited.
    assert sn1_refresh_completed.is_set()


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
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_ensure_credential.assert_awaited_once_with(hass)
    assert mock_get_impl.await_count == 2
    mock_stomp_cls.return_value.connect.assert_awaited_once()


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


async def test_async_setup_entry_wires_up_modbus_coordinator_for_capable_device(
    hass, enable_custom_integrations
):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
        modbus={"SN1": {"host": "10.2.1.60", "port": 502}},
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls, \
         patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient") as client_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )
        client_cls.return_value.read = AsyncMock(return_value=[])
        client_cls.return_value.aclose = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    client_cls.assert_called_once_with("10.2.1.60", 502, "balco260")
    assert "SN1" in entry.runtime_data.modbus_coordinators
    assert entry.runtime_data.modbus_coordinators["SN1"].last_update_success


async def test_modbus_first_refresh_failure_does_not_prevent_cloud_entities_from_loading(
    hass, enable_custom_integrations
):
    # Local Modbus is opt-in/supplementary - a hiccup here at startup must
    # not fail the whole config entry (and take the cloud entities down
    # with it). A failed first refresh should just leave that device's
    # Modbus entities unavailable until the coordinator's own next poll
    # succeeds, same as the cloud path already promises.
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
        modbus={"SN1": {"host": "10.2.1.60", "port": 502}},
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls, \
         patch("custom_components.bluetti.ProductClient") as mock_product_cls, \
         patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient") as client_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )
        client_cls.return_value.read = AsyncMock(side_effect=ModbusConnectionError("no route to host"))
        client_cls.return_value.aclose = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "SN1" in entry.runtime_data.coordinators
    assert entry.runtime_data.coordinators["SN1"].last_update_success
    assert not entry.runtime_data.modbus_coordinators["SN1"].last_update_success
