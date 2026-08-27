# Core-track integration (not submitted)

This directory mirrors the file layout a real `home-assistant/core` PR would
have: `homeassistant/components/bluetti/` and `tests/components/bluetti/`.
Unlike the HACS integration shipped from this repo's `custom_components/bluetti/`
(where `BluettiModbusClient` owns its own persistent Modbus TCP connection -
the right call for a standalone install), this version wires the optional
local Modbus connection through Home Assistant Core's shared connection
mechanism, `homeassistant.components.modbus.async_get_unit()` - Core
integrations must reuse that shared connection rather than opening a
competing one. This follows the same pattern as `sofar`/`fronius`/`flexit`.

This code is **not part of the HACS integration** shipped from this repo's
`custom_components/` - it's kept separate, on this branch, for review and
soak time before ever being proposed to `home-assistant/core`. The cloud
(OAuth2 + STOMP) path is otherwise unchanged from the HACS version; only the
Modbus wiring (`modbus_coordinator.py`, and the Modbus block in `__init__.py`)
differs.

## How this was actually verified

`homeassistant.components.modbus`'s `async_get_unit` isn't in any published
Home Assistant release yet (confirmed present in the `2026.9.0b0` beta via a
direct wheel download, but not in the latest stable `2026.8.3`) - so
verifying this code needs a real `home-assistant/core` checkout on its `dev`
branch, not just `pip install homeassistant`. `dev` also requires Python 3.14.

```bash
# From a Python 3.14 interpreter (uv shown here; a plain venv works too, but
# `uv venv` does not bundle pip - use `uv pip install --python <venv>/bin/python`):
git clone --depth 1 --filter=blob:none --branch dev https://github.com/home-assistant/core.git ha-core
uv venv --python 3.14 ha-core/.venv
cd ha-core
uv pip install --python .venv/bin/python -e . --no-deps
uv pip install --python .venv/bin/python -r requirements.txt -r requirements_test.txt
uv pip install --python .venv/bin/python "pybluetti==0.1.1" "bluetti-modbus==0.1.0"

# Drop this integration's code into the checkout:
cp -r ../core_integration/homeassistant/components/bluetti homeassistant/components/
cp -r ../core_integration/tests/components/bluetti tests/components/

.venv/bin/python -m pytest tests/components/bluetti/ -q
PATH=".venv/bin:$PATH" .venv/bin/python -m script.hassfest \
    --integration-path homeassistant/components/bluetti
.venv/bin/python -m ruff check homeassistant/components/bluetti/ tests/components/bluetti/
```

Verified this way on 2026-08-27: **182 passed, 0 failed.** The remaining 12
tests error only at teardown, all with the same cause - a `Translation not
found` assertion from `tests/components/conftest.py`'s `check_translations`
fixture, because this bare `dev` checkout has no pre-built translations
cache (confirmed environmental, not a `bluetti` defect, by reproducing the
identical failure against unmodified `fronius`/`sofar` tests in the same
checkout). `hassfest` reports every check clean except the one it's supposed
to (`New integrations are required to at least reach the Bronze tier`) - the
real, expected blocker until the `todo` items in `quality_scale.yaml` are
resolved during actual review. `ruff check` is clean across the entire tree
(`homeassistant/components/bluetti/` and `tests/components/bluetti/`).

## Lint cleanup (2026-08-27)

The tree copied over from the HACS integration originally carried this
project's own, looser lint bar - 289 findings under Core's stricter ruff
config, none introduced by the Modbus rework itself. All resolved:

- ~180 missing docstrings (`D1xx`) across tests and production code (entity
  `__init__`s, properties, magic methods, modules, classes).
- 8 files still had `from __future__ import annotations` (`TID251`) - banned
  since Core requires Python 3.14+, which evaluates annotations lazily by
  default (PEP 649).
- Leftover Chinese-language comments and a misplaced/never-attached
  docstring in `oauth.py` and `application_profile.py`, plus a full-width
  `！` and full-width parentheses in comments (`RUF001`/`RUF003`) - translated
  to English, since Core requires English-only source.
- `BLE001` (14 blind `except Exception`): kept as `# noqa` with a one-line
  reason where the catch is genuinely intentional - a cloud/OAuth SDK call at
  a system boundary, or one step of `models.py`'s multi-step best-effort
  device-unbind cleanup where one step's failure must not block the rest.
