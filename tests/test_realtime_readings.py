"""Tests for taking a realtime push's readings without a REST round trip."""
import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.models import (
    REALTIME_TIMESTAMP_TZ,
    BluettiData,
    BluettiDevice,
    _realtime_timestamp,
)


def _stamp(offset: float = 0) -> str:
    """A push timestamp as the cloud writes it: UTC+8, no zone, to the second."""
    when = dt_util.utcnow() + timedelta(seconds=offset)
    return when.astimezone(REALTIME_TIMESTAMP_TZ).strftime("%Y-%m-%d %H:%M:%S")


# The two payload shapes a PR30V2 pushes, alternating (trimmed: every key not
# shown was null). The first carries readings deviceStates also has; the
# second only battery pack data that deviceStates never has.
def _readings_push(**changes: object) -> dict[str, object]:
    return {
        "allFieldIsNull": False,
        "timestamp": _stamp(),
        "powerPvIn": "0",
        "powerGridIn": "16",
        "powerAcOut": "16",
        "powerDcOut": "0",
        "batterySoc": "80",
        "acSwitch": "1",
        "dcSwitch": None,
        "chgFullTime": "1326",
        "powerInvTotal": "18",
        **changes,
    }


def _pack_push() -> dict[str, object]:
    return {
        "allFieldIsNull": False,
        "timestamp": _stamp(),
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


async def test_a_current_push_updates_the_entities_without_a_rest_call(hass):
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    with patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe") as mock_run:
        data.web_socket_message_handler(_push(_readings_push()))
    mock_run.assert_not_called()
    assert _value(device, "GridAllTotalPower") == "16"
    assert _value(device, "ACLoadAllTotalPower") == "16"
    assert _value(device, "SetCtrlAc") == "1"
    device.coordinator.async_update_listeners.assert_called_once()
    # async_set_updated_data would push the next poll back on every push.
    device.coordinator.async_set_updated_data.assert_not_called()


async def test_the_battery_level_is_never_taken_from_a_push(hass):
    # batterySoc often trails the deviceStates SOC by a poll, and a late push
    # took the level back a step on a Balco 260: the poll is its only source.
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push(batterySoc="27")))
    assert _value(device, "SOC") == "79"
    assert _value(device, "GridAllTotalPower") == "16"


async def test_a_null_or_unmapped_key_leaves_the_state_alone(hass):
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push()))
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
        data.web_socket_message_handler(_push(_pack_push()))
    mock_run.assert_not_called()
    assert _value(device, "GridAllTotalPower") == "15"
    # Still a sign of life, so the entities hear of it.
    assert device.last_alive is not None
    device.coordinator.async_update_listeners.assert_called_once()


@pytest.mark.parametrize("soc", ["80", "0", None])
async def test_a_push_with_every_power_at_zero_is_left_to_the_poll(hass, soc):
    # The #73 case (readings falling to 0 around a reconnection) and an idle
    # unit look the same in a push, whatever its batterySoc says: the push
    # is kept out whole, and the next poll, at most 30 s later, decides.
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    zeros = _readings_push(powerPvIn="0", powerGridIn="0", powerAcOut="0", powerDcOut="0", batterySoc=soc)
    data.web_socket_message_handler(_push(zeros))
    assert _value(device, "GridAllTotalPower") == "15"
    assert _value(device, "ACLoadAllTotalPower") == "15"
    assert _value(device, "SetCtrlAc") == "0"
    device.coordinator.async_update_listeners.assert_called_once()


async def test_a_state_the_device_does_not_have_is_skipped(hass):
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco 260",
        state_list=[_state("GridAllTotalPower", "SENSOR", "15")],
    )
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push()))
    assert _value(device, "GridAllTotalPower") == "16"
    assert device.get_state("DCLoadAllTotalPower") is None


