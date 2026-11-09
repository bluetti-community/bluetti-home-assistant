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

# Lowercased fn_codes (= translation keys, see BluettiEntity) whose entity
# name comes from the translations, per platform. Every other fn_code keeps
# the name the cloud sends, so a model or field not listed here still gets a
# usable name. The English name of each is the one the cloud sends for it,
# so an English install keeps today's entity IDs; SetCtrlWorkModeBalco is
# the exception, since the cloud sends no name for it and its code was shown.
TRANSLATED_FN_CODES: dict[str, frozenset[str]] = {
    "sensor": frozenset({
        "soc",
        "pvalltotalpower",
        "gridalltotalpower",
        "acloadalltotalpower",
        "estimatedbatterychargepower",
        "estimatedbatterydischargepower",
    }),
    "switch": frozenset({"setctrlac", "setctrlstandby"}),
    "select": frozenset({"setctrlworkmodebalco"}),
}

# Power sensors whose integrated energy sensor has a translated name too,
# under the sensor key "<fn_code>_energy".
TRANSLATED_ENERGY_FN_CODES: frozenset[str] = frozenset({
    "pvalltotalpower",
    "gridalltotalpower",
    "acloadalltotalpower",
    "estimatedbatterychargepower",
    "estimatedbatterydischargepower",
})