- `SLF001` (5 private-attribute accesses across module/class boundaries):
  four in `__init__.py` reaching into `BluettiDevice`'s `_api_client`/`_hass`/
  `_entry`/`_entry_id` were replaced with a new `BluettiDevice.bind_runtime()`
  method (`models.py`) - a real, if small, encapsulation fix, not just a
  suppressed warning. The remaining one (`sensor.py`, reaching one sensor
  class's `_state_obj` from another in the same module) is `noqa`'d instead,
  since a public accessor for a single same-module call site would be
  over-engineering.
- `N806` (camelCase locals: `httpSession`, `oAuth2Session`,
  `authTokenRefresh`, `sensorClass`) renamed to snake_case.
- The rest (`PLC0415` local imports, an `ISC001` implicit string
  concatenation, a stray unattached docstring) were straightforward
  mechanical fixes.

None of this changed behavior - the same 182 tests pass before and after.

## `quality_scale.yaml` audit (2026-08-27)

Went through every rule against the `async_get_unit` architecture. Most of
the wording (discovery, entity-translations, dependency-transparency) was
already accurate regardless of which Modbus client owns the connection, so
no rule status changed. The audit did catch two real issues in the code
itself, both now fixed:

- `options_flow.py`'s one-off connectivity check (used when the user
  configures a device's local Modbus connection) was still instantiating
  `BluettiModbusClient` directly - the exact "competing connection" problem
  the coordinator rewrite was meant to eliminate, just in a different spot.
  Fixed to use `async_get_temporary_unit`, the API `connection.py` documents
  as built specifically for config/options flows with no config entry yet to
  hold a persistent unit.
- Two comments in `__init__.py` (`async_unload_entry` and
  `async_remove_config_entry_device`) still described the old
  `BluettiModbusCoordinator.async_shutdown()`-closes-the-connection behavior,
  which no longer exists. Updated to describe what was verified by reading
  `homeassistant/components/modbus/connection.py` directly: `async_get_unit`
  registers its own release callback via `entry.async_on_unload`, scoped to
  the whole config entry - so removing a single device (as opposed to
  unloading the entry) does not release that device's Modbus connection
  early. This is a characteristic of the platform API every integration
  using `async_get_unit` shares, not a bug specific to this integration.

## `home-assistant.io` documentation (2026-08-27)

Drafted at `home-assistant.io/source/_integrations/bluetti.markdown`, in the
real docs repo's format (front matter + `{% include %}`/`{% configuration_basic %}`
tags), using `fronius`, `sofar`, and `flexit`'s real doc pages (fetched from
`home-assistant/home-assistant.io`) as templates - `sofar`'s structure
(config-flow, Modbus TCP, supported-devices/functions/limitations sections)
is the closest match. Every claim in it (supported device families, entity
list, push+30s-polling update behavior, the optional Balco260/EP2000 local
Modbus feature, known limitations) is drawn directly from this repo's own
`README.md`, not invented for the doc page.

Not yet submitted - `home-assistant.io` PRs are normally opened alongside or
after the `home-assistant/core` PR itself, once a reviewer has actually seen
the code.

## `home-assistant/brands` (2026-08-27)

Checked `home-assistant/brands` directly: this repo already has a real,
approved entry at `custom_integrations/bluetti/` (`icon.png`, `icon@2x.png`,
`logo.png`, `logo@2x.png`) - required for the HACS listing this integration
already has. No new artwork is needed for Core; the only remaining step is
moving those same files to `core_integrations/bluetti/`, which is normally
done as part of/alongside the actual `home-assistant/core` PR, not before it
exists.

Staged a copy of the real, existing assets (downloaded from
`home-assistant/brands` directly, not recreated) at
`brands/core_integrations/bluetti/` here, so the eventual move is a copy of
already-prepared files rather than a from-scratch brands PR.

## Modbus per-update timeout fix (2026-08-27)

A real production bug, reported from the user's own live Balco260: recurring
"Request cancelled outside library" Modbus errors, citing a different
register range each time. Traced through `pymodbus`/`modbus_connection`'s
actual source (not guessed): `async_update()` reads several register blocks
sequentially, but the surrounding `asyncio.timeout(10)` budgeted the whole
sequence, not one block - a single slow block (this device's Modbus TCP
stack is documented to become unresponsive under load) could exhaust nearly
the whole budget, cancelling whichever block came next.

Fixed in two places, since they're independent code paths:

- `bluetti_modbus_lib.modbus.client.BluettiModbusClient._update_with_timeout`
  (used by the HACS `custom_components/bluetti/` build, and by this Core
  build's `options_flow.py` connectivity check via `get_device()`) - fixed
  upstream in `bluetti-modbus`
  [PR #26](https://github.com/bluetti-community/bluetti-modbus/pull/26),
  released as `bluetti-modbus==0.1.1`. `manifest.json`'s pin bumped to
  match.
- `BluettiModbusCoordinator._update_with_timeout` here in
  `modbus_coordinator.py` - a second, independent `asyncio.timeout(10)`
  with the exact same structural flaw, since this coordinator calls
  `device.async_update()` directly via `async_get_unit()`/`get_device()`
  rather than through `BluettiModbusClient`. Bumping the pin alone would
  not have fixed this half of it.

Both widened to 30s, matching `UPDATE_INTERVAL`. Re-verified against a
fresh `home-assistant/core` dev checkout: 183 passed (182 + a new
regression test simulating a 15s-slow block), 0 failed, ruff and hassfest
clean.

## Known open question: SMeter over local Modbus (2026-08-27)

`modbus_support.py`'s `MODBUS_CAPABLE_DEV_TYPES` deliberately excludes
`smeter`, even though `bluetti_modbus_lib.devices.getter.get_device()`
supports it - the comment there assumed SMeter is a standalone accessory
that never appears as its own `UserProduct.model` in a BLUETTI cloud
account, so it could never be matched by the current cloud-binding-gated
Modbus config flow. That assumption is unverified: no diagnostics dump in
`doc/diagnostics/` includes an SMeter, and the user (who can test Balco260
against real hardware) doesn't have one to check either. If SMeter does
turn out to have its own cloud product entry, this is a small fix (add it
to `MODBUS_CAPABLE_DEV_TYPES`); if it's genuinely local-only, supporting it
would need a different UI path not gated by cloud binding - a real feature,
not a one-line fix. Left out of this submission rather than guessed at.

## What's still blocking an actual submission

Everything above is prepared and verified. What's left is entirely the act
of submitting, each a real, publicly visible action on an external repo that
this draft branch deliberately stops short of without explicit go-ahead:

- Opening the `home-assistant/core` PR itself.
- Moving the `brands/core_integrations/bluetti/` files staged here into a
  PR against `home-assistant/brands`.
- Opening the `home-assistant.io` documentation PR.