async def test_a_push_does_not_reschedule_the_next_poll(hass):
    device = _make_device()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    heard: list[None] = []
    unsubscribe = coordinator.async_add_listener(lambda: heard.append(None))
    scheduled = coordinator._unsub_refresh
    assert scheduled is not None
    _data_for(device).web_socket_message_handler(_push(_readings_push()))
    assert heard == [None]
    assert coordinator._unsub_refresh is scheduled
    unsubscribe()


async def test_a_message_for_an_unknown_device_is_ignored(hass):
    device = _make_device()
    device.coordinator = MagicMock()
    data = _data_for(device)
    message = _push(_readings_push()).replace('"SN1"', '"OTHER"')
    with patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe") as mock_run:
        data.web_socket_message_handler(message)
    mock_run.assert_not_called()
    assert _value(device, "GridAllTotalPower") == "15"


async def test_a_push_with_only_a_switch_is_applied(hass):
    # No reading at all, so nothing to judge as empty: the switch is taken.
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push({"allFieldIsNull": False, "timestamp": _stamp(), "acSwitch": "1"}))
    assert _value(device, "SetCtrlAc") == "1"


# --- Late pushes -------------------------------------------------------------
# Seen on a Balco 260 (2026-11-14): pushes arriving 5 to 20 s after their own
# timestamp, after a poll that already showed what came next.


async def test_a_push_stamped_before_the_last_poll_is_ignored(hass, caplog):
    device = _make_device()
    device.coordinator = MagicMock()
    device._last_poll_at = dt_util.utcnow()
    data = _data_for(device)
    late = _readings_push(timestamp=_stamp(-10), powerGridIn="99", acSwitch="1")
    with caplog.at_level(logging.DEBUG, logger="custom_components.bluetti.models"):
        data.web_socket_message_handler(_push(late))
    assert _value(device, "GridAllTotalPower") == "15"
    assert _value(device, "SetCtrlAc") == "0"
    assert "before the last poll" in caplog.text
    # A late push is still a sign of life.
    assert device.last_alive is not None
    device.coordinator.async_update_listeners.assert_called_once()


async def test_a_push_stamped_after_the_last_poll_is_taken(hass):
    device = _make_device()
    device._last_poll_at = dt_util.utcnow() - timedelta(seconds=10)
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push(powerGridIn="99")))
    assert _value(device, "GridAllTotalPower") == "99"


@pytest.mark.parametrize("timestamp", ["missing", None, 1763127521, "", "2026-11-14T21:48:41", "21:48:41"])
async def test_a_push_without_a_usable_timestamp_is_not_trusted(hass, caplog, timestamp):
    device = _make_device()
    data = _data_for(device)
    payload = _readings_push(powerGridIn="99")
    if timestamp == "missing":
        del payload["timestamp"]
    else:
        payload["timestamp"] = timestamp
    with caplog.at_level(logging.DEBUG, logger="custom_components.bluetti.models"):
        data.web_socket_message_handler(_push(payload))
    assert _value(device, "GridAllTotalPower") == "15"
    assert "without a usable timestamp" in caplog.text


@pytest.mark.parametrize(("offset", "taken"), [(5, True), (30, False), (3600, False)])
async def test_a_push_stamped_ahead_of_this_clock_is_only_taken_within_the_skew(hass, caplog, offset, taken):
    # A second or two of clock difference is normal; a push stamped further
    # ahead means UTC+8 is wrong for this cloud, or this clock is behind.
    device = _make_device()
    data = _data_for(device)
    with caplog.at_level(logging.DEBUG, logger="custom_components.bluetti.models"):
        data.web_socket_message_handler(_push(_readings_push(timestamp=_stamp(offset), powerGridIn="99")))
    assert _value(device, "GridAllTotalPower") == ("99" if taken else "15")
    assert ("ahead of this clock" in caplog.text) is not taken


