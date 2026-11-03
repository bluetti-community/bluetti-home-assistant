"""Tests for diagnostics.py."""

import contextlib
from unittest.mock import AsyncMock, MagicMock

from homeassistant.helpers.update_coordinator import UpdateFailed
from pybluetti import ApplicationRuntimeException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti import BluettiRuntimeData
from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.diagnostics import (
    RECENT_POLLS,
    async_get_config_entry_diagnostics,
)
from custom_components.bluetti.models import BluettiDevice


async def test_diagnostics_redacts_sensitive_data_and_lists_devices(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "super-secret", "refresh_token": "also-secret"},
            "products": [{"sn": "SN1", "name": "Device"}],
        },
        options={"devices": ["SN1"]},
    )
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "80", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            # No sensorInfo at all - some SENSOR-type states never carry one.
            {"fnCode": "Weird", "fnName": "Weird", "fnValue": "1", "fnType": "SENSOR"},
        ],
    )
    coordinator = MagicMock(last_update_success=True, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry_data"]["token"] == "**REDACTED**"  # noqa: S105 - redaction placeholder, not a secret
    assert diagnostics["entry_data"]["products"] == "**REDACTED**"
    assert diagnostics["entry_options"] == {"devices": ["device_1"]}

    # The real serial number (device_id) must not appear anywhere in the
    # dump - it's aliased to a stable "device_N" instead.
    assert diagnostics["devices"] == [{
        "device_id": "device_1",
        "model": "AC200L",
        "online": True,
        "states": [
            {
                "fn_code": "SOC", "fn_type": "SENSOR", "fn_value": "80",
                "sensor_info": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            {"fn_code": "Weird", "fn_type": "SENSOR", "fn_value": "1", "sensor_info": None},
        ],
    }]

    assert diagnostics["coordinators"]["device_1"]["last_update_success"] is True
    assert "SN1" not in diagnostics["coordinators"]


async def test_diagnostics_aliases_are_stable_and_correlate_across_multiple_devices(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {}, "products": []},
        options={"devices": ["SN1", "SN2"]},
    )
    entry.add_to_hass(hass)

    device1 = BluettiDevice(device_id="SN1", on_line="1", name="First", sn="SN1", model="AC200L")
    device2 = BluettiDevice(device_id="SN2", on_line="0", name="Second", sn="SN2", model="EL400")
    coordinator1 = MagicMock(last_update_success=True, update_interval="0:00:30")
    coordinator2 = MagicMock(last_update_success=False, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device1, device2]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator1, "SN2": coordinator2},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Two distinct devices must get two distinct, stable aliases - not both
    # collapsed to the same placeholder - so each device's states can still
    # be matched to its own coordinator entry in the same dump.
    device_ids = [d["device_id"] for d in diagnostics["devices"]]
    assert device_ids == ["device_1", "device_2"]
    assert set(diagnostics["coordinators"].keys()) == {"device_1", "device_2"}
    assert diagnostics["coordinators"]["device_1"]["last_update_success"] is True
    assert diagnostics["coordinators"]["device_2"]["last_update_success"] is False
    assert "SN1" not in str(diagnostics)
    assert "SN2" not in str(diagnostics)


async def test_diagnostics_show_each_poll_and_the_failure_windows(hass, freezer):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {}, "products": []},
        options={"devices": ["SN1"]},
    )
    entry.add_to_hass(hass)
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    coordinator.data = device
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    polls = diagnostics["coordinators"]["device_1"]
    assert polls["history_since"] is None
    assert polls["last_poll"] is None
    assert polls["recent_polls"] == []
    assert polls["failure_windows"] == []

    freezer.move_to("2026-11-03T15:04:00+00:00")
    device.async_refresh_from_api = AsyncMock()
    await coordinator._async_update_data()
    freezer.move_to("2026-11-03T15:05:00+00:00")
    # The message names the serial, as the real one does; nothing of it may
    # reach the dump.
    device.async_refresh_from_api = AsyncMock(side_effect=ApplicationRuntimeException(
        msgCode=500, errMessage="no status for SN1"
    ))
    await coordinator._async_update_data()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    polls = diagnostics["coordinators"]["device_1"]
    assert polls["history_since"] == "2026-11-03T15:04:00+00:00"
    assert polls["last_poll"] == {
        "started": "2026-11-03T15:05:00+00:00",
        "duration_ms": 0,
        "outcome": "api_error",
        "attempts": 1,
        "msg_code": 500,
        "http_status": None,
    }
    assert [p["outcome"] for p in polls["recent_polls"]] == ["ok", "api_error"]
    assert polls["failure_windows"] == [{
        "start": "2026-11-03T15:05:00+00:00",
        "end": "2026-11-03T15:05:00+00:00",
        "count": 1,
        "outcomes": ["api_error"],
        "ongoing": True,
    }]
    assert "SN1" not in str(diagnostics)


async def test_diagnostics_list_only_the_most_recent_polls(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"auth_implementation": DOMAIN})
    entry.add_to_hass(hass)
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    device.async_refresh_from_api = AsyncMock(side_effect=TimeoutError())
    for _ in range(RECENT_POLLS + 5):
        with contextlib.suppress(UpdateFailed):
            await coordinator._async_update_data()
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    polls = (await async_get_config_entry_diagnostics(hass, entry))["coordinators"]["device_1"]

    assert len(polls["recent_polls"]) == RECENT_POLLS
    # The windows still cover the whole history.
    assert polls["failure_windows"][0]["count"] == RECENT_POLLS + 5
