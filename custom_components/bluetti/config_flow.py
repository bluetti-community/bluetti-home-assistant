"""Copyright (C) 2025 BLUETTI Corporation."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .application_credentials import async_ensure_default_credential
from .const import DOMAIN
from .oauth import OAuth2FlowHandler
from .options_flow import BluettiOptionsFlowHandler
from .profile.application_profile import APPLICATION_PROFILE


class BluettiConfigFlow(OAuth2FlowHandler, domain=DOMAIN):
    """BLUETTI Custom Integration config flow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        await APPLICATION_PROFILE.load_config(self.hass)
        await async_ensure_default_credential(self.hass)
        return await super().async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BluettiOptionsFlowHandler:
        """Return the options flow used to add more devices later."""
        return BluettiOptionsFlowHandler()
