"""Tests for application_credentials.py."""

from homeassistant.components import application_credentials
from homeassistant.setup import async_setup_component

from custom_components.bluetti.application_credentials import (
    async_ensure_default_credential,
    async_get_authorization_server,
)
from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.profile.application_profile import APPLICATION_PROFILE


async def test_async_get_authorization_server(hass):
    server = await async_get_authorization_server(hass)

    gateway_sso = APPLICATION_PROFILE.config["server"]["sso"]
    assert server.authorize_url == f"{gateway_sso}/oauth2/grant"
    assert server.token_url == f"{gateway_sso}/oauth2/token"


def _stored_credential(hass):
    collection = hass.data[application_credentials.DATA_COMPONENT]
    return collection.async_client_credentials(DOMAIN).get(DOMAIN)


async def test_async_ensure_default_credential_imports_it(hass, enable_custom_integrations):
    await async_setup_component(hass, "application_credentials", {})

    await async_ensure_default_credential(hass)

    credential = _stored_credential(hass)
    assert credential is not None
    assert credential.client_id == "HomeAssistant"


async def test_async_ensure_default_credential_is_idempotent(hass, enable_custom_integrations):
    # A missing credential (e.g. lost in a partial backup restore) must be
    # safe to re-import on every setup attempt, not just the first one.
    await async_setup_component(hass, "application_credentials", {})

    await async_ensure_default_credential(hass)
    await async_ensure_default_credential(hass)

    collection = hass.data[application_credentials.DATA_COMPONENT]
    assert len(collection.async_client_credentials(DOMAIN)) == 1
