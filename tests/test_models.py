"""Tests for the BLUETTI data models."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pybluetti import ApplicationRuntimeException, UnifyResponse

from custom_components.bluetti.models import BluettiData, BluettiDevice, BluettiState


def test_state_is_switch_without_modes():
    state = BluettiState(fn_code="SetCtrlAc", fn_name="AC", fn_value="0", fn_type="SWITCH")
    assert state.is_switch() is True
    assert state.get_name_for_value() == "Off"


def test_state_set_value_switch():
    state = BluettiState(fn_code="SetCtrlAc", fn_name="AC", fn_value="0", fn_type="SWITCH")
    state.set_value("1")
    assert state.fn_value == "1"
    assert state.get_name_for_value() == "On"


def test_state_get_name_for_value_falls_back_to_raw_value():
    modes = [{"code": "0", "name": "Standard"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode", fn_name="Mode", fn_value="unmapped-value", fn_type="SELECT",
        support_mode_values=modes,
    )
    assert state.get_name_for_value() == "unmapped-value"


def test_state_repr():
    state = BluettiState(fn_code="SOC", fn_name="Battery", fn_value="80", fn_type="SENSOR")
    assert repr(state) == "<BluettiState SOC=80>"


def test_device_repr():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    assert repr(device) == "<BluettiDevice id=SN1 name=Test>"


def test_state_select_valid_value():
    modes = [{"code": "0", "name": "Standard"}, {"code": "1", "name": "Silent"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode", fn_name="Mode", fn_value="0", fn_type="SELECT",
        support_mode_values=modes,
    )
    state.set_value("1")
    assert state.fn_value == "1"
    assert state.get_name_for_value() == "Silent"


def test_state_select_invalid_value_raises():
    modes = [{"code": "0", "name": "Standard"}]
    state = BluettiState(
        fn_code="SetCtrlWorkMode", fn_name="Mode", fn_value="0", fn_type="SELECT",
        support_mode_values=modes,
    )
    with pytest.raises(ValueError):
        state.set_value("99")


def test_device_get_state_returns_none_for_missing_code():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    assert device.get_state("does-not-exist") is None


def test_state_falls_back_to_fn_code_when_fn_name_is_blank():
    """
    Some fn_codes come back from the API without a localized fnName.

    With has_entity_name = True, an empty entity name makes Home
    Assistant's frontend display the raw entity_id (which contains the
    device serial number) instead of a real label, so BluettiDevice must
    fall back to a non-empty name when building its states.
    """
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlWorkMode", "fnValue": "2", "fnType": "SELECT"}],
    )
    state = device.get_state("SetCtrlWorkMode")
    assert state.fn_name == "SetCtrlWorkMode"


def test_device_battery_level_reads_soc_state():
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SOC", "fnName": "Battery", "fnValue": "42", "fnType": "SENSOR"}],
    )
    assert device.battery_level == 42


def test_device_battery_level_defaults_to_zero_without_soc():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    assert device.battery_level == 0


def test_device_online_property():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    assert device.online is True
    device.on_line = "0"
    assert device.online is False


def test_bluetti_data_get_device_by_sn():
    fake_hass = SimpleNamespace(loop=None)
    product = SimpleNamespace(sn="SN1", online="1", name="Test", model="AC200L", stateList=[])
    data = BluettiData(fake_hass, [product])
    assert data.get_device_by_sn("SN1") is not None
    assert data.get_device_by_sn("unknown") is None


async def test_async_refresh_from_api_updates_states():
    device = BluettiDevice(
        device_id="SN1", on_line="0", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SOC", "fnName": "Battery", "fnValue": "10", "fnType": "SENSOR"}],
    )
    status_data = SimpleNamespace(
        sn="SN1", online="1", isBindByCurUser="1",
        stateList=[{"fnCode": "SOC", "fnValue": "77"}],
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[status_data], is_ok=lambda: True)

    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("SOC").fn_value == "77"


async def test_async_refresh_from_api_logs_the_cloud_answer(caplog):
    # The raw online flag and values, so a debug log shows what the cloud
    # actually sent (e.g. "online" with every reading at 0).
    device = BluettiDevice(
        device_id="SN1", on_line="0", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SOC", "fnName": "Battery", "fnValue": "10", "fnType": "SENSOR"}],
    )
    status_data = SimpleNamespace(
        sn="SN1", online="1", isBindByCurUser="1",
        stateList=[{"fnCode": "SOC", "fnValue": "0"}],
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[status_data], is_ok=lambda: True)

    with caplog.at_level(logging.DEBUG, logger="custom_components.bluetti.models"):
        await device.async_refresh_from_api()

    assert "Cloud status for SN1: online=1, values={'SOC': '0'}" in caplog.text


def _elite_200_v2(api_client: AsyncMock) -> BluettiDevice:
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Elite 200 V2",
        state_list=[
            {"fnCode": "SOC", "fnName": "Battery", "fnValue": "100", "fnType": "SENSOR"},
            {"fnCode": "DsgFullTime", "fnName": "Time to empty", "fnValue": "5994", "fnType": "SENSOR"},
            {"fnCode": "DCLoadAllTotalPower", "fnName": "DC load", "fnValue": "5", "fnType": "SENSOR"},
            {"fnCode": "SetCtrlDc", "fnName": "DC", "fnValue": "1", "fnType": "SWITCH"},
        ],
    )
    device._api_client = api_client
    return device


def _status(online: str, **values: str) -> SimpleNamespace:
    status_data = SimpleNamespace(
        sn="SN1", online=online, isBindByCurUser="1",
        stateList=[{"fnCode": code, "fnValue": value} for code, value in values.items()],
    )
    return SimpleNamespace(data=[status_data], is_ok=lambda: True)


async def test_async_refresh_from_api_takes_every_reading_at_zero_as_no_reading():
    api_client = AsyncMock()
    device = _elite_200_v2(api_client)

    # What an Elite 200 V2's cloud sent around a reconnection: online, with
    # every reading at 0 (a switch keeps its value).
    api_client.get_device_status.return_value = _status(
        "1", SOC="0", DsgFullTime="0", DCLoadAllTotalPower="0.0", SetCtrlDc="1"
    )
    await device.async_refresh_from_api()

    assert device.online is False
    assert device.get_state("SOC").fn_value == "100"
    assert device.get_state("DsgFullTime").fn_value == "5994"

    api_client.get_device_status.return_value = _status(
        "1", SOC="99", DsgFullTime="2133", DCLoadAllTotalPower="5", SetCtrlDc="1"
    )
    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("SOC").fn_value == "99"


async def test_async_refresh_from_api_keeps_a_zero_battery_level_next_to_real_readings():
    api_client = AsyncMock()
    device = _elite_200_v2(api_client)

    api_client.get_device_status.return_value = _status(
        "1", SOC="0", DsgFullTime="0", DCLoadAllTotalPower="5"
    )
    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("SOC").fn_value == "0"


async def test_async_refresh_from_api_keeps_zero_readings_of_a_unit_without_battery_level():
    # A unit without a battery level (a charger, say) idles at 0 for real.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Charger",
        state_list=[{"fnCode": "PVAllTotalPower", "fnName": "PV", "fnValue": "40", "fnType": "SENSOR"}],
    )
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = _status("1", PVAllTotalPower="0")

    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("PVAllTotalPower").fn_value == "0"


async def test_async_refresh_from_api_reads_a_value_that_is_not_a_number_as_a_reading():
    api_client = AsyncMock()
    device = _elite_200_v2(api_client)

    api_client.get_device_status.return_value = _status("1", SOC="0", DsgFullTime="--")
    await device.async_refresh_from_api()

    assert device.online is True
    assert device.get_state("DsgFullTime").fn_value == "--"


async def test_async_refresh_from_api_raises_on_failed_envelope():
    # Regression test: get_device_status() doesn't raise for a nonzero
    # msgCode (e.g. an expired token, code 805) - it returns a response
    # with data=None. Previously this fell through to the generic "empty
    # status response" RuntimeError instead of the classifiable
    # ApplicationRuntimeException the coordinator relies on for reauth.
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = UnifyResponse(
        msgId="1", msgCode=805, data=None
    )

    with pytest.raises(ApplicationRuntimeException) as exc_info:
        await device.async_refresh_from_api()

    assert exc_info.value.msgCode == 805


async def test_async_refresh_from_api_raises_on_empty_data():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[], is_ok=lambda: True)

    with pytest.raises(RuntimeError):
        await device.async_refresh_from_api()


async def test_async_refresh_from_api_ignores_mismatched_sn():
    device = BluettiDevice(
        device_id="SN1", on_line="0", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SOC", "fnName": "Battery", "fnValue": "10", "fnType": "SENSOR"}],
    )
    status_data = SimpleNamespace(sn="OTHER-SN", online="1", isBindByCurUser="1", stateList=[])
    device._api_client = AsyncMock()
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[status_data], is_ok=lambda: True)

    await device.async_refresh_from_api()

    # Nothing should have changed since the response was for a different device.
    assert device.on_line == "0"
    assert device.get_state("SOC").fn_value == "10"


async def test_set_state_value_applies_optimistic_update_and_notifies_coordinator():
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=0)
    device.coordinator = MagicMock()

    await device.set_state_value("SetCtrlAc", "1")

    assert device.get_state("SetCtrlAc").fn_value == "1"
    device.coordinator.async_set_updated_data.assert_called_once_with(device)


async def test_set_state_value_does_not_apply_on_server_error_code():
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=1)
    device.coordinator = MagicMock()

    await device.set_state_value("SetCtrlAc", "1")

    assert device.get_state("SetCtrlAc").fn_value == "0"


async def test_set_state_value_does_not_apply_on_non_json_response():
    """
    control_device() returns a plain str for a non-JSON server response.

    Regression test: accessing .msgCode on that str used to crash with an
    unhandled AttributeError instead of just not applying the update.
    """
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = "not json"
    device.coordinator = MagicMock()

    await device.set_state_value("SetCtrlAc", "1")  # must not raise

    assert device.get_state("SetCtrlAc").fn_value == "0"


async def test_set_state_value_wraps_api_errors():
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.side_effect = RuntimeError("boom")

    with pytest.raises(HomeAssistantError):
        await device.set_state_value("SetCtrlAc", "1")


async def test_set_state_value_unknown_fn_code_raises_value_error():
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")

    with pytest.raises(ValueError):
        await device.set_state_value("does-not-exist", "1")
