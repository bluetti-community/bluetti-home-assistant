"""Tests for the BLUETTI options flow (add devices without re-authenticating)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.helpers.json import JSONEncoder
from modbus_connection.exceptions import ModbusConnectionError
from pybluetti import UserProduct
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.options_flow import BluettiOptionsFlowHandler


def _flow(hass, entry) -> BluettiOptionsFlowHandler:
    flow = BluettiOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


def _entry(hass, *, products=None, devices=None, modbus=None) -> MockConfigEntry:
    options = {"devices": devices or []}
    if modbus is not None:
        options["modbus"] = modbus
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok"},
            "products": products or [],
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_shows_form_with_available_devices(hass):
    entry = _entry(hass, devices=["SN1"])
    flow = _flow(hass, entry)
    products = [
        UserProduct(sn="SN1", name="Already added", stateList=[], online="1"),
        UserProduct(sn="SN2", name="New device", stateList=[], online="1"),
    ]

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_no_devices_available_aborts(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[])
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_all_devices_already_enabled_aborts(hass):
    entry = _entry(hass, devices=["SN1"])
    flow = _flow(hass, entry)
    products = [UserProduct(sn="SN1", name="Already added", stateList=[], online="1")]

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_fetch_failure_aborts_cannot_connect(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(side_effect=RuntimeError("boom"))
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_submit_binds_and_merges_devices_and_products(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Existing", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._products = [UserProduct(sn="SN2", name="New Device", stateList=[], online="1")]

    result = await flow.async_step_init(user_input={"devices": ["SN2"]})

    assert result["type"] == "create_entry"
    assert set(result["data"]["devices"]) == {"SN1", "SN2"}
    flow._product_client.bind_devices.assert_awaited_once_with({"bindSnList": ["SN2"]})

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN1", "SN2"}
    json.dumps(dict(updated.data), cls=JSONEncoder)  # must stay JSON-serializable


async def test_submit_bind_failure_aborts_cannot_connect(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.side_effect = RuntimeError("boom")

    result = await flow.async_step_init(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_config_flow_exposes_options_flow(hass):
    from custom_components.bluetti.config_flow import BluettiConfigFlow

    entry = _entry(hass)
    flow = BluettiConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, BluettiOptionsFlowHandler)


async def test_init_shows_menu_when_a_modbus_capable_device_is_enabled(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert set(result["menu_options"]) == {"add_devices", "configure_modbus"}


async def test_init_falls_through_to_add_devices_when_enabled_device_is_not_modbus_capable(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "AC200L", "stateList": [], "online": "1", "model": "AC200L"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(return_value=SimpleNamespace(data=[]))
        result = await flow.async_step_init(user_input=None)

    # AC200L doesn't support Modbus, so no menu is shown and this falls
    # through to the plain add-devices form (which then aborts since there
    # are no more devices to add - the point being tested is "no menu").
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_configure_modbus_shows_form_with_only_modbus_capable_enabled_devices(hass):
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"},
            {"sn": "SN2", "name": "Other", "stateList": [], "online": "1", "model": "AC200L"},
        ],
        devices=["SN1", "SN2"],
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_configure_modbus(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "configure_modbus"
    assert list(result["data_schema"].schema["device_sn"].container) == ["SN1"]


async def test_configure_modbus_success_stores_connection_in_options(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    client = MagicMock()
    client.read = AsyncMock(return_value=[])
    client.aclose = AsyncMock()

    with patch(
        "custom_components.bluetti.options_flow.BluettiModbusClient", return_value=client
    ) as client_cls:
        result = await flow.async_step_configure_modbus(
            user_input={"device_sn": "SN1", "host": "10.2.1.60", "port": 502}
        )

    client_cls.assert_called_once_with("10.2.1.60", 502, "balco260")
    client.aclose.assert_awaited_once()
    assert result["type"] == "create_entry"

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["modbus"] == {"SN1": {"host": "10.2.1.60", "port": 502}}


async def test_configure_modbus_connection_failure_reshows_form_with_error(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    client = MagicMock()
    client.read = AsyncMock(side_effect=ModbusConnectionError("no route to host"))
    client.aclose = AsyncMock()

    with patch("custom_components.bluetti.options_flow.BluettiModbusClient", return_value=client):
        result = await flow.async_step_configure_modbus(
            user_input={"device_sn": "SN1", "host": "10.2.1.60", "port": 502}
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"
    client.aclose.assert_awaited_once()

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert "modbus" not in updated.options
