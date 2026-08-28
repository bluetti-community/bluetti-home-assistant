"""Tests for the OAuth2 device-selection config flow step (oauth.py)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.helpers.json import JSONEncoder
from pybluetti import UnifyResponse, UserProduct
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import ACCOUNT_UNIQUE_ID, DOMAIN, INTEGRATION_NAME
from custom_components.bluetti.oauth import OAuth2FlowHandler


def _make_flow(hass) -> OAuth2FlowHandler:
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {}
    flow._oauth_data = {
        "auth_implementation": "bluetti",
        "token": {"access_token": "tok", "expires_at": 9999999999},
    }
    return flow


async def test_new_entry_products_are_json_serializable(hass):
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "create_entry"
    stored_products = result["data"]["products"]
    assert all(isinstance(p, dict) for p in stored_products)
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(result["data"], cls=JSONEncoder)


async def test_new_entry_gets_account_unique_id(hass):
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()

    await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert flow.unique_id == ACCOUNT_UNIQUE_ID


async def test_merge_into_existing_entry_by_unique_id(hass):
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": [{"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}]},
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    # Merging into an existing entry is only allowed for a reauth/reconfigure
    # re-run - a plain "Add Integration" flow finding an existing entry
    # rejects it as already_configured instead (see the second-account test).
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [UserProduct(sn="SN1", name="New Device", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert set(updated.options["devices"]) == {"SN0", "SN1"}
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN0", "SN1"}
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(dict(updated.data), cls=JSONEncoder)


async def test_legacy_entry_without_unique_id_is_adopted(hass):
    """Entries created before ACCOUNT_UNIQUE_ID existed must still be found."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": []},
        options={"devices": []},
    )
    legacy_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [UserProduct(sn="SN1", name="New Device", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(legacy_entry.entry_id)
    assert updated.unique_id == ACCOUNT_UNIQUE_ID
    assert updated.options["devices"] == ["SN1"]


async def test_second_account_via_fresh_flow_aborts_already_configured(hass):
    """
    A plain (non-reauth/reconfigure) flow rejects a second account.

    Regression test: authenticating a different BLUETTI account through a
    fresh "Add Integration" flow while one is already configured used to
    silently merge into the existing entry and overwrite its stored token,
    leaving the first account's retained devices inaccessible. It must
    instead abort cleanly, before even calling bind_devices() (otherwise a
    rejected setup still performs a real, wasted cloud-side bind).
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti",
            "token": {"access_token": "original-token"},
            "products": [{"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}],
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    # _make_flow's flow.context == {} - self.source is None, matching a
    # real "Add Integration" flow (never reauth/reconfigure).
    flow._products = [UserProduct(sn="SN1", name="Second Account Device", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    flow._product_client.bind_devices.assert_not_awaited()

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "original-token"}
    assert updated.options["devices"] == ["SN0"]


async def test_bind_devices_failure_aborts_cannot_connect(hass):
    flow = _make_flow(hass)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.side_effect = RuntimeError("boom")

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_bind_devices_rejected_response_aborts_cannot_connect(hass):
    """
    A rejected bind (nonzero msgCode) must not be treated as success.

    Regression test: bind_devices() returns UnifyResponse | str and does not
    raise on a rejected bind - the result used to be discarded entirely, so
    the flow created a config entry for devices the cloud never bound.
    """
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=1)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_new_entry_only_caches_selected_products(hass):
    """
    Regression test: entry.data["products"] used to cache every product on
    the account, not just the ones the user actually selected. A device
    left unselected here (SN2) would then, when added later, look like it
    was already cached and reuse this stale snapshot instead of a fresh
    fetch.
    """
    flow = _make_flow(hass)
    flow._products = [
        UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
        UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "create_entry"
    stored_sns = {p["sn"] for p in result["data"]["products"]}
    assert stored_sns == {"SN1"}


async def test_get_user_products_failure_aborts_cannot_connect(hass):
    flow = _make_flow(hass)

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(side_effect=RuntimeError("boom"))
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failed_envelope_aborts_cannot_connect(hass):
    flow = _make_flow(hass)

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=None, is_ok=lambda: False)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_no_devices_available_aborts(hass):
    flow = _make_flow(hass)

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_all_devices_exists_aborts(hass):
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": []},
        options={"devices": ["SN1"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    product = UserProduct(sn="SN1", name="Already Added", stateList=[], online="1")

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_reconfigure_token_updates_existing_entry(hass):
    """When re-running the flow for an existing entry_id, only the token is refreshed."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"auth_implementation": "bluetti", "token": {"access_token": "old"}, "products": []},
        options={"devices": []},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}
    assert updated.data["auth_implementation"] == "bluetti"


async def test_reconfigure_token_missing_entry_aborts(hass):
    """entry_id in context but the entry itself is gone (e.g. removed mid-flow)."""
    flow = _make_flow(hass)
    flow.context = {"entry_id": "does-not-exist"}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"