async def test_a_push_stamped_in_the_same_second_as_the_last_poll_is_left_to_it(hass):
    # The timestamp is to the second, so a tie cannot say which came first:
    # the poll, whose answer is known to be complete, wins.
    device = _make_device()
    second = dt_util.utcnow().replace(microsecond=0)
    device._last_poll_at = second
    data = _data_for(device)
    stamp = second.astimezone(REALTIME_TIMESTAMP_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data.web_socket_message_handler(_push(_readings_push(timestamp=stamp, powerGridIn="99")))
    assert _value(device, "GridAllTotalPower") == "15"


async def test_a_push_stamped_in_the_same_second_as_the_last_push_taken_is_ignored(hass):
    device = _make_device()
    data = _data_for(device)
    stamp = _stamp()
    data.web_socket_message_handler(_push(_readings_push(timestamp=stamp, powerGridIn="30")))
    data.web_socket_message_handler(_push(_readings_push(timestamp=stamp, powerGridIn="20")))
    assert _value(device, "GridAllTotalPower") == "30"


async def test_pushes_arriving_out_of_order_cannot_step_a_value_back(hass, caplog):
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push(powerGridIn="30")))
    assert _value(device, "GridAllTotalPower") == "30"
    older = _readings_push(timestamp=_stamp(-5), powerGridIn="20")
    with caplog.at_level(logging.DEBUG, logger="custom_components.bluetti.models"):
        data.web_socket_message_handler(_push(older))
    assert _value(device, "GridAllTotalPower") == "30"
    assert "not after the last push taken" in caplog.text


async def test_a_newer_push_after_a_taken_one_is_taken(hass):
    device = _make_device()
    data = _data_for(device)
    data.web_socket_message_handler(_push(_readings_push(timestamp=_stamp(-5), powerGridIn="20")))
    data.web_socket_message_handler(_push(_readings_push(powerGridIn="30")))
    assert _value(device, "GridAllTotalPower") == "30"


async def test_a_push_kept_out_does_not_count_as_taken(hass):
    # An all-zero push reaches no state, so a later push stamped before it
    # but after the last poll is still the newest reading shown.
    device = _make_device()
    data = _data_for(device)
    zeros = _readings_push(powerPvIn="0", powerGridIn="0", powerAcOut="0", powerDcOut="0")
    data.web_socket_message_handler(_push(zeros))
    assert device._last_push_at is None
    data.web_socket_message_handler(_push(_readings_push(timestamp=_stamp(-5), powerGridIn="20")))
    assert _value(device, "GridAllTotalPower") == "20"


def test_the_timestamp_is_read_as_utc_plus_8():
    # Measured on a PR30V2 (gwde) and a Balco 260 (EU account): 8 h ahead of UTC.
    assert _realtime_timestamp({"timestamp": "2026-11-14 21:48:41"}) == datetime(2026, 11, 14, 13, 48, 41, tzinfo=UTC)


async def test_a_poll_that_reaches_the_states_marks_the_time():
    device = _make_device()
    device._api_client = AsyncMock()
    status = SimpleNamespace(
        sn="SN1", online="1", isBindByCurUser="1",
        stateList=[{"fnCode": "SOC", "fnValue": "80"}, {"fnCode": "GridAllTotalPower", "fnValue": "20"}],
    )
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[status], is_ok=lambda: True)
    before = dt_util.utcnow()
    await device.async_refresh_from_api()
    assert device._last_poll_at is not None
    assert device._last_poll_at >= before


async def test_a_poll_with_no_readings_does_not_mark_the_time():
    # The all-zero snapshot is kept out of the states, so it is not the poll
    # a push is compared with.
    device = _make_device()
    device._api_client = AsyncMock()
    status = SimpleNamespace(
        sn="SN1", online="1", isBindByCurUser="1",
        stateList=[{"fnCode": "SOC", "fnValue": "0"}, {"fnCode": "GridAllTotalPower", "fnValue": "0"}],
    )
    device._api_client.get_device_status.return_value = SimpleNamespace(data=[status], is_ok=lambda: True)
    await device.async_refresh_from_api()
    assert device._last_poll_at is None
