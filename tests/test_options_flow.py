"""Tests for the BLUETTI options flow (add devices without re-authenticating)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.json import JSONEncoder
from pybluetti import UnifyResponse, UserProduct
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.options_flow import BluettiOptionsFlowHandler


def _flow(hass, entry) -> BluettiOptionsFlowHandler:
    flow = BluettiOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


def _entry(hass, *, products=None, devices=None, gateway=None) -> MockConfigEntry:
    options = {"devices": devices or []}
    data = {
        "auth_implementation": DOMAIN,
        "token": {"access_token": "tok"},
        "products": products or [],
    }
    if gateway is not None:
        data["gateway"] = gateway
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options)
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
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    # step_id matches the method that actually owns the form
    # (async_step_add_devices), not the router (async_step_init) that
    # delegated to it - this is what lets the real flow manager correctly
    # re-invoke async_step_add_devices on submit instead of re-routing.
    assert result["step_id"] == "add_devices"


async def test_no_devices_available_aborts(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
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
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_fetch_failure_aborts_cannot_connect(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(side_effect=RuntimeError("boom"))
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
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)
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


async def test_submit_bind_rejected_response_aborts_cannot_connect(hass):
    """A rejected bind (nonzero msgCode) must not be treated as success."""
    entry = _entry(hass)
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=1)

    result = await flow.async_step_init(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failed_envelope_aborts_cannot_connect(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=None, is_ok=lambda: False)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_config_flow_exposes_options_flow(hass):
    from custom_components.bluetti.config_flow import BluettiConfigFlow

    entry = _entry(hass)
    flow = BluettiConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, BluettiOptionsFlowHandler)


async def test_init_goes_straight_to_add_devices(hass):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "AC200L", "stateList": [], "online": "1", "model": "AC200L"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(return_value=SimpleNamespace(data=[], is_ok=lambda: True))
        result = await flow.async_step_init(user_input=None)

    # No menu: the add-devices step itself, which aborts here since there
    # are no more devices to add.
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_add_devices_through_real_flow_manager_keeps_the_enabled_devices(
    hass, enable_custom_integrations
):
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Balco", "stateList": [], "online": "1", "model": "Balco260"}],
        devices=["SN1"],
    )
    products = [UserProduct(sn="SN2", name="New Device", stateList=[], online="1")]

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        mock_client_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "add_devices"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"devices": ["SN2"]}
        )

    assert result["type"] == "create_entry"

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert set(updated.options["devices"]) == {"SN1", "SN2"}


async def test_adding_devices_asks_the_data_center_the_entry_recorded(hass):
    entry = _entry(hass, gateway="eu")
    flow = _flow(hass, entry)

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
        )
        await flow.async_step_init(user_input=None)

    assert mock_client_cls.call_args.args[1] == "https://gwde.bluettipower.com"



async def test_add_devices_does_not_offer_a_device_without_cloud_access(hass):
    entry = _entry(hass)
    flow = _flow(hass, entry)
    answer = SimpleNamespace(
        data=[
            UserProduct(sn="NEW", name="New", stateList=[], online="1", supportNetwork="1"),
            UserProduct(sn="BLE", name="Ble", stateList=[], online="1", supportNetwork="0"),
        ],
        is_ok=lambda: True,
    )

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(return_value=answer)
        result = await flow.async_step_add_devices(user_input=None)

    assert set(result["data_schema"].schema["devices"].options) == {"NEW"}


async def test_add_devices_aborts_when_no_device_has_cloud_access(hass, caplog):
    entry = _entry(hass)
    flow = _flow(hass, entry)
    answer = SimpleNamespace(
        data=[UserProduct(sn="BLE", model="EB3A", stateList=[], online="1", supportNetwork="0")],
        is_ok=lambda: True,
    )

    with patch("custom_components.bluetti.options_flow.async_get_clientsession"), \
         patch("custom_components.bluetti.options_flow.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products_v2 = AsyncMock(return_value=answer)
        result = await flow.async_step_add_devices(user_input=None)

    assert result["reason"] == "no_devices_available"
    assert "['EB3A']" in caplog.text
