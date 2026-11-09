"""Tests for taking a realtime push's readings without a REST round trip."""
import asyncio
import json
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.models import BluettiData, BluettiDevice

# The two payload shapes a PR30V2 pushes, alternating (2026-11-06, trimmed:
# every key not shown was null). The first carries the readings deviceStates
# also has; the second only battery pack data that deviceStates never has.
READINGS_PUSH = {
    "allFieldIsNull": False,
    "powerPvIn": "0",
    "powerGridIn": "16",
    "powerAcOut": "16",
    "powerDcOut": "0",
    "batterySoc": "80",
    "acSwitch": "1",
    "dcSwitch": None,
    "chgFullTime": "1326",
    "powerInvTotal": "18",
}
PACK_PUSH = {
    "allFieldIsNull": False,
    "batteryVoltage": "165.8",
    "batterySoh": "95",
    "packTotalChgEnergy": "1099.5",
    "packTotalDsgEnergy": "1149.1",
    "batterySoc": None,
}


def _state(fn_code: str, fn_type: str, value: str) -> dict[str, str]:
    return {"fnCode": fn_code, "fnName": fn_code, "fnType": fn_type, "fnValue": value}


def _make_device() -> BluettiDevice:
    return BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="PR30V2",
        state_list=[
            _state("SOC", "SENSOR", "79"),
            _state("GridAllTotalPower", "SENSOR", "15"),
            _state("ACLoadAllTotalPower", "SENSOR", "15"),
            _state("DCLoadAllTotalPower", "SENSOR", "0"),
            _state("PVAllTotalPower", "SENSOR", "0"),
            _state("DsgFullTime", "SENSOR", "1320"),
            _state("ChgFullTime", "SENSOR", "0"),
            _state("SetCtrlAc", "SWITCH", "0"),
            _state("SetCtrlDc", "SWITCH", "1"),
        ],
    )


def _push(payload: dict[str, object]) -> str:
    return json.dumps({"data": {"message": {
        "messageType": "DEVICE_REALTIME_STATUS",
        "deviceSn": "SN1",
        "type": "PR30V2",
        "payload": payload,
    }}})


def _data_for(device: BluettiDevice) -> BluettiData:
    data = BluettiData.__new__(BluettiData)
    data.devices = [device]
    data.loop = asyncio.get_running_loop()
    return data


def _value(device: BluettiDevice, fn_code: str) -> str:
    state = device.get_state(fn_code)
    assert state is not None
    return state.fn_value


async def test_a_push_with_readings_updates_the_entities_without_a_rest_call(hass):
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    with patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe") as mock_run:
        data.web_socket_message_handler(_push(READINGS_PUSH))
    mock_run.assert_not_called()
    assert _value(device, "SOC") == "80"
    assert _value(device, "GridAllTotalPower") == "16"
    assert _value(device, "ACLoadAllTotalPower") == "16"
    assert _value(device, "SetCtrlAc") == "1"
    device.coordinator.async_update_listeners.assert_called_once()
    # async_set_updated_data would push the next poll back on every push.
    device.coordinator.async_set_updated_data.assert_not_called()


async def test_a_null_or_unmapped_key_leaves_the_state_alone(hass):
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push(READINGS_PUSH))
    # dcSwitch is null in the push: not "off".
    assert _value(device, "SetCtrlDc") == "1"
    # chgFullTime is not mapped: neither runtime value moves.
    assert _value(device, "DsgFullTime") == "1320"
    assert _value(device, "ChgFullTime") == "0"


async def test_a_push_without_mapped_readings_changes_nothing_and_asks_nothing(hass):
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    with patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe") as mock_run:
        data.web_socket_message_handler(_push(PACK_PUSH))
    mock_run.assert_not_called()
    assert _value(device, "SOC") == "79"
    # Still a sign of life, so the entities hear of it.
    assert device.last_alive is not None
    device.coordinator.async_update_listeners.assert_called_once()


async def test_a_push_with_every_reading_at_zero_is_kept_out(hass):
    device = _make_device()
    data = _data_for(device)
    zeros = {**READINGS_PUSH, "batterySoc": "0", "powerGridIn": "0", "powerAcOut": "0"}
    data.web_socket_message_handler(_push(zeros))
    assert _value(device, "SOC") == "79"
    assert _value(device, "SetCtrlAc") == "0"


async def test_a_state_the_device_does_not_have_is_skipped(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="PR30V2",
        state_list=[_state("SOC", "SENSOR", "79")],
    )
    data = _data_for(device)
    data.web_socket_message_handler(_push(READINGS_PUSH))
    assert _value(device, "SOC") == "80"
    assert device.get_state("SetCtrlAc") is None


async def test_a_push_does_not_reschedule_the_next_poll(hass):
    device = _make_device()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    heard: list[None] = []
    unsubscribe = coordinator.async_add_listener(lambda: heard.append(None))
    scheduled = coordinator._unsub_refresh
    assert scheduled is not None
    _data_for(device).web_socket_message_handler(_push(READINGS_PUSH))
    assert heard == [None]
    assert coordinator._unsub_refresh is scheduled
    unsubscribe()


async def test_a_message_for_an_unknown_device_is_ignored(hass):
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    message = _push(READINGS_PUSH).replace('"SN1"', '"OTHER"')
    with patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe") as mock_run:
        data.web_socket_message_handler(message)
    mock_run.assert_not_called()
    assert _value(device, "SOC") == "79"


async def test_a_push_with_every_power_at_zero_and_no_battery_level_is_kept_out(hass):
    # _is_empty_snapshot needs SOC, and a push often has no batterySoc: this
    # is the #73 case (readings falling to 0 around a reconnection) seen
    # through a push. Kept out whole; a real 0 comes back with the next poll.
    device = _make_device()
    data = _data_for(device)
    zeros_no_soc = {
        "allFieldIsNull": False,
        "powerPvIn": "0", "powerGridIn": "0", "powerAcOut": "0", "powerDcOut": "0",
        "acSwitch": "1",
    }
    data.web_socket_message_handler(_push(zeros_no_soc))
    assert _value(device, "GridAllTotalPower") == "15"
    assert _value(device, "ACLoadAllTotalPower") == "15"
    assert _value(device, "SetCtrlAc") == "0"


async def test_powers_at_zero_with_a_real_battery_level_are_a_real_reading(hass):
    # An idle unit: nothing in, nothing out, the battery at 80 %.
    device = _make_device()
    data = _data_for(device)
    idle = {**READINGS_PUSH, "powerGridIn": "0", "powerAcOut": "0"}
    data.web_socket_message_handler(_push(idle))
    assert _value(device, "GridAllTotalPower") == "0"
    assert _value(device, "ACLoadAllTotalPower") == "0"
    assert _value(device, "SOC") == "80"


async def test_a_push_with_only_a_switch_is_applied(hass):
    # No reading at all, so nothing to judge as empty: the switch is taken.
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push({"allFieldIsNull": False, "acSwitch": "1"}))
    assert _value(device, "SetCtrlAc") == "1"
