import logging
import time
from datetime import datetime, timedelta
from typing import Any, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from pybluetti import ProductClient, UnifyResponse, UserProduct

from .const import (
    ACCOUNT_UNIQUE_ID,
    DOMAIN,
    EVENT_TOKEN_EXPIRED,
    INTEGRATION_NAME,
    NOTIFY_ID_TOKEN_EXPIRED,
)
from .profile.application_profile import APPLICATION_PROFILE

__LOGGER__ = logging.getLogger(__name__)

ISSUE_ID_OAUTH_EXPIRED = "oauth_expired"


class OAuth2FlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """BLUETTI OAUTH2 handler."""

    DOMAIN = DOMAIN
    reauth_supported = True

    _oauth_data: dict[str, Any]
    _product_client: ProductClient
    _products: list[UserProduct]
    entry: config_entries.ConfigEntry

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Handle OAuth2 callback and create config entry."""
        self._oauth_data = data
        return await self.async_step_select_devices()

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let user select devices after OAuth2 login."""
        if user_input is not None:
            # Prevent configuring the same BLUETTI account twice: look up any
            # existing entry by its unique_id instead of matching on title.
            await self.async_set_unique_id(ACCOUNT_UNIQUE_ID)
            existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, ACCOUNT_UNIQUE_ID
            )
            if existing_entry is None:
                # Entries created before this integration used a stable
                # unique_id have none set; fall back to the old title match
                # once and backfill the unique_id so future lookups work.
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.unique_id is None and entry.title == f"{INTEGRATION_NAME} Power Integration":
                        self.hass.config_entries.async_update_entry(entry, unique_id=ACCOUNT_UNIQUE_ID)
                        existing_entry = entry
                        break

            if existing_entry and self.source not in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                # A plain "Add Integration" flow finding an existing entry
                # means a second account - reject before binding anything
                # server-side, don't merge and overwrite the first
                # account's token.
                return self.async_abort(reason="already_configured")

            try:
                result = await self._product_client.bind_devices({"bindSnList": user_input["devices"]})
            except Exception as err:
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
                return self.async_abort(reason="cannot_connect")

            # bind_devices() doesn't raise on a rejected bind - check msgCode.
            if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                return self.async_abort(reason="cannot_connect")

            # Only cache the products the user actually selected - self._products
            # holds every product on the account, and caching all of it means a
            # device added later (already present in this snapshot) would reuse
            # this stale data instead of the fresh get_user_products() fetch
            # that runs when it's actually added.
            selected_products = [p for p in self._products if p.sn in user_input["devices"]]

            if existing_entry:
                # Merge into the existing integration entry.
                existing_devices = existing_entry.options.get("devices", [])
                existing_products = existing_entry.data.get("products", [])

                merged_devices = list(set(existing_devices + user_input["devices"]))

                existing_product_sns = {p.get("sn") if isinstance(p, dict) else p.sn for p in existing_products}
                new_products = [p for p in selected_products if p.sn not in existing_product_sns]
                merged_products = existing_products + [p.model_dump() if hasattr(p, "model_dump") else p for p in new_products]

                # auth_implementation too, not just token - the user could
                # have picked a different Application Credential during this
                # login. async_update_entry() already fires the entry's
                # registered update listener, which reloads it - no separate
                # reload needed.
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        "auth_implementation": self._oauth_data["auth_implementation"],
                        "token": self._oauth_data["token"],
                        "products": merged_products
                    },
                    options={"devices": merged_devices}
                )

                return self.async_abort(reason="success")
            # Create a new integration entry.
            return self.async_create_entry(
                title=f"{INTEGRATION_NAME} Power Integration",
                data={
                    "auth_implementation": self._oauth_data["auth_implementation"],
                    "token": self._oauth_data["token"],
                    "products": [p.model_dump() for p in selected_products]
                },
                options=user_input,
            )

        httpSession = async_get_clientsession(self.hass)
        access_token = self._oauth_data["token"]["access_token"]
        product_client = ProductClient(
            httpSession,
            APPLICATION_PROFILE.config["server"]["gateway"],
            access_token,
            on_auth_expired=lambda: self.hass.bus.fire(EVENT_TOKEN_EXPIRED),
        )
        try:
            products = await product_client.get_user_products()
        except Exception as err:
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", err)
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
        if not products.data:
            return self.async_abort(reason="no_devices_available")

        self._product_client = product_client
        self._products = products.data

        # 获取已集成的设备列表
        integrated_devices = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            integrated_devices.update(entry.options.get("devices", []))

        # 过滤掉已经集成过的设备
        available_devices = {
            prod.sn: f"{prod.name} - {prod.sn}"
            for prod in products.data
            if prod.sn not in integrated_devices
        }


        # reconfigure token
        if "entry_id" in self.context:
            cur_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if cur_entry is None:
                return self.async_abort(reason="reconfigure_failed")
            __LOGGER__.info("reconfigure token")
            # auth_implementation too, not just token - the user could have
            # picked a different Application Credential during this login.
            new_data = {
                **cur_entry.data,
                "auth_implementation": self._oauth_data["auth_implementation"],
                "token": self._oauth_data["token"],
            }
            # async_update_entry() already fires the entry's registered
            # update listener, which reloads it - no separate reload needed.
            self.hass.config_entries.async_update_entry(cur_entry, data=new_data)
            return self.async_abort(reason="success")

        # 已全部集成
        if not available_devices:
            return self.async_abort(reason="all_devices_exists")

        schema = vol.Schema(
            {
                vol.Required(
                    "devices",
                    default=list(available_devices.keys())
                ): cv.multi_select(available_devices)
            }
        )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=schema,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reauth configure"""
        found_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if found_entry is None:
            return self.async_abort(reason="reconfigure_failed")
        self.entry = found_entry

        return await self.async_step_user()


class AsyncConfigEntryAuth:
    """Provide BLUETTI authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize BLUETTI auth."""
        self._websession = websession
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast("str", self._oauth_session.token["access_token"])


class AuthTokenRefresh:
    """Handler Token expired and refresh token."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.oAuth2Session = oauth_session
        unsub = hass.bus.async_listen(EVENT_TOKEN_EXPIRED, self.on_token_expired_event)
        entry.async_on_unload(unsub)

    async def on_token_expired_event(self, event: Event[Any]) -> None:
        __LOGGER__.info("on_token_expired_event")
        self.send_expired_notification()

    def start_token_check(self) -> None:
        # first clear old notify
        persistent_notification.async_dismiss(self.hass,notification_id=NOTIFY_ID_TOKEN_EXPIRED)
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ID_OAUTH_EXPIRED)
        if not self.is_token_valid():
            __LOGGER__.info("token have expired send notify")
            self.send_expired_notification()
        else:
            interval = timedelta(days=1)
            unsub = async_track_time_interval(
                self.hass,
                self.async_check_token_expiry,  # 要执行的任务函数
                interval       # 执行间隔
            )
            self.entry.async_on_unload(unsub)
            __LOGGER__.info("token is valid after 24 hours to check again")
        # Entry-scoped so it's canceled on unload, rather than a bare
        # hass-level task outliving the entry.
        self.entry.async_create_background_task(
            self.hass,
            self.async_check_token_expiry(),
            name="bluetti_initial_token_expiry_check",
        )


    # check oauth2 token is ok
    def is_token_valid(self) -> bool:
        """Check token"""
        token = self.oAuth2Session.token
        if not token:
            return False

        if "expires_at" in token:
            expire_timestamp = cast("float", token["expires_at"]) - 30
            current_timestamp = time.time()
            return expire_timestamp > current_timestamp

        if "expires_in" in token and "created_at" in token:
            expire_timestamp = cast("float", token["created_at"]) + cast("float", token["expires_in"]) - 30
            current_timestamp = time.time()
            return expire_timestamp > current_timestamp

        return False

    # show token expire notify
    def send_expired_notification(self) -> None:
        reauth_url = f"/config/integrations/integration/{DOMAIN}"
        notification_message = (
            "Your OAuth token has expired.\n"
            f"Please go to the **[integration settings]({reauth_url})** page and click [Reconfigure] to complete the login."
        )
        persistent_notification.async_create(
            self.hass,
            notification_message,
            title = "OAuth Expired",
            notification_id = NOTIFY_ID_TOKEN_EXPIRED,
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_ID_OAUTH_EXPIRED,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="oauth_expired",
        )

    # check token is in 7 day if in 7day refesh token
    async def async_check_token_expiry(self, now: datetime | None = None) -> None:
        """
        Check whether the token needs a refresh, and refresh it if so.

        Registered directly as the callback for async_track_time_interval,
        which always calls it with the current UTC time - `now` must be
        accepted even though this method doesn't use it, or every timer
        fire raises TypeError and silently breaks the daily proactive
        check. Also called manually with no argument (start_token_check,
        on a fresh timer registration), which is why it stays optional.
        """
        __LOGGER__.info("check token is expired")
        expire_timestamp = self.oAuth2Session.token.get("expires_at")
        if expire_timestamp is None:
            __LOGGER__.warning("No expires_at in token, skipping expiry check")
            return
        current_timestamp = time.time()
        remain_timestamp = expire_timestamp - current_timestamp

        # Also tries an already-expired token, not just an expiring one - a
        # refresh token normally covers this fine.
        if remain_timestamp < 3600*24*7 :
            try:
                __LOGGER__.info("start refresh token")
                last_refesh = self.entry.data.get("last_token_refresh", 0.0)
                # 1 hour only one time ,when server is 500 do not always refesh token
                if current_timestamp - last_refesh < 3600 :
                    __LOGGER__.info("last refesh token in 1 hour,this do not refesh return")
                    if remain_timestamp < 0:
                        self.send_expired_notification()
                    return
                last_refesh = current_timestamp

                new_token = await self.oAuth2Session.implementation.async_refresh_token(self.oAuth2Session.token)
                # async_update_entry() already fires the registered update
                # listener, which reloads - no separate reload needed here.
                self.hass.config_entries.async_update_entry(
                    self.entry, data={**self.entry.data, "token": new_token,"last_token_refresh":last_refesh}
                )
                __LOGGER__.info("refresh token ok")
            except Exception as e:
                __LOGGER__.error("refresh token failed: %s", e)
                if remain_timestamp < 0:
                    self.send_expired_notification()
