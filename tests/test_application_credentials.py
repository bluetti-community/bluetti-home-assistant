"""Tests for application_credentials.py."""

from homeassistant.components import application_credentials
from homeassistant.setup import async_setup_component

from custom_components.bluetti.application_credentials import (
    DirectCallbackAuthImplementation,
    async_ensure_default_credential,
    async_get_auth_implementation,
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


async def _get_implementation(hass):
    await async_setup_component(hass, "application_credentials", {})
    await async_ensure_default_credential(hass)
    collection = hass.data[application_credentials.DATA_COMPONENT]
    credential = collection.async_client_credentials(
        "bluetti"
    ).get("bluetti")
    assert credential is not None
    return await async_get_auth_implementation(hass, "bluetti", credential)


async def test_async_get_auth_implementation_returns_direct_callback(hass):
    implementation = await _get_implementation(hass)

    assert isinstance(implementation, DirectCallbackAuthImplementation)
    # Inherited behavior is unchanged: SSO endpoints come from the profile.
    gateway_sso = APPLICATION_PROFILE.config["server"]["sso"]
    assert implementation.authorize_url == f"{gateway_sso}/oauth2/grant"
    assert implementation.token_url == f"{gateway_sso}/oauth2/token"


async def test_redirect_uri_points_at_this_instance(hass):
    implementation = await _get_implementation(hass)

    api = hass.config.api
    scheme = "https" if api.use_ssl else "http"
    port = "" if api.port in (80, 443) else f":{api.port}"
    expected = f"{scheme}://{api.local_ip}{port}/auth/external/callback"

    assert implementation.redirect_uri == expected
    # The redirect URI must be HA's own external callback: the OAuth flow
    # embeds it in both the authorize URL and the state JWT, and BLUETTI's
    # token exchange validates the same value (this is what removes the
    # my.home-assistant.io hop whose latency exceeds the SSO code TTL).
    assert implementation.redirect_uri.endswith("/auth/external/callback")


async def test_redirect_uri_omits_default_ports(hass, monkeypatch):
    implementation = await _get_implementation(hass)

    class FakeAPI:
        local_ip = "10.0.0.5"
        port = 8123
        use_ssl = False

    monkeypatch.setattr(implementation.hass.config, "api", FakeAPI())
    assert implementation.redirect_uri == "http://10.0.0.5:8123/auth/external/callback"

    FakeAPI.port = 443
    FakeAPI.use_ssl = True
    assert implementation.redirect_uri == "https://10.0.0.5/auth/external/callback"
