"""Tests for the per-device cloud health diagnostic entities."""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pybluetti import HttpStatusException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.binary_sensor import BluettiCloudApiBinarySensor
from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.models import BluettiData, BluettiDevice
from custom_components.bluetti.poll_history import PollOutcome
from custom_components.bluetti.sensor import (
    BluettiCloudLastResultSensor,
    BluettiCloudResponseTimeSensor,
    BluettiWebsocketLastMessageSensor,
)

ROOT = Path(__file__).parents[1]
STATE_LIST = [
    {"fnCode": "SOC", "fnName": "Battery", "fnValue": "80", "fnType": "SENSOR"},
    {"fnCode": "ACOutputPower", "fnName": "AC", "fnValue": "5", "fnType": "SENSOR"},
    {"fnCode": "onLine", "fnName": "Online", "fnValue": "1", "fnType": "SENSOR"},
]
HEALTH_ENTITIES = {
    "SN1_cloud_health_api": "binary_sensor",
    "SN1_cloud_health_response_time": "sensor",
    "SN1_cloud_health_last_result": "sensor",
    "SN1_cloud_health_websocket_last_message": "sensor",
}


def _answer(**values: str) -> MagicMock:
    state_list = [{"fnCode": code, "fnValue": value} for code, value in values.items()]
    return MagicMock(
        data=[MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=state_list)],
        is_ok=lambda: True,
    )


