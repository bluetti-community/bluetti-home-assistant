"""Application credentials platform for the BLUETTI integration."""

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    AuthImplementation,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .profile.application_profile import APPLICATION_PROFILE


class DirectCallbackAuthImplementation(AuthImplementation):
    """Auth implementation that redirects straight to this HA instance.

    BLUETTI SSO authorization codes expire in under about 60 seconds. The
    default redirect_uri points at my.home-assistant.io, whose hop (instance
    URL form on a browser without saved state, then the Link-account click)
    can exceed that budget, so the code reaches HA's token exchange already
    expired ("Expired authorize code."). Deriving redirect_uri from
    hass.config.api keeps authorize and token exchange consistent (HA embeds
    the implementation's redirect_uri in both the authorize URL and the
    state JWT) and cuts code-to-exchange to about a second.
    """

    @property
    def redirect_uri(self) -> str:
        """Redirect to this instance's own external callback."""
        api = self.hass.config.api
        scheme = "https" if api.use_ssl else "http"
        port = "" if api.port in (80, 443) else f":{api.port}"
        return f"{scheme}://{api.local_ip}{port}/auth/external/callback"


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> DirectCallbackAuthImplementation:
    """Return the direct-callback implementation for the given credential."""
    server = await async_get_authorization_server(hass)
    return DirectCallbackAuthImplementation(hass, auth_domain, credential, server)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    await APPLICATION_PROFILE.load_config(hass)
    return AuthorizationServer(
        authorize_url=APPLICATION_PROFILE.config["server"]["sso"] + "/oauth2/grant",
        token_url=APPLICATION_PROFILE.config["server"]["sso"] + "/oauth2/token",
    )


async def async_ensure_default_credential(hass: HomeAssistant) -> None:
    """
    (Re-)import the integration's built-in OAuth2 client credential.

    Home Assistant resolves a config entry's OAuth2 implementation by looking
    up this credential in Application Credentials storage. If it is ever
    missing there - lost in a partial backup restore, or an entry that was
    created without going through the config flow - every future setup of
    that entry fails with "Implementation not available" until this import
    runs again. `async_import_client_credential` is a no-op when the
    credential already exists, so this is safe to call on every config flow
    run and every integration setup.
    """
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("HomeAssistant", "SG9tZUFzc2lzdGFudA=="),
    )
