"""Entity names and IDs, through a real setup that loads the translations."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti.const import DOMAIN

POWER = {"sensorType": "SensorDeviceClass.POWER"}
# Names as the cloud sends them for a Balco 260.
STATE_LIST = [
    {"fnCode": "SOC", "fnName": "Battery Level", "fnValue": "80", "fnType": "SENSOR",
     "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": "%"}},
    {"fnCode": "PVAllTotalPower", "fnName": "Photovoltaics Input Power", "fnValue": "0",
     "fnType": "SENSOR", "sensorInfo": POWER},
    {"fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "0",
     "fnType": "SENSOR", "sensorInfo": POWER},
    {"fnCode": "ACLoadAllTotalPower", "fnName": "Alternating Current Out Power", "fnValue": "0",
     "fnType": "SENSOR", "sensorInfo": POWER},
    {"fnCode": "DCLoadAllTotalPower", "fnName": "DC Load Power", "fnValue": "0",
     "fnType": "SENSOR", "sensorInfo": POWER},
    {"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"},
    {"fnCode": "SetCtrlWorkModeBalco", "fnValue": "workmode_1", "fnType": "SELECT",
     "supportModeValues": [{"code": "workmode_1", "name": "Self Consumption"}]},
]

# unique_id -> (English entity_id, English name, French name). The English
# entity IDs are the ones a new install got before the names were
# translated, except the select, whose name was its bare fn_code.
EXPECTED = {
    "SN1_SOC": ("sensor.sn1_battery_level", "Battery Level", "SoC batterie"),
    "SN1_PVAllTotalPower": (
        "sensor.sn1_photovoltaics_input_power", "Photovoltaics Input Power",
        "Puissance d'entrée PV",
    ),
    "SN1_PVAllTotalPower_energy": (
        "sensor.sn1_photovoltaics_input_power_energy", "Photovoltaics Input Power Energy",
        "Énergie d'entrée PV",
    ),
    "SN1_GridAllTotalPower": (
        "sensor.sn1_grid_input_power", "Grid Input Power", "Puissance d'entrée réseau",
    ),
    "SN1_ACLoadAllTotalPower": (
        "sensor.sn1_alternating_current_out_power", "Alternating Current Out Power",
        "Puissance de sortie AC",
    ),
    "SN1_ACLoadAllTotalPower_energy": (
        "sensor.sn1_alternating_current_out_power_energy",
        "Alternating Current Out Power Energy", "Énergie de sortie AC",
    ),
    # Not translated: the cloud's name in every language.
    "SN1_DCLoadAllTotalPower": ("sensor.sn1_dc_load_power", "DC Load Power", "DC Load Power"),
    "SN1_DCLoadAllTotalPower_energy": (
        "sensor.sn1_dc_load_power_energy", "DC Load Power Energy", "DC Load Power Energy",
    ),
    "SN1_SetCtrlAc": ("switch.sn1_ac", "AC", "Sortie AC"),
    "SN1_SetCtrlWorkModeBalco": ("select.sn1_working_mode", "Working Mode", "Mode de fonctionnement"),
}


async def _set_up(hass) -> None:
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
    answer = MagicMock(
        data=[MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])],
        is_ok=lambda: True,
    )
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
        mock_product_cls.return_value.get_device_status = AsyncMock(return_value=answer)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("language", "column"), [("en", 1), ("fr", 2)])
async def test_a_new_install_gets_these_entity_ids_and_names(
    hass, enable_custom_integrations, language, column
):
    hass.config.language = language
    await _set_up(hass)
    registry = er.async_get(hass)

    for unique_id, expected in EXPECTED.items():
        domain = expected[0].split(".")[0]
        entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        # Home Assistant builds a new entity ID from the name in the
        # configured language when it has native entity IDs (French does).
        assert entity_id == f"{domain}.{slugify(f'SN1 {expected[column]}')}", unique_id
        if language == "en":
            assert entity_id == expected[0], unique_id
        # The device is named after its serial number.
        assert hass.states.get(entity_id).name == f"SN1 {expected[column]}", unique_id
