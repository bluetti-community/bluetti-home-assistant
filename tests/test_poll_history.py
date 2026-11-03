"""Tests for the cloud poll history: what each poll got, before any ride-out."""

import asyncio
import contextlib
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pybluetti import ApplicationRuntimeException, HttpStatusException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.coordinator import BluettiDeviceCoordinator
from custom_components.bluetti.models import BluettiData, BluettiDevice
from custom_components.bluetti.poll_history import (
    POLL_HISTORY_SIZE,
    PollHistory,
    PollOutcome,
    PollRecord,
    failure_windows,
)

T0 = datetime(2026, 11, 3, 15, 4, tzinfo=UTC)


def _coordinator(hass, device: BluettiDevice | None = None) -> BluettiDeviceCoordinator:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return BluettiDeviceCoordinator(
        hass, entry, device or BluettiDevice(
            device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
            state_list=[
                {"fnCode": "SOC", "fnName": "Battery", "fnValue": "80", "fnType": "SENSOR"},
                {"fnCode": "ACOutputPower", "fnName": "AC", "fnValue": "5", "fnType": "SENSOR"},
            ],
        ),
    )


def _status(sn: str = "SN1", bound: str = "1", **values: str) -> SimpleNamespace:
    status_data = SimpleNamespace(
        sn=sn, online="1", isBindByCurUser=bound,
        stateList=[{"fnCode": code, "fnValue": value} for code, value in values.items()],
    )
    return SimpleNamespace(data=[status_data], is_ok=lambda: True, msgCode=0)


