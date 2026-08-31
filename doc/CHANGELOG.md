# 1.2.3 2026-08-31
Fixes:
- Fix the websocket real-time update connection getting stuck in a silent crash-reconnect loop once the cloud rejects it with a persistent (non-token-expiry) error - reported as a repeating `Upgrade required, and then reconfigure the BLUETTI integration` / `BLUETTI WebSocket task crashed` cycle every ~30 seconds (bluetti-official/bluetti-home-assistant#145). Device data kept updating via the 30-second polling fallback throughout, but real-time push stayed broken with no visible signal beyond log spam. The integration now surfaces this as a Repair issue in Settings -> Devices & services -> Repairs instead, and `pybluetti` (>= 0.2.0) no longer leaks the previous connection's heartbeat task into every retry or re-logs the same full traceback on each one.

# 1.2.0 2026-08-25
New:
- The device's serial number now shows up in its Device Info panel (Settings -> Devices & services -> BLUETTI -> device page), matching how other Home Assistant integrations surface it.
- A single device can now be removed from an existing multi-device setup via its device page's "Delete" button, without having to remove and re-add the whole integration. This only stops Home Assistant from tracking the device - it does not unbind it from your BLUETTI account, so it can be added back later via Settings -> Devices & services -> BLUETTI -> Configure.

Internal:
- The BLUETTI cloud API client (HTTP + websocket push updates) now lives in a standalone package, [`pybluetti`](https://pypi.org/project/pybluetti/), instead of being embedded in this repo. Along the way, the websocket transport moved off the blocking `websocket-client` library (run on a dedicated thread) onto `aiohttp`'s native async websocket client - fully async, no threads. No user-visible behavior change; `manifest.json` now depends on `pybluetti>=0.1.0` instead of `pydantic`/`stomper`/`websocket-client` directly.
- Adopted `mypy --strict` across the whole codebase (wired into CI via `scripts/typecheck`), fulfilling the "strict-typing" requirement of Home Assistant's Platinum integration quality scale.

Fixes:
- Fix the device's real serial number appearing in plain text in downloaded diagnostics (in the device list, the `coordinators` keys, and the enabled-devices list under `entry_options`), even though the same serial is redacted everywhere else in the dump. It's now aliased to a stable "device_N" per dump instead, so devices in a multi-device dump can still be told apart without exposing the actual serial number.
- Fix the integration getting permanently stuck failing to set up with "BLUETTI setup failed: Implementation not available" if the underlying OAuth Application Credential is ever lost (e.g. a partial backup restore, or an entry created without going through the config flow). The default credential is now automatically re-imported and setup retried once, instead of requiring a manual remove-and-re-add of the integration.
- Fix the daily proactive OAuth token-refresh timer silently failing every single time it fired (a `TypeError` from a callback signature mismatch, found while adding strict typing) - the "check again in 24 hours" mechanism had effectively never worked.
- Fix two spots (`options_flow.py`, `oauth.py`) where adding a device on an account with zero BLUETTI devices bound to it would crash instead of showing "no devices available".
- Fix `set_state_value` crashing instead of just not applying the update if the cloud ever responds to a control command with a non-JSON body.
- Fix `hassfest` validation failures: `icons.json`'s entity translation keys used the cloud's raw, mixed-case `fn_code` values, which don't match Home Assistant's required key pattern; and `manifest.json`'s `documentation` field pointed at a URL reserved for integrations already bundled in Home Assistant core, not a custom integration like this one.
- Fix the "Online" binary sensor being registered under the `sensor.*` domain instead of `binary_sensor.*` - it was being added through the `sensor` platform's `async_add_entities` instead of its own `binary_sensor` platform (entity_id domain is decided by which platform registers the entity, not by the entity class's own base class). It now lives in its own `binary_sensor.py` platform file, matching `switch.py`/`select.py`.


# 1.1.0 2026-08-20
New:
- Add more devices to an existing setup later without logging in again, via Settings -> Devices & services -> BLUETTI -> Configure.
- Diagnostics download for troubleshooting, from the integration's device page.
- Every power (W) sensor - PV input, battery charge/discharge, grid input, AC/DC output, etc., on any supported model - now also gets a companion cumulated energy (kWh) sensor automatically, computed the same way as a manually added "Integral - Riemann sum" helper. No more setting up helpers by hand to use these values in the Energy dashboard.
- On models that don't report battery charge/discharge power directly (e.g. Balco260), an estimated battery charge power and discharge power sensor (and their kWh companions) are now added automatically, computed from the PV/grid/AC load balance. Clearly labeled "(Estimated)" since it's a power-balance approximation, not a real measurement.
- Diagnostics now also include each sensor's recognized type, to make it possible to tell "this data isn't sent by the cloud for my device" apart from "this data is sent but silently skipped" without digging through logs.

Fixes:
- Fix the OAuth token-refresh timer leak that could accumulate duplicate timers on every reload, causing recurring forced re-logins.
- Fix an unrecognized sensor type crashing the whole integration setup instead of just skipping that sensor.
- Fix a blocking call, a websocket thread that could die silently without reconnecting, and several other reliability issues found during a full code review.
- Fix the integration disappearing after a Home Assistant restart when adding a device for the first time.
- Fix a control showing the device's serial number instead of its real name.
- Fix a missing "unit" key in the cloud's sensor metadata (e.g. for enum-type sensors) crashing the whole sensor setup and silently dropping every other sensor on every device on the account, not just the affected one (EL400, FP, and likely other models - #101, #102).

Internal:
- Adopted Home Assistant's DataUpdateCoordinator pattern for polling and push updates.
- Reached Home Assistant's "Gold" integration quality scale.
- Added a full automated test suite (100% line coverage).
- Filled in translation keys that had gone missing from every shipped language except English since the config flow and options flow were added, and added a regression test so a translation file falling behind again fails CI instead of going unnoticed.
- Added `hacs.json` and a `hassfest`/HACS validation CI workflow, and filled in `manifest.json`'s `issue_tracker` field - the technical requirements for HACS default-repository inclusion (actual submission is still up to the maintainers).


# 1.0.2 2026-03-31
New power station models have been supported:

- EP500Pro
- AORA300
- AORA30V2
- RV5
- Balco 260,Balco 500
- AC300,AC500
- AC200PL,AC200L

Functions changes are as follows:
- Add "PV Input Power", "Grid Input Power", "AC Ouput Power" and "DC Ouput Power", only some specific models are supported.
- Fix token expired can`t auto refesh issue.


# 1.0.1 2025-12-15
New power station models have been supported:

- AP300
- EL300
- EL320, AORA320
- PR30V2, EL30V2
- EL400
- EP760
- PR100V2, EL100V2, AORA100V2
- PR200V2, Elite 200 V2, AORA200

Functions changes are as follows:

- Add "DC ECO", only some specific models are supported.
- Add "Sleep Mode"
- Remove "Disaster Warning"

# 1.0.0 2025-10-17
The first version of BLUETTI Integration for Home Assistant.  
BLUETTI Power Station Support List:

- EP6K
- EP13K
- EP2000
- FP