"""Tests for BluettiModbusCoordinator."""

from unittest.mock import AsyncMock, MagicMock

from modbus_connection.exceptions import AcknowledgeError, ModbusConnectionError
import pytest

from homeassistant.components.bluetti.modbus_coordinator import BluettiModbusCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed


def _device(values=None):
    device = MagicMock()
    device.async_update = AsyncMock()
    device._values = values or {}
    device.get_field.side_effect = lambda name: MagicMock(unit="W")
    return device


async def test_async_update_data_maps_results_by_name(hass):
    """Values read over Modbus are returned keyed by their field name."""
    device = _device(values={"b_soc": 42, "b_cycle_count": 12})
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert result["b_soc"].name == "b_soc"
    assert result["b_soc"].value == 42
    assert result["b_cycle_count"].value == 12


async def test_async_update_data_with_no_fields_returns_empty_dict(hass):
    """A device that reported no fields yields an empty result, not an error."""
    device = _device()
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert result == {}


async def test_modbus_error_becomes_update_failed(hass):
    """A Modbus error is surfaced as UpdateFailed, not the raw exception."""
    device = _device()
    device.async_update = AsyncMock(side_effect=ModbusConnectionError("no route to host"))
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_retries_once_after_an_acknowledge_response(hass):
    """An AcknowledgeError is retried once and can still succeed."""
    device = _device(values={"b_soc": 42})
    device.async_update = AsyncMock(side_effect=[AcknowledgeError(5), None])
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert device.async_update.await_count == 2
    assert result["b_soc"].value == 42


async def test_gives_up_after_a_second_acknowledge_response(hass):
    """A second consecutive AcknowledgeError is not retried again."""
    device = _device()
    device.async_update = AsyncMock(side_effect=[AcknowledgeError(5), AcknowledgeError(5)])
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert device.async_update.await_count == 2
