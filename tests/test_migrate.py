"""Tests for async_migrate_entry: the entry after local Modbus left."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti import (
    ISSUE_ID_MODBUS_DEPRECATED,
    ISSUE_ID_MODBUS_REMOVED,
    MODBUS_INTEGRATION_URL,
    async_migrate_entry,
)
from custom_components.bluetti.const import DOMAIN


def _entry(hass, *, options, version=1, minor_version=1) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        minor_version=minor_version,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": [
                {"sn": "SN1", "name": "Balco", "stateList": [], "online": "1"},
                {"sn": "SN2", "name": "AC200L", "stateList": [], "online": "1"},
            ],
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_a_modbus_connection_leaves_the_entry_its_entities_and_its_device(hass):
    entry = _entry(
        hass,
        options={"devices": ["SN1", "SN2"], "modbus": {"SN1": {"host": "10.2.1.60", "port": 502}}},
    )
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        sw_version="ARM 1.0, DSP 1.0",
        configuration_url="http://10.2.1.60",
    )
    entity_registry = er.async_get(hass)
    for domain, unique_id in (
        ("sensor", "SN1_modbus_ac_o_p"),
        ("number", "SN1_modbus_b_soc_low"),
        ("sensor", "SN1_SOC"),
        ("binary_sensor", "SN1_onLine"),
    ):
        entity_registry.async_get_or_create(
            domain, DOMAIN, unique_id, config_entry=entry, device_id=device.id
        )
    ir.async_create_issue(
        hass, DOMAIN, ISSUE_ID_MODBUS_DEPRECATED,
        is_fixable=False, severity=ir.IssueSeverity.WARNING, translation_key="modbus_deprecated",
    )

    assert await async_migrate_entry(hass, entry) is True

    assert entry.minor_version == 2
    assert entry.options == {"devices": ["SN1", "SN2"]}
    remaining = {e.unique_id for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)}
    assert remaining == {"SN1_SOC", "SN1_onLine"}
    device = device_registry.async_get(device.id)
    assert device.sw_version is None
    assert device.configuration_url is None

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID_MODBUS_DEPRECATED) is None
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID_MODBUS_REMOVED)
    assert issue is not None
    assert issue.is_persistent is True
    assert issue.learn_more_url == MODBUS_INTEGRATION_URL
    assert issue.translation_placeholders == {"devices": "Balco"}


async def test_an_entry_without_modbus_only_moves_on(hass):
    entry = _entry(hass, options={"devices": ["SN1"]})

    assert await async_migrate_entry(hass, entry) is True

    assert entry.minor_version == 2
    assert entry.options == {"devices": ["SN1"]}
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID_MODBUS_REMOVED) is None


async def test_a_device_gone_from_the_registry_is_skipped(hass):
    entry = _entry(hass, options={"devices": [], "modbus": {"SN9": {"host": "10.2.1.60", "port": 502}}})

    assert await async_migrate_entry(hass, entry) is True

    # Not among the entry's products: named by its serial.
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID_MODBUS_REMOVED)
    assert issue.translation_placeholders == {"devices": "SN9"}


async def test_an_entry_already_migrated_is_left_alone(hass):
    entry = _entry(hass, options={"devices": ["SN1"]}, minor_version=2)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.minor_version == 2


async def test_an_entry_from_a_newer_major_version_is_refused(hass):
    entry = _entry(hass, options={"devices": []}, version=2)

    assert await async_migrate_entry(hass, entry) is False


async def test_home_assistant_migrates_the_entry_before_setting_it_up(hass, enable_custom_integrations):
    entry = _entry(hass, options={"devices": [], "modbus": {"SN1": {"host": "10.2.1.60", "port": 502}}})

    with patch("custom_components.bluetti.async_get_clientsession", MagicMock()), \
         patch(
             "custom_components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
             AsyncMock(return_value=MagicMock()),
         ), \
         patch("custom_components.bluetti.config_entry_oauth2_flow.OAuth2Session") as mock_session_cls, \
         patch("custom_components.bluetti.StompClient") as mock_stomp_cls:
        mock_session_cls.return_value.token = {"access_token": "tok", "expires_at": time.time() + 10000}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert "modbus" not in entry.options
