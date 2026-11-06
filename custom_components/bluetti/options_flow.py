"""
Options flow for the BLUETTI integration.

Lets the user add devices bound to their BLUETTI account after the initial
setup, without going through the OAuth2 login flow again (the stored token
is reused).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pybluetti import ProductClient, UnifyResponse, UserProduct

from .cloud_retry import describe_error
from .const import EVENT_TOKEN_EXPIRED
from .gateway import cloud_products, entry_gateway, gateway_url, log_no_cloud_devices

__LOGGER__ = logging.getLogger(__name__)


class BluettiOptionsFlowHandler(OptionsFlow):
    """Handle an options flow to add BLUETTI devices to an existing entry."""

    _product_client: ProductClient
    _products: list[UserProduct]

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Go straight to the add-devices form, the only option there is."""
        return await self.async_step_add_devices(user_input)

    async def async_step_add_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick additional devices from their BLUETTI account."""
        entry: ConfigEntry = self.config_entry

        if user_input is not None:
            selected = user_input["devices"]
            try:
                result = await self._product_client.bind_devices({"bindSnList": selected})
            except Exception as err:
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", describe_error(err))
                return self.async_abort(reason="cannot_connect")

            # bind_devices() doesn't raise on a rejected bind - check msgCode.
            if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                return self.async_abort(reason="cannot_connect")

            current_devices = entry.options.get("devices", [])
            merged_devices = list(set(current_devices) | set(selected))

            existing_products = entry.data.get("products", [])
            existing_sns = {p.get("sn") if isinstance(p, dict) else p.sn for p in existing_products}
            # Only merge in the products actually selected this time -
            # self._products holds every product on the account, and merging
            # all of it would cache stale metadata for devices left unchecked.
            new_products = [p for p in self._products if p.sn in selected and p.sn not in existing_sns]
            merged_products = existing_products + [p.model_dump() for p in new_products]

            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, "products": merged_products}
            )

            # async_create_entry's data REPLACES entry.options wholesale (see
            # OptionsFlowManager.async_finish_flow) - carry every other key
            # forward explicitly.
            return self.async_create_entry(data={**entry.options, "devices": merged_devices})

        access_token = entry.data["token"]["access_token"]
        http_session = async_get_clientsession(self.hass)
        product_client = ProductClient(
            http_session,
            gateway_url(entry_gateway(entry.data)),
            access_token,
            on_auth_expired=lambda: self.hass.bus.fire(EVENT_TOKEN_EXPIRED),
        )
        try:
            products = await product_client.get_user_products_v2()
        except Exception as err:
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", describe_error(err))
            return self.async_abort(reason="cannot_connect")

        # A failed application-level response (nonzero msgCode) doesn't
        # raise - it would otherwise look like a real "no devices" account.
        if not products.is_ok():
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", products)
            return self.async_abort(reason="cannot_connect")

        # Checked before iterating products.data below: it's `T | None` on
        # the wire, and a cloud response that omits "data" entirely would
        # otherwise crash the dict comprehension with an unhandled
        # TypeError instead of aborting gracefully.
        usable_products = cloud_products(products.data or [])
        if not usable_products:
            log_no_cloud_devices(entry_gateway(entry.data), products.data or [])
            return self.async_abort(reason="no_devices_available")

        self._product_client = product_client
        self._products = usable_products

        enabled_devices = set(entry.options.get("devices", []))
        available_devices = {
            product.sn: f"{product.name} - {product.sn}"
            for product in usable_products
            if product.sn not in enabled_devices
        }

        if not available_devices:
            return self.async_abort(reason="all_devices_exists")

        schema = vol.Schema(
            {
                vol.Required(
                    "devices",
                    default=list(available_devices.keys()),
                ): cv.multi_select(available_devices)
            }
        )

        # Home Assistant 2026.10 types data_schema as probatio.Schema; inside
        # Home Assistant, voluptuous's Schema is that same class.
        return self.async_show_form(
            step_id="add_devices",
            data_schema=schema,  # type: ignore[arg-type,unused-ignore]
        )
