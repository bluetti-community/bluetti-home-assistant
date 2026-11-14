# BLUETTI cloud outages

This integration only reaches your devices through the BLUETTI cloud. When the cloud stops answering, entities keep their last values for two failed polls, then go unavailable, and recover on their own once it answers again. Signing in again does not help during an outage.

Measurements behind this page: [discussion #95](https://github.com/bluetti-community/bluetti-home-assistant/discussions/95).

## What an outage looks like

Outages have been measured from Europe on the European node. They hit BLUETTI's data service, not your network or the gateway:

| Request | During an outage |
|---|---|
| Device data, with the account's token | No answer, or an answer after many seconds |
| The same request without a token (answered by the gateway alone) | Normal |
| Websocket handshake | Normal |
| DNS, TCP, TLS | Normal |

- **When:** the longest outages start around 15:00 UTC, on most days, and can last several hours. Shorter ones happen at other times.
- **In Home Assistant:** the **Cloud Last Result** entity shows `timeout`, and **Download diagnostics** lists the failure windows in UTC. See [Cloud health entities](../README.md#cloud-health-entities).
- **At night:** for a few minutes, the cloud can also report a device as online with every reading at 0, or as offline. **Cloud Last Result** shows `no_readings` when the reply says online.

To report an outage, attach the diagnostics file and give the times in UTC. Responses carry no request id, so times are all BLUETTI can match with its logs.

To measure an outage layer by layer, there is a temporary [probe](../tools/cloud-probe/README.md). You don't need it for a normal report.

## Data centers

The cloud has several gateways. The integration finds the one that serves your account when you sign in, and again if the recorded one starts rejecting a fresh token. You should not need to choose one.

| Gateway | Role |
|---|---|
| `gw.bluettipower.com` | Default. A traffic manager sends this name to one node or another, depending on your DNS resolver. |
| `gwde.bluettipower.com` | European gateway. |
| `gwpry.bluettipower.com` | The gateway the integration uses for US accounts. |

- **A token is only honoured by its own data center.** Another one answers code 805, the same code as an expired token. A resolver that sends `gw` to another continent can therefore cause "expired token" errors unrelated to the token. Changing DNS does not help during an outage.
- **`gwpry` also answers accounts it does not hold.** European accounts have received code 0 from it with the device offline and SOC 0, or no data at all ([#90](https://github.com/bluetti-community/bluetti-home-assistant/issues/90)). Do not point a European account at it: a successful connection there does not mean your data is there. `gwpry` has not been confirmed yet on an account it really holds.
- **A manual change to `application.yaml`** is overwritten by the next update.

## Token codes

The gateways answer these with HTTP 200, the verdict only in the body:

| Code | Meaning |
|---|---|
| 801 | No token. |
| 803 | The token fails verification. |
| 805 | The token is not honoured: expired, or issued for an account another data center holds. |

The integration handles all three by renewing the token first, and only asks you to sign in if that fails. Only 805 makes it look for another data center.
