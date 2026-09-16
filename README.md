# BLUETTI Integration for Home Assistant (community fork)

[🇨🇳 简体中文](./README_zh.md) | [🇩🇪 German](./README_de.md) | [🇫🇷 Français](./README_fr.md) | [🇬🇧 English](./README.md) | 
[🇳🇱 Dutch](./README_nl.md) | [🇺🇦 Ukrainian](./README_uk.md)

This is the **community-maintained fork** of BLUETTI's official Home Assistant
integration, [bluetti-official/bluetti-home-assistant](https://github.com/bluetti-official/bluetti-home-assistant).
It connects your BLUETTI power stations to Home Assistant through the BLUETTI
cloud service (account login, real-time push updates), exactly like the official
one - and adds what the community needs sooner than the official release cycle
delivers it: bug fixes as they are found, plus an optional **local Modbus TCP**
connection for Balco 260 and EP2000 (see [How Data Is Updated](#-how-data-is-updated)).

It is a drop-in replacement: same `bluetti` integration domain, so your existing
configuration entry, devices and entities carry over as they are. It shows up as
**BLUETTI (community)** in HACS and in Home Assistant, to tell it apart from the
official one.

> [!IMPORTANT]
> Install **either** this fork **or** the official integration, not both: they
> install into the same `custom_components/bluetti` folder, and whichever HACS
> updates last silently overwrites the other.

## ✨ Features

- ✅ Power Switch
- ✅ Inverter Status
- ✅ Battery state of charge (SOC)
- ✅ AC Switch
- ✅ DC Switch
- ✅ Main unit power switch
- ✅ AC ECO
- ✅ DC ECO
- ✅ Work mode switch: Backup, Self-consumption, Peak and Off-Peak
- ✅ Sleep Mode
- ✅ PV Input Power
- ✅ Grid Input Power
- ✅ AC Ouput Power
- ✅ DC Ouput Power

## 💡 Use Cases

- **Monitor your power station from anywhere** — battery level, inverter
  status and input/output power show up as regular Home Assistant sensors,
  so they work in dashboards, history graphs and the mobile app just like
  any other device.
- **Automate charging and discharging** — trigger automations based on
  battery state of charge (e.g. stop charging above 90%, send an alert
  below 20%).
- **Control AC/DC outputs remotely** — turn the power station's outputs on
  or off from Home Assistant, a script, or voice assistants integrated with
  Home Assistant.
- **Combine with energy dashboards** — use the power sensors (PV input,
  grid input, AC/DC output) alongside Home Assistant's Energy dashboard to
  track solar production and consumption.
- **React to grid/power events** — build automations that respond to the
  inverter or work-mode state, for example switching to backup mode when a
  power outage is detected elsewhere in your setup.

## 🎮 Power Station Support List

> [!NOTE]
>
> More power station models will be added in the future.

|     Power Station Model      |             Buesiness Name              | Inverter Status | Battery SOC | AC Switch | DC Switch | power switch | AC ECO | DC ECO | Work mode switch | Sleep Mode | PV Input Power | Grid Input Power | AC Output Power | DC Output Power | 
|:----------------------------:|:---------------------------------------:|:---------------:|:-----------:|:---------:|:---------:|:------------:|:------:|:------:|:----------------:|:----------:|:--------------:|:----------------:|:---------------:|:---------------:|
|            AP300             |                Apex 300                 |                 |      ✅      |     ✅     |           |             |   ✅    |        |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|            EL300             |           Elite 300,AORA 300            |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|        EL320,AORA320         |           Elite 320,AORA 320            |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|            EL400             |                Elite 400                |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|            EP13K             |                  EP13k                  |        ✅        |      ✅      |           |           |      ✅      |        |        |        ✅         |            |                |                  |                 |                 |
|            EP2000            |                  EP200                  |        ✅        |      ✅      |           |           |      ✅      |        |        |        ✅         |            |                |                  |                 |                 |
|             EP6K             |                  EP6k                   |        ✅        |      ✅      |           |           |      ✅      |        |        |        ✅         |            |                |                  |                 |                 |
|            EP760             |                  EP760                  |        ✅        |      ✅      |           |           |      ✅      |        |        |                  |            |                |                  |                 |                 |
|           EP500Pro           |                EP500Pro                 |                 |      ✅      |     ✅     |      ✅     |             |        |        |        ✅         |            |       ✅        |        ✅         |        ✅        |        ✅        |
|              FP              |             Fridge Product              |        ✅        |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |                |                  |                 |                 |
|  PR100V2,EL100V2,AORA100V2   | Premium 100 V2,Elite 100 V2,AORA 100 V2 |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
| PR200V2,Elite 200 V2,AORA200 | Premium 200 V2,Elite 200 V2,AORA 200 V2 |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|        PR30V2,EL30V2         |  Premium 30 V2,Elite 30 V2,AORA 30 V2   |                 |      ✅      |     ✅     |     ✅     |             |   ✅    |   ✅    |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|             RV5              |                   RV5                   |        ✅        |      ✅      |     ✅     |     ✅     |             |        |        |        ✅         |     ✅      |       ✅        |        ✅         |        ✅        |        ✅        |
|      Balco260,Balco500       |            Balco260,Balco500            |        ✅        |      ✅      |     ✅     |           |             |        |        |        ✅         |            |       ✅        |        ✅         |        ✅        |                 |
|         AC300,AC500          |               AC300,AC500               |                 |      ✅      |     ✅     |      ✅     |             |        |        |        ✅         |            |       ✅        |        ✅         |        ✅        |        ✅        |
|        AC200PL,AC200L        |             AC200PL,AC200L              |                 |      ✅      |     ✅     |      ✅     |             |   ✅    |   ✅    |        ✅         |            |       ✅        |        ✅         |        ✅        |        ✅        |


## 📦 Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bluetti-community&repository=bluetti-home-assistant&category=integration)

_or manually:_

1. [Install HACS](https://hacs.xyz/docs/setup/download) if you don't have it yet.
2. In HACS, open the **⋮** menu → **Custom repositories**.
3. Add `https://github.com/bluetti-community/bluetti-home-assistant` with category
   **Integration**.
4. Find **BLUETTI (community)** in HACS and install it.
5. **Restart Home Assistant.**

Coming from the official integration? Remove **BLUETTI** (the official one) from
HACS first, then install this one - the removal deletes the shared
`custom_components/bluetti` folder, and the install puts this fork's copy in its
place. Your configuration entry and entities are kept.

### Manually

1. Download `bluetti.zip` from the
   [latest release](https://github.com/bluetti-community/bluetti-home-assistant/releases/latest)
   and extract it into your Home Assistant configuration's
   `custom_components/bluetti/` directory (replacing that folder if it exists).
2. Restart Home Assistant.

## ⚙️ Integration configuration

1. Follow the steps "Settings -> Devices & services", click to enter the
   `Integration List` page.

   <img src="./doc/images/1-setting_devices_and_services.png" width="880">

2. Click the "Add Integration" button, then search for the brand keyword
   `bluetti`; select the **BLUETTI (community)** integration to proceed with the
   OAUTH authorization login.

   <img src="./doc/images/2-search_and_add_integration.png" width="880">

3. You must agree that `Home Assistant` can access your BLUETTI account and
   establish a connection with the BLUETTI cloud service.

   <img src="./doc/images/3-oauth_agree_to_connect_with_bluetti.png">

4. Enter your BLUETTI account to authorize and login.

   <img src="./doc/images/4-oauth_enter_bluetti_account.png">

5. You must agree that `Home Assistant` link to your BLUETTI account.

   <img src="./doc/images/5-oauth_link_account_to_ha.png">

6. Select your BLUETTI power station devices that need to be used and managed in
   Home Assistant.

   <img src="./doc/images/6-choose_bluetti_devices.png" width="880">
   <img src="./doc/images/7-bluetti_device_in_ha.png" width="880">

## 🔄 How Data Is Updated

This integration is cloud-based by default: it talks to the BLUETTI cloud
service, not directly to your power station over the local network.

- **Push updates**: the integration keeps a WebSocket connection open to the
  BLUETTI cloud. When your power station reports a change (e.g. you toggle
  a switch in the official BLUETTI app), Home Assistant is notified and
  refreshes that device's entities within a few seconds.
- **Polling fallback**: independently of push updates, each device is also
  polled every 30 seconds. This guarantees entities stay up to date even if
  a push notification is missed.
- **Availability**: if the BLUETTI cloud is unreachable or your account's
  authorization expires, affected entities are marked `unavailable` in Home
  Assistant rather than showing stale data.

### Optional: local Modbus for Balco260 / EP2000

Balco260 and EP2000 also expose a local Modbus TCP interface, in addition to
the cloud API. For these models, once the device is enabled in this
integration, go to **Settings -> Devices & services -> BLUETTI -> Configure**
and choose **Configure local Modbus** to add the device's IP address and
port. This is entirely optional and additive:

- It surfaces data the cloud API doesn't report (real battery
  charge/discharge energy, cycle count, per-string PV data), as extra
  sensors on the same device.
- It does not replace the cloud connection - if the local Modbus connection
  drops, only those extra sensors go `unavailable`; the device's normal
  cloud-sourced entities and controls keep working.
- It is polled every 30 seconds, matching the cloud path. Bluetti's Modbus
  TCP stack is known to become unresponsive under connection/polling
  pressure, so this integration deliberately keeps one persistent
  connection per device rather than reconnecting on every poll.

## 🧩 Example Automations

Replace `sensor.xxx_battery_level` / `switch.xxx_ac_output` with the actual
entity IDs created for your device (visible on the device page under
**Settings -> Devices & services -> BLUETTI**).

**Notify when the battery is low:**

```yaml
automation:
  - alias: "BLUETTI: notify on low battery"
    trigger:
      - platform: numeric_state
        entity_id: sensor.xxx_battery_level
        below: 20
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "BLUETTI power station battery is below 20%."
```

**Turn off the AC output at night:**

```yaml
automation:
  - alias: "BLUETTI: turn off AC output at night"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.xxx_ac_output
```

## 🗑️ Removing the Integration

1. Go to **Settings -> Devices & services**, open the **BLUETTI (community)**
   integration card, click the three-dot menu on the integration entry and select
   **Delete**. This removes the config entry, its devices and entities from
   `Home Assistant`.

2. Remove the integration files:

   - **Installed via HACS**: go to **HACS -> Integrations**, open
     **BLUETTI (community)**, and select **Remove**.
   - **Installed manually**: delete the `custom_components/bluetti` folder
     from your `Home Assistant` configuration directory.

3. Restart `Home Assistant` to complete the removal.

4. (Optional) If you no longer want `Home Assistant` to have access to your
   BLUETTI account, revoke it from your BLUETTI account's connected-apps
   settings.

## ❓ Frequently Asked Questions (FAQ)

### Not found `BLUETTI Integration` after installation?

Please check whether the `custom_components` path is correct and confirm whether
the `Home Assistant` system has been restarted.

### Always offline or failed connect to BLUETTI server?

Please check the **network**, **ports** and **firewall** to ensure that
`Home Assistant` can access the power station devices.

### How to update the integration?

Through HACS, like any other HACS integration: it shows the new version as an
available update. Installed manually? Replace the `custom_components/bluetti/`
folder with the one from the
[latest release](https://github.com/bluetti-community/bluetti-home-assistant/releases/latest)
and restart Home Assistant.

## ⚠️ Known Limitations

- **Cloud-dependent by default**: this integration relies on the BLUETTI
  cloud service (OAuth2 login + WebSocket push), and stops updating if
  BLUETTI's cloud service is unreachable. Balco260 and EP2000 can
  additionally be configured with a local Modbus connection (see "How Data
  Is Updated" above) for the data the cloud API doesn't report, but this is
  optional and supplementary, not a replacement for the cloud connection.
- **One BLUETTI account per Home Assistant install**: all devices from a
  given BLUETTI account are grouped under a single integration entry. If
  you have devices on multiple BLUETTI accounts, only the most recently
  authenticated account's devices merge into that entry.
- **Newly bound devices require a manual step**: after binding a new device
  to your BLUETTI account, use **Settings -> Devices & services -> BLUETTI
  -> Configure** to add it — it is not picked up automatically.
- **Sensor coverage varies by model**: not every fn_code/sensor reported by
  every power station model is mapped to a Home Assistant entity yet. If a
  sensor is missing for your model, please open an issue.
- **Balco260 self-consumption mode** needs the electricity meter connected
  to report correctly.

## 📮 Support & Feedback

💬 Have any problems or suggestions? Create an issue on GitHub:
[https://github.com/bluetti-community/bluetti-home-assistant/issues](https://github.com/bluetti-community/bluetti-home-assistant/issues)

This fork is maintained by the community, not by BLUETTI. Anything about the
official integration itself belongs on its own tracker,
[bluetti-official/bluetti-home-assistant](https://github.com/bluetti-official/bluetti-home-assistant/issues).

Want to contribute code? See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a dev
environment and submit a pull request.