async def _poll(coordinator: BluettiDeviceCoordinator) -> PollRecord:
    """Run one poll, failed or not, and return what it recorded."""
    with contextlib.suppress(UpdateFailed, ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    record = coordinator.last_poll
    assert record is not None
    return record


@pytest.mark.parametrize(
    ("error", "outcome", "msg_code", "http_status"),
    [
        # HttpStatusException is an ApplicationRuntimeException: a 504 from
        # the gateway is an HTTP error, not an API msgCode 504.
        (HttpStatusException(504, "Gateway Time-out"), PollOutcome.HTTP_ERROR, None, 504),
        (HttpStatusException(401, "Unauthorized"), PollOutcome.HTTP_ERROR, None, 401),
        (ApplicationRuntimeException(msgCode=805), PollOutcome.AUTH_REJECTED, 805, None),
        (ApplicationRuntimeException(msgCode=401), PollOutcome.AUTH_REJECTED, 401, None),
        (ApplicationRuntimeException(msgCode=500), PollOutcome.API_ERROR, 500, None),
        (TimeoutError(), PollOutcome.TIMEOUT, None, None),
        # A ClientError and a TimeoutError at once: still a timeout.
        (aiohttp.ServerTimeoutError(), PollOutcome.TIMEOUT, None, None),
        # A ClientConnectorError subclass: the DNS one wins.
        (
            aiohttp.ClientConnectorDNSError(MagicMock(), OSError(-2, "Name or service not known")),
            PollOutcome.DNS_ERROR, None, None,
        ),
        (
            aiohttp.ClientConnectorError(MagicMock(), OSError(111, "Connection refused")),
            PollOutcome.CONNECT_ERROR, None, None,
        ),
        (aiohttp.ServerDisconnectedError(), PollOutcome.NETWORK_ERROR, None, None),
        (aiohttp.ClientPayloadError(), PollOutcome.NETWORK_ERROR, None, None),
        (RuntimeError("boom"), PollOutcome.ERROR, None, None),
    ],
)
async def test_each_failure_is_recorded_with_its_outcome(
    hass, error, outcome, msg_code, http_status
):
    coordinator = _coordinator(hass)
    coordinator.device.async_refresh_from_api = AsyncMock(side_effect=error)

    record = await _poll(coordinator)

    assert (record.outcome, record.msg_code, record.http_status) == (outcome, msg_code, http_status)


async def test_a_good_answer_is_recorded_as_ok(hass):
    coordinator = _coordinator(hass)
    coordinator.device._api_client = AsyncMock()
    coordinator.device._api_client.get_device_status.return_value = _status(SOC="80", ACOutputPower="5")

    record = await _poll(coordinator)

    assert record.outcome is PollOutcome.OK
    assert record.attempts == 1


async def test_online_with_every_reading_at_zero_is_recorded_as_no_readings(hass):
    # The overnight pattern: the poll goes through, but carries nothing.
    coordinator = _coordinator(hass)
    coordinator.device._api_client = AsyncMock()
    coordinator.device._api_client.get_device_status.return_value = _status(SOC="0", ACOutputPower="0")

    assert (await _poll(coordinator)).outcome is PollOutcome.NO_READINGS


async def test_an_answer_without_data_is_recorded_as_empty(hass):
    coordinator = _coordinator(hass)
    coordinator.device._api_client = AsyncMock()
    coordinator.device._api_client.get_device_status.return_value = SimpleNamespace(
        data=[], is_ok=lambda: True, msgCode=0
    )

    assert (await _poll(coordinator)).outcome is PollOutcome.EMPTY_RESPONSE


async def test_an_answer_for_another_device_is_recorded_as_empty(hass):
    # Nothing for this device came back - after a poll that had no readings,
    # so a left-over flag cannot be what decides it.
    coordinator = _coordinator(hass)
    coordinator.device._api_client = AsyncMock()
    coordinator.device._api_client.get_device_status.return_value = _status(SOC="0", ACOutputPower="0")
    await _poll(coordinator)

    coordinator.device._api_client.get_device_status.return_value = _status(sn="OTHER")

    assert (await _poll(coordinator)).outcome is PollOutcome.EMPTY_RESPONSE


async def test_an_answer_that_the_device_was_unbound_is_recorded_as_ok(hass):
    # The cloud answered, and correctly: it is no cloud failure.
    coordinator = _coordinator(hass)
    coordinator.device._api_client = AsyncMock()
    coordinator.device._api_client.get_device_status.return_value = _status(bound="0")

    assert (await _poll(coordinator)).outcome is PollOutcome.OK


async def test_a_ridden_out_failure_is_still_recorded_as_a_failure(hass):
    coordinator = _coordinator(hass)
    coordinator.data = coordinator.device
    coordinator.device.async_refresh_from_api = AsyncMock(side_effect=TimeoutError())

    # The previous data comes back, as before...
    assert await coordinator._async_update_data() is coordinator.device
    # ...but the history says what happened.
    assert coordinator.last_poll.outcome is PollOutcome.TIMEOUT


async def test_the_attempts_count_the_one_retry(hass):
    coordinator = _coordinator(hass)
    coordinator.device.async_refresh_from_api = AsyncMock(
        side_effect=[HttpStatusException(504, "Gateway Time-out"), None]
    )
    assert (await _poll(coordinator)).attempts == 2
    assert coordinator.last_poll.outcome is PollOutcome.OK

    coordinator.device.async_refresh_from_api = AsyncMock(side_effect=TimeoutError())
    assert (await _poll(coordinator)).attempts == 2

    # Not retried at all: one attempt.
    coordinator.device.async_refresh_from_api = AsyncMock(side_effect=RuntimeError("boom"))
    assert (await _poll(coordinator)).attempts == 1


async def test_a_record_carries_its_start_in_utc_and_its_duration(hass, freezer):
    freezer.move_to(T0)
    coordinator = _coordinator(hass)
    coordinator.device.async_refresh_from_api = AsyncMock()
    clock = MagicMock(wraps=time)
    clock.monotonic.side_effect = [100.0, 100.2504]

    with patch("custom_components.bluetti.coordinator.time", clock):
        record = await _poll(coordinator)

    assert record.started == T0
    assert record.started.tzinfo is not None
    assert record.duration_ms == 250


async def test_a_refresh_asked_for_by_the_websocket_is_recorded(hass):
    coordinator = _coordinator(hass)
    coordinator.device.async_refresh_from_api = AsyncMock()
    data = BluettiData.__new__(BluettiData)
    data.devices = [coordinator.device]
    data.loop = asyncio.get_running_loop()

    # On the websocket's own thread, as pybluetti calls it.
    await hass.async_add_executor_job(
        data.web_socket_message_handler, '{"data": {"message": {"deviceSn": "SN1"}}}'
    )
    await hass.async_block_till_done()

    assert len(coordinator.poll_history()) == 1
    coordinator.device.async_refresh_from_api.assert_awaited_once()


async def test_the_history_is_bounded_and_keeps_the_newest(hass):
    coordinator = _coordinator(hass)
    coordinator._poll_history = PollHistory(size=3)
    coordinator.device.async_refresh_from_api = AsyncMock()
    for _ in range(4):
        await _poll(coordinator)
    coordinator.device.async_refresh_from_api = AsyncMock(side_effect=RuntimeError("boom"))
    await _poll(coordinator)

    history = coordinator.poll_history()
    assert len(history) == 3
    assert history[-1].outcome is PollOutcome.ERROR
    assert isinstance(history, tuple)


def test_the_default_bound_is_a_day_at_the_fastest_poll_rate():
    # One poll every 10 s (Home Assistant's refresh debouncer) for 24 h.
    assert POLL_HISTORY_SIZE == 24 * 3600 // 10
    assert PollHistory().latest is None


def _record(minute: int, outcome: PollOutcome) -> PollRecord:
    return PollRecord(
        started=T0 + timedelta(minutes=minute), duration_ms=1500, outcome=outcome, attempts=1
    )


def test_no_failure_means_no_window():
    assert failure_windows([]) == []
    assert failure_windows([_record(0, PollOutcome.OK), _record(1, PollOutcome.OK)]) == []


def test_consecutive_failures_merge_into_one_window():
    windows = failure_windows([
        _record(0, PollOutcome.OK),
        _record(1, PollOutcome.TIMEOUT),
        _record(2, PollOutcome.HTTP_ERROR),
        _record(3, PollOutcome.TIMEOUT),
        _record(4, PollOutcome.OK),
    ])

    assert windows == [{
        "start": "2026-11-03T15:05:00+00:00",
        "end": "2026-11-03T15:07:01.500000+00:00",
        "count": 3,
        "outcomes": ["http_error", "timeout"],
        "ongoing": False,
    }]


def test_separate_runs_make_separate_windows_and_no_readings_counts():
    windows = failure_windows([
        _record(0, PollOutcome.NO_READINGS),
        _record(1, PollOutcome.OK),
        _record(2, PollOutcome.TIMEOUT),
        _record(3, PollOutcome.OK),
    ])

    assert [(w["count"], w["outcomes"]) for w in windows] == [
        (1, ["no_readings"]), (1, ["timeout"]),
    ]


def test_a_window_still_open_at_the_end_says_so():
    windows = failure_windows([
        _record(0, PollOutcome.OK),
        _record(1, PollOutcome.TIMEOUT),
        _record(2, PollOutcome.TIMEOUT),
    ])

    assert len(windows) == 1
    assert windows[0]["ongoing"] is True
    assert windows[0]["count"] == 2
