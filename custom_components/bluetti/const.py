"""Constants for the BLUETTI integration."""

DOMAIN: str = "bluetti"
INTEGRATION_NAME: str = "BLUETTI"

EVENT_TOKEN_EXPIRED: str = "onTokenExpired"  # noqa: S105 - event name, not a secret
NOTIFY_ID_TOKEN_EXPIRED: str = "notifyTokenExpire"  # noqa: S105 - notification ID, not a secret

# The cloud's websocket gateway does client identification/version gating -
# established while tracking down a persistent msgCode 600 ("Upgrade
# required, and then reconfigure the BLUETTI integration") rejection that
# never once succeeded on retry against a real device (issue #35). This key
# was issued specifically for this community integration - not the same one
# BLUETTI's own official app/integration uses - and is sent as the
# x-app-key CONNECT header alongside x-app-ver (this integration's own
# manifest.json version, read live - see its call site in __init__.py) and
# a fixed x-os:open. See pybluetti's own StompClient(app_key=, app_ver=)
# for where these actually get sent.
BLUETTI_APP_KEY: str = "1A08E300701BC91B273A417414E"

# The BLUETTI cloud API does not expose a stable per-account identifier, and
# this integration is designed around a single config entry that accumulates
# every device bound to whichever BLUETTI account the user authenticates
# with. This fixed unique_id lets the config flow use Home Assistant's
# standard duplicate-prevention mechanism instead of matching on the entry
# title.
ACCOUNT_UNIQUE_ID: str = "account"
