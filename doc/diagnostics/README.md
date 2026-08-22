# Diagnostics reference samples

Anonymized diagnostics dumps, one per device model, used as reference data when adding support
for new sensors/controls - so future work doesn't need to ask a user to grab a fresh dump for
every question about a model that's already documented here.

## Contributing a new one

1. **Settings -> Devices & services -> BLUETTI**, three-dot menu (on the integration entry or the
   device page) -> **Download diagnostics**. Tokens are already redacted by the integration.
2. Before submitting a PR, strip anything not relevant to BLUETTI from the raw download: your
   `device_id`/serial number, and the `home_assistant`/`custom_components` sections (which list
   your other, unrelated HA integrations and environment details).
3. Keep just the device's `model` and its `states` array (`fn_code`/`fn_type`/`fn_value`, and
   `sensor_info` where present) - see the existing files in this folder for the format.
4. Name the file after the model, e.g. `balco260.json`, `ac200l.json`.

## Note on this Balco260 sample

Collected against integration version 1.1.0, before diagnostics started including each sensor's
`sensor_info` (added later in the same version) - so this particular file doesn't have it. Newer
contributions should include it when present.
