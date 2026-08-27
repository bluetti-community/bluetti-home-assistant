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
resolved during actual review. `ruff check` is clean on every file touched
for this Modbus rework (`modbus_coordinator.py`, `__init__.py`'s Modbus
wiring, `test_modbus_coordinator.py`, `test_init_setup.py`); the rest of the
tree (copied largely as-is from the HACS integration) still carries this
project's original, looser lint bar and has pre-existing findings - mostly
missing test docstrings (`D103`), a few blind `except Exception` clauses
(`BLE001`), and non-lowercase local variables (`N806`) - real cleanup work
before an actual submission, not something introduced by the Modbus rework.

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

## What's still blocking an actual submission

- The pre-existing ruff debt noted above, across the files not touched by
  this rework.
- A `home-assistant/brands` entry for `core_integrations/bluetti` (brands
  entries are normally added during actual PR review, not preemptively).
- `home-assistant.io` documentation, using the RC/beta doc pages for
  `fronius`, `sofar`, and `flexit` as templates.
