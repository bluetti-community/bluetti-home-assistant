"""
Which BLUETTI cloud gateway (data center) serves this account.

The cloud has one sign-in server but several REST gateways, one per data
center, and a gateway rejects a token issued for an account held elsewhere
with msgCode 805 - the same code as a genuinely expired token. The token
response does not say which data center holds the account (no such field
is returned, checked on accounts in France and Germany on 2026-09-22), so
the integration finds out the only way it can: it asks the default gateway
for the account's devices and, if that one rejects a token the sign-in
just issued, asks the other data centers in turn. The one that answers is
remembered in the config entry and used from then on.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pybluetti import UnifyResponse, UserProduct

from .profile.application_profile import APPLICATION_PROFILE

__LOGGER__ = logging.getLogger(__name__)

# Config entry data key holding the data center the account answered from.
CONF_GATEWAY = "gateway"
# The profile's gateway: gw.bluettipower.com unless application.yaml says otherwise.
GATEWAY_GLOBAL = "global"
# The other data centers known to serve accounts, keyed the way the entry
# stores the choice. EU: BLUETTI's own recommendation for European accounts
# (bluetti-official/bluetti-home-assistant#72), confirmed on a German account
# (#172). US: reported working for a US account (#72).
GATEWAY_URLS: dict[str, str] = {
    "eu": "https://gwde.bluettipower.com",
    "us": "https://gwpry.bluettipower.com",
}
# msgCode a gateway returns for a token it will not honour - expired, or
# issued for an account another data center holds.
TOKEN_REJECTED = 805

FetchProducts = Callable[[str], Awaitable[UnifyResponse[list[UserProduct]]]]


def gateway_url(region: str) -> str:
    """The REST gateway base URL for a data center key."""
    if region == GATEWAY_GLOBAL:
        return str(APPLICATION_PROFILE.config["server"]["gateway"])
    return GATEWAY_URLS[region]


def entry_gateway(data: Mapping[str, Any]) -> str:
    """The data center a config entry recorded, or the default for one that predates the choice."""
    region = data.get(CONF_GATEWAY, GATEWAY_GLOBAL)
    if region == GATEWAY_GLOBAL or region in GATEWAY_URLS:
        return str(region)
    return GATEWAY_GLOBAL


async def async_probe_gateway(
    fetch_products: FetchProducts, preferred: str
) -> tuple[str, UnifyResponse[list[UserProduct]]]:
    """
    Fetch the account's devices from the data center that serves it.

    ``fetch_products`` is called with a gateway URL and returns the devices
    response from it; the preferred data center goes first, then the others,
    until one does not answer msgCode 805. Anything other than that code -
    success, another application error, or an exception - ends the search
    there, so a genuine failure surfaces to the caller unchanged. If every
    data center rejects the token, the preferred one's response is returned:
    the token really has expired, and the caller handles that as before.
    """
    others = [r for r in (GATEWAY_GLOBAL, *GATEWAY_URLS) if r != preferred]
    response = await fetch_products(gateway_url(preferred))
    if getattr(response, "msgCode", 0) != TOKEN_REJECTED:
        return preferred, response
    for region in others:
        __LOGGER__.info(
            "The account's token was rejected (code %d); trying the %s data center",
            TOKEN_REJECTED,
            region,
        )
        candidate = await fetch_products(gateway_url(region))
        if getattr(candidate, "msgCode", 0) != TOKEN_REJECTED:
            return region, candidate
    return preferred, response
