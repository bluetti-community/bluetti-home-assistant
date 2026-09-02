"""Tests for BluettiModbusCoordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from modbus_connection.exceptions import ModbusConnectionError, ModbusTimeoutError

from custom_components.bluetti.modbus_coordinator import BluettiModbusCoordinator


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_client_is_built_once_from_arguments(client_cls, hass):
    client_cls.return_value.read = AsyncMock(return_value=[])

    BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    client_cls.assert_called_once_with("10.2.1.60", 502, "balco260")


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_repeated_updates_reuse_the_same_client(client_cls, hass):
    client_cls.return_value.read = AsyncMock(return_value=[])
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    client_cls.assert_called_once_with("10.2.1.60", 502, "balco260")
    assert client_cls.return_value.read.await_count == 2


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_async_update_data_maps_results_by_name(client_cls, hass):
    field1 = MagicMock(name="b_soc")
    field1.name = "b_soc"
    field2 = MagicMock(name="b_cycle_count")
    field2.name = "b_cycle_count"
    client_cls.return_value.read = AsyncMock(return_value=[field1, field2])
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    result = await coordinator._async_update_data()

    assert result == {"b_soc": field1, "b_cycle_count": field2}


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_modbus_error_becomes_update_failed(client_cls, hass):
    client_cls.return_value.read = AsyncMock(side_effect=ModbusConnectionError("no route to host"))
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert client_cls.return_value.read.await_count == 2


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_modbus_error_retries_once_before_giving_up(client_cls, hass):
    """
    A transient read failure (e.g. a malformed frame) must not surface as
    unavailable if the very next attempt, moments later, succeeds.

    Regression test: this device's Modbus TCP stack has been observed
    returning a truncated response for a single register block, seen in
    production activity logs recurring many times a day. Without a retry,
    every one of those glitches made the entities flap unavailable for a
    full 30s poll interval.
    """
    field = MagicMock(name="b_soc")
    field.name = "b_soc"
    client_cls.return_value.read = AsyncMock(
        side_effect=[ModbusTimeoutError("no response"), [field]]
    )
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    result = await coordinator._async_update_data()

    assert result == {"b_soc": field}
    assert client_cls.return_value.read.await_count == 2


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_device_property_returns_the_clients_device(client_cls, hass):
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    assert coordinator.device is client_cls.return_value.device


@patch("custom_components.bluetti.modbus_coordinator.BluettiModbusClient")
async def test_async_shutdown_closes_the_underlying_client(client_cls, hass):
    client_cls.return_value.aclose = AsyncMock()
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", "10.2.1.60", 502, "balco260")

    await coordinator.async_shutdown()

    client_cls.return_value.aclose.assert_awaited_once()