async def _set_up(hass, *, enable: bool) -> tuple[MockConfigEntry, BluettiDeviceCoordinator, AsyncMock]:
    """A loaded entry with one device; its health entities enabled if asked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": [{"sn": "SN1", "name": "Device", "stateList": STATE_LIST, "online": "1"}],
        },
        options={"devices": ["SN1"]},
    )
    entry.add_to_hass(hass)
    if enable:
        registry = er.async_get(hass)
        for unique_id, domain in HEALTH_ENTITIES.items():
            registry.async_get_or_create(domain, DOMAIN, unique_id, config_entry=entry)
    get_device_status = AsyncMock(return_value=_answer(SOC="80", ACOutputPower="5", onLine="1"))

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
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_device_status = get_device_status

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry, entry.runtime_data.coordinators["SN1"], get_device_status


def _entity_id(hass, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(HEALTH_ENTITIES[unique_id], DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


def _states(hass) -> dict[str, str]:
    return {
        unique_id.removeprefix("SN1_cloud_health_"): hass.states.get(_entity_id(hass, unique_id)).state
        for unique_id in HEALTH_ENTITIES
    }


async def test_each_device_gets_four_disabled_diagnostic_entities_on_its_own_device(hass, enable_custom_integrations):
    await _set_up(hass, enable=False)
    entity_registry = er.async_get(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "SN1")})
    assert device is not None

    for unique_id, domain in HEALTH_ENTITIES.items():
        entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
        assert entity_id is not None, unique_id
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC
        assert registry_entry.device_id == device.id
        # Disabled: never written to the state machine, so never recorded.
        assert hass.states.get(entity_id) is None


def test_the_unique_ids_cannot_collide_with_a_cloud_fn_code():
    fn_codes = {
        state["fn_code"]
        for path in (ROOT / "doc" / "diagnostics").glob("*.json")
        for state in json.loads(path.read_text())["states"]
    }
    assert fn_codes
    cloud_unique_ids = {f"SN1_{fn_code}" for fn_code in fn_codes}
    cloud_unique_ids |= {f"{unique_id}_energy" for unique_id in cloud_unique_ids}

    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    device.coordinator = MagicMock()
    unique_ids = {
        entity.unique_id
        for entity in (
            BluettiCloudApiBinarySensor(device),
            BluettiCloudResponseTimeSensor(device),
            BluettiCloudLastResultSensor(device),
            BluettiWebsocketLastMessageSensor(device),
        )
    }
    assert unique_ids == set(HEALTH_ENTITIES)
    assert not unique_ids & cloud_unique_ids


async def test_the_states_follow_each_poll(hass, enable_custom_integrations):
    _, coordinator, get_device_status = await _set_up(hass, enable=True)

    states = _states(hass)
    # Milliseconds, a whole number.
    assert states.pop("response_time").isdigit()
    assert states == {
        "api": STATE_ON,
        "last_result": "ok",
        "websocket_last_message": STATE_UNKNOWN,
    }
    last_result = hass.states.get(_entity_id(hass, "SN1_cloud_health_last_result"))
    assert last_result.attributes["attempts"] == 1
    assert last_result.attributes["options"] == [outcome.value for outcome in PollOutcome]

    get_device_status.side_effect = HttpStatusException(500, "Internal Server Error")
    await coordinator.async_refresh()
    last_result = hass.states.get(_entity_id(hass, "SN1_cloud_health_last_result"))
    assert last_result.state == "http_error"
    assert last_result.attributes["http_status"] == 500
    assert last_result.attributes["msg_code"] is None
    assert hass.states.get(_entity_id(hass, "SN1_cloud_health_api")).state == STATE_OFF


async def test_they_stay_available_once_the_ride_out_is_exhausted(hass, enable_custom_integrations):
    _, coordinator, get_device_status = await _set_up(hass, enable=True)
    online = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, "SN1_onLine")

    get_device_status.side_effect = TimeoutError()
    for _ in range(3):
        await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    # Home Assistant does not call the coordinator's listeners for the
    # third failure in a row; the poll listener still came through.
    assert len(coordinator.poll_history()) == 4

    assert hass.states.get(online).state == STATE_UNAVAILABLE
    assert _states(hass) == {
        "api": STATE_OFF,
        # The client's limit, not the cloud's answer time.
        "response_time": STATE_UNKNOWN,
        "last_result": "timeout",
        "websocket_last_message": STATE_UNKNOWN,
    }
    last_result = hass.states.get(_entity_id(hass, "SN1_cloud_health_last_result"))
    assert last_result.attributes["attempts"] == 2


async def test_they_stay_available_while_the_device_is_offline(hass, enable_custom_integrations):
    _, coordinator, get_device_status = await _set_up(hass, enable=True)
    online = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, "SN1_onLine")

    # Online, with every reading at 0: the device counts as offline.
    get_device_status.return_value = _answer(SOC="0", ACOutputPower="0", onLine="0")
    await coordinator.async_refresh()

    assert coordinator.device.online is False
    assert hass.states.get(online).state == STATE_UNAVAILABLE
    states = _states(hass)
    assert states["api"] == STATE_OFF
    assert states["last_result"] == "no_readings"
    assert states["response_time"].isdigit()


async def test_unloading_removes_the_poll_listeners(hass, enable_custom_integrations):
    entry, coordinator, _ = await _set_up(hass, enable=True)
    assert len(coordinator._poll_listeners) == 4

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert coordinator._poll_listeners == []


async def test_they_are_unavailable_before_the_first_poll(hass):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    BluettiDeviceCoordinator(hass, entry, device)

    binary_sensor = BluettiCloudApiBinarySensor(device)
    response_time = BluettiCloudResponseTimeSensor(device)
    last_result = BluettiCloudLastResultSensor(device)
    websocket = BluettiWebsocketLastMessageSensor(device)

    assert not any(e.available for e in (binary_sensor, response_time, last_result, websocket))
    assert binary_sensor.is_on is None
    assert response_time.native_value is None
    assert last_result.native_value is None
    assert last_result.extra_state_attributes is None
    assert websocket.native_value is None


async def test_the_websocket_timestamp_is_wall_clock_time(hass, freezer):
    message_at = datetime(2026, 11, 3, 2, 20, 5, tzinfo=UTC)
    freezer.move_to(message_at)
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L")
    device.coordinator = MagicMock()
    data = BluettiData.__new__(BluettiData)
    data.devices = [device]
    data.loop = asyncio.get_running_loop()
    clock = MagicMock(wraps=time)
    # A monotonic clock reads nothing like the time of day.
    clock.monotonic.return_value = 4242.5

    with patch("custom_components.bluetti.models.time", clock), \
         patch("custom_components.bluetti.models.asyncio.run_coroutine_threadsafe"):
        data.web_socket_message_handler(json.dumps({"data": {"message": {
            "deviceSn": "SN1",
            "messageType": "DEVICE_REALTIME_STATUS",
            "payload": {"allFieldIsNull": False},
        }}}))

    assert device.last_alive == 4242.5
    assert BluettiWebsocketLastMessageSensor(device).native_value == message_at


def test_every_outcome_has_a_translated_state():
    strings = json.loads((ROOT / "custom_components" / "bluetti" / "strings.json").read_text())
    states = strings["entity"]["sensor"]["cloud_health_last_result"]["state"]
    assert list(states) == [outcome.value for outcome in PollOutcome]

    icons = json.loads((ROOT / "custom_components" / "bluetti" / "icons.json").read_text())["entity"]
    for unique_id, domain in HEALTH_ENTITIES.items():
        key = unique_id.removeprefix("SN1_")
        assert key in strings["entity"][domain]
        assert key in icons[domain]
