# BLUETTI cloud API probe for Home Assistant

*Version française : [README_fr.md](README_fr.md)*

> **A temporary diagnostic tool, not part of the integration.** It reads the integration's token from Home Assistant's storage and adds about 6 to 8 requests per minute to a cloud that is already struggling. Run it to document an outage, then stop it (section 8).

This kit measures, every minute and layer by layer, the availability of the BLUETTI cloud API that Home Assistant uses. The goal: document outages with timestamped evidence that can be compared between users.

Context: [bluetti-official/bluetti-home-assistant#183](https://github.com/bluetti-official/bluetti-home-assistant/issues/183), [bluetti-community#81](https://github.com/bluetti-community/bluetti-home-assistant/issues/81), [bluetti-community#65](https://github.com/bluetti-community/bluetti-home-assistant/issues/65), and the discussion [bluetti-community#95](https://github.com/bluetti-community/bluetti-home-assistant/discussions/95).

Probe and kit version: **1.5.3** (shown by `check` and at the top of every report). The kit includes a ready-made dashboard view (section 5.1).

---

## 1. The problem

From time to time, `GET /api/bluiotdata/ha/v1/deviceStates` on `gw.bluettipower.com` stops answering altogether: no HTTP status comes back, and the request hangs until the client times out. Meanwhile, the integration's websocket stays connected.

What is already known:

- Outage windows recur **around 15:04–15:07 UTC** (23:04 China time). They were observed on 11, 12, 13, 15 and 18 October 2026, which suggests a scheduled job on BLUETTI's side.
- Another window shows up at night, **around 02:20 UTC**. There, requests do answer, but the device comes back with no usable values.
- Commands can be accepted by the cloud (HTTP 200, `msgCode 0`) without being applied by the device. That is a separate problem, and the probe does not cover it.

The probe tells **at which stage** a request stops, and whether an outage hits everyone or only some nodes.

---

## 2. What the probe measures

Every minute, the probe runs in parallel:

| Measurement | Purpose |
|---|---|
| DNS A and AAAA through the system resolver, 1.1.1.1, 8.8.8.8 and 223.5.5.5 (AliDNS) | returned IP, CNAME chain, status (including NODATA) |
| `deviceStates` with Home Assistant's token | the failing request, identical to the integration's |
| `deviceStates` on **each IP** seen in DNS (`per_ip`) | shows whether a single node fails |
| `deviceStates` without a token | if it answers while the authenticated request hangs, the backend is failing, not the gateway |
| `devices` with the token | same service, another endpoint |
| Websocket handshake (HTTP 101 expected) | confirms the gateway itself answers |
| `deviceStates` **with** the token on `gwde.bluettipower.com` (`other_gateways_auth`) | does the backend behind `gwde` answer when the one behind `gw` doesn't? |
| `deviceStates` without a token on `gwpry.bluettipower.com` | another gateway's own answer, with no data involved |

Each request is classified by the stage where it stops:

| Stage | Meaning |
|---|---|
| `no_tcp` | no TCP connection |
| `no_tls` | TCP connected, but no TLS handshake |
| `no_first_byte` | connected, not a single byte of answer: **the symptom described in #183** |
| `body_incomplete` | the answer started but was cut |
| `answered` | complete answer |

An answer that is complete but slower than `SLOW_MS` (5,000 ms by default) is reported as **`slow`**: a degraded backend that still answers. It counts as a failure in the report.

On a network-level failure, the probe also starts a long request (up to 300 s, at most one every 30 min), to measure how long the gateway keeps the connection open. On 3 November it always ended with an nginx 504 after 120 s.

**Privacy:**
- the token is never written to the logs, and it is handed to curl through a temporary file, never on the command line;
- serial numbers are masked (`AC30…1234`);
- the logs contain no identifier and no device value, only the number of values returned.

---

## 3. Requirements

- Home Assistant OS or Supervised, with the BLUETTI integration configured and working: the probe reuses its token.
- Access to the files in `/config`, through the "Terminal & SSH", "Samba" or "Studio Code Server" add-on.

The required tools (`bash`, `curl`, `jq`, `dig`) are already in the Home Assistant container; there is nothing to install.

Files in this kit:

| File | Location |
|---|---|
| `config/bluetti-probe/bluetti-probe.sh` | `/config/bluetti-probe/bluetti-probe.sh` |
| `config/bluetti-probe/bluetti-probe.conf` | `/config/bluetti-probe/bluetti-probe.conf` |
| `config/packages/bluetti_probe.yaml` | `/config/packages/bluetti_probe.yaml` |
| `dashboard/bluetti_cloud_view.yaml` (English) or `dashboard/bluetti_cloud_view_fr.yaml` (French) | optional: pasted into a dashboard, not copied into `/config` (section 5.1) |

---

## 4. Installation

### 4.1 Copy the files

Copy the contents of the kit's `config/` folder into your `/config`. Create `/config/packages/` if it doesn't exist.

### 4.2 Enable packages

If not already done, add this to `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 4.3 Fill in the configuration

Edit `/config/bluetti-probe/bluetti-probe.conf`:

```bash
GATEWAY=""
SNS="SERIAL_NUMBER_OF_AN_ONLINE_DEVICE"
HA_CONFIG_ENTRIES="/config/.storage/core.config_entries"
```

- **`GATEWAY`**: leave it empty, and the probe uses the gateway the integration recorded for your account. A token is only honoured by its own data center. If you set it by hand (`https://gw.bluettipower.com`, `https://gwde.bluettipower.com` or `https://gwpry.bluettipower.com`), `check` warns you when it differs from the integration's.
- **`SNS`**: **one** serial number, that of an **online** device.
  - The API does not handle lists: with `SNS="A,B"`, it returns only the first device (checked on 3 November 2026). That matches the integration, which sends one request per device.
  - Why an online device: for an offline device, the cloud returns a stored state, probably through a different internal path. It could keep answering during an outage that blocks the online device.
  - To find out which one is online: after a first pass, the `devices` probe in the log lists every device of the account with its `online` field.
- **`HA_CONFIG_ENTRIES`**: leave as is. The token is re-read on every pass, so it is always current.

The other settings have sensible defaults. To lower the load on the API, set `COMPARE_GATEWAYS=""` to disable the cross-region comparison.

### 4.4 Load and check

1. Developer tools → YAML → "Check configuration".
2. Restart Home Assistant.
3. Developer tools → Actions → `shell_command.bluetti_probe_check`. Tick "Return response", then run it.
4. The last line of `stdout` must be `=> ready`.

`check` also validates `SNS` against your account's own device list (masked serials only):
- `EMPTY` or `INVALID` (space, comma, quote): fix the line in the conf file;
- `NOT FOUND`: the serial number has a typo;
- `WARNING: the two endpoints disagree`: `deviceStates` and `devices` report a different state for the device. Double-check the serial number first; if it is right, that disagreement is itself worth reporting;
- a note if the device is offline.

Then, within a minute, `sensor.bluetti_cloud_devicestates` should read `ok`.

> From the "Terminal & SSH" add-on, `docker exec` is not available: that is expected. Use the action above, which runs in the right container.

---

## 5. What the package creates

| Entity or action | Content |
|---|---|
| `sensor.bluetti_cloud_devicestates` | state: `ok`, `slow`, `empty`, `no_first_byte`, `no_tls`, `no_tcp`, `auth_error`, `http_XXX` or `msgcode_XX`; attributes: TCP/TLS/first-byte/total timings, IP, `per_ip`, DNS, state of the other probes |
| `sensor.bluetti_cloud_devicestates_response_time` | total time in ms, for graphs |
| `binary_sensor.bluetti_cloud_devicestates_problem` | `on` whenever the state is not `ok`, handy for an alert |
| `shell_command.bluetti_probe_check` | checks the installation |
| `shell_command.bluetti_probe_report` / `_report_week` | Markdown report over 24 h or 7 days |
| `script.bluetti_probe_report_24h` | shows the 24 h report in a persistent notification |

The sensor goes through the `command_line` integration, whose timeout is configurable, rather than `shell_command`, which stops everything after 60 s with no exception.

### 5.1 Dashboard view (optional)

`dashboard/bluetti_cloud_view.yaml` is a complete dashboard view built with native cards only (sections view, heading, tile, gauge, Markdown, history graph, statistics graph). No custom card or HACS frontend plugin is needed. A French version, `bluetti_cloud_view_fr.yaml`, has the same layout.

It shows:
1. **Cloud status**: a red banner only during an outage, saying since when and where the fault is (gateway answering but data service not, or the other way round), and whether `gwde` answers at the same moment; the outage and result tiles; a response-time gauge (green below 1 s, orange up to 5 s, red beyond); the result in plain words.
2. **Last pass, layer by layer**: DNS, TCP, TLS, wait for the first byte, total, plus the HTTP status, `msgCode`, BLUETTI node and DNS answer.
3. **Where is the outage?**: every request of the same pass side by side (`gw` and `gwde` with the token, the gateway without token, websocket, `gwpry`, each node), with 🟢 🟠 🔴 markers.
4. **History**: the last 24 h, and the response time over 7 days (hourly mean and max).
5. **Tools**: a button that generates the 24 h report.

To install it: open a dashboard → ✏️ → ⋮ → **Raw configuration editor**, and paste the file's content under `views:`. Or add an empty view, ⋮ → **Edit in YAML**, and replace its content with the file.

The view uses the entity IDs of a fresh install. If you installed the very first, French version of the package, the file's header lists the two IDs to replace (`…_temps_de_reponse`, `…_en_panne`).

---

## 6. Reading the results

### Normal baseline

Measured on 3 November 2026, 09:22–09:30 UTC, from France, system resolver: 9 passes, no failure.

| Probe | Median | Max |
|---|---|---|
| `deviceStates` | 195 ms | 245 ms |
| `deviceStates` without token | 157 ms | 255 ms |
| `devices` | 224 ms | 326 ms |
| without token on `gwpry` | 765 ms | 815 ms |

A normal request breaks down as: TCP about 40 ms, TLS about 100 ms, first byte about 55 ms after TLS.

### What to expect during an outage

| Observation | Likely meaning |
|---|---|
| `deviceStates` in `no_first_byte`, the token-less request `answered` | the data backend is failing, the gateway works |
| `deviceStates` and `devices` in `slow`, token-less and websocket fast | the authenticated backend is degraded, the gateway works |
| both in `no_first_byte` or `no_tls` | the gateway itself no longer answers |
| a single IP failing in `per_ip` | outage limited to one node |
| `empty` (online, 0 values) | empty answer: the night pattern seen in #81 |
| DNS `NODATA` on A | the traffic manager has no node left to offer |
| `auth_error` (msgCode 805) | the token isn't honoured by this gateway: another data center, or expired. The community integration renews it and changes data center on its own |

### First real event: 3 November 2026, 11:05–11:07 UTC

Same pass, same EU node (47.254.169.86), started at 11:05:40 UTC:

| Probe | First byte |
|---|---|
| `deviceStates` with token | **11.4 s** |
| `devices` with token | **32.8 s** (beyond the integration's 30 s timeout) |
| `deviceStates` without token | 0.14 s |
| websocket | 0.16 s |

TCP and TLS were normal everywhere. The gateway answered instantly; only the authenticated requests waited, which points at the backend behind the gateway. The next pass (11:06:40) still took 13 to 24 s. At 11:07:40 `deviceStates` was back to 156 ms while `devices` still took 14.7 s; everything was normal from 11:08:40. This lines up with the 11:06–11:08 UTC window reported on 12 October in #183.

### Second real event: 3 November 2026, from 15:03 UTC (the daily window)

From 15:03:30 UTC, and still at 18:27 when the log ended (at least 3 h 24 min), **every authenticated request to the EU node got no answer**, while on the same node token-less requests answered in 143 ms and the websocket in 154 ms. TCP and TLS stayed normal. Every long request ended with an **nginx `504 Gateway Time-out` after 120 s**, through eight different load balancer instances (`via: HTTP/1.1 SLB.n`). The data backend behind the gateway was down; the gateway, DNS and network were fine. The write-up was posted in bluetti-official#183.

### Normal quirks (not incidents)

- **AAAA in `NODATA`**: there is no IPv6 address, only the CNAME chain.
- **Websocket closed with code 1002 and "Server internal error"** right after the handshake: the probe does not speak the STOMP protocol that follows, so the server closes. This happens every time. A different close code during an incident, on the other hand, is worth noting.
- **`msgCode 801`** on token-less requests: "missing access token", as intended.
- **AliDNS (223.5.5.5) slow or silent** from Europe: noise, with no effect on Home Assistant.
- **`wrong_datacenter` in `per_ip`** (`msgCode 805`, "please log in") on the node of another continent: a token is only valid in its account's data center. See below.

### DNS does not send everyone to the same place

`gw.bluettipower.com` is a CNAME to `gtm-apigw.bluetti.ltd.`, a global traffic manager. On 3 November, the system resolver, 8.8.8.8 and AliDNS returned **47.254.169.86** (the EU node), while 1.1.1.1 twice returned **47.253.45.39** (the US node). Cloudflare probably does not forward the client's location, so the traffic manager picks the wrong continent.

About the "DNS redirect from `gw` to `gwde`" tip: a DNS rewrite only changes the IP the name resolves to; the request still says `gw.bluettipower.com`. For EU users whose resolver already returns 47.254.169.86 for `gw`, it changes nothing. It does help users whose resolver sent `gw` to the US node (which rejects EU tokens with `805` and is slower). Whether the backend behind the **name** `gwde` survives the daily window is what `other_gateways_auth` measures.

`gwpry.bluettipower.com` is **not** that US node: on 6 November it resolved to 139.95.6.229. Reports in community issues #65 and #92 show EU accounts getting `msgCode 0` from it, with the device `online=0` and SOC 0 or no data (#90). So don't set up an EU account on it, and don't add it to `AUTH_COMPARE_GATEWAYS`: the probe would report that placeholder as `ok`.

Two users can therefore talk to different nodes depending on their DNS resolver. And it matters: on 3 November, the US node rejected an EU account's token **every time** (35 out of 35 requests) with `msgCode 805`, the same code as an expired token. A Home Assistant whose resolver sends `gw` to the wrong continent would therefore see "expired token" errors that have nothing to do with the token. This is a plausible mechanism behind the 805 rejections of European accounts on `gw` that the community integration worked around in 1.5.0 by using each account's own data center (`gwde` for Europe); `gwde` always resolved to the EU node here.

---

## 7. Producing and sharing a report

After a period that covers **15:00–16:30 UTC**:

- run the "BLUETTI probe report (24 h)" script; the report appears in the notifications;
- or the `shell_command.bluetti_probe_report` action (or `_report_week`), with "Return response" ticked.

The report contains:
- the probe version and gateway;
- the table of failure windows, in UTC;
- the state of the other probes during those windows;
- the actual hang duration, measured by the long requests.

**To paste a report into GitHub, copy it from the file, not from the action response.** Developer tools show action responses as YAML, which wraps long lines and adds blank lines, and that breaks the Markdown tables. Every report is also saved as `/config/bluetti-probe/logs/report-last-1d.md` (or `-7d.md`): open it with the File editor, Studio Code Server or Samba, and copy it as is. The 7-day report can take a while on slow hardware; Home Assistant stops a `shell_command` after 60 s.

Raw logs are in `/config/bluetti-probe/logs/`: one JSONL file per day, compressed from the next day on, kept 7 days.

### So that reports can be compared, add this to yours

```text
Country / ISP         :
HA's DNS resolver     : (router, Pi-hole, 1.1.1.1, …)
Node IP seen          : (remote_ip attribute, e.g. 47.254.169.86)
Gateway (GATEWAY)     : gw / gwde / gwpry
Account region        : EU / US / other
Device models         :
HA version            :
Integration version   : (official or community, version number)
Period covered (UTC)  :
```

Post it in [discussion #95](https://github.com/bluetti-community/bluetti-home-assistant/discussions/95).

**Never share:** the contents of `core.config_entries`, your token, or full serial numbers.

---

## 8. Limits and precautions

- **Load on the API**: the probe adds about 6 to 8 requests per minute on top of the integration's polls. Stop it when the investigation is over, by commenting out the `command_line` block of the package.
- **Backups**: about 8 MB of logs per day, roughly ten times less once compressed. With a 7-day retention, expect about 15 MB in `/config`, hence in every Home Assistant backup.
- **Database**: the sensor changes every minute, about 1,440 states per day. You can exclude it from the recorder if needed.
- **Home Assistant downtime**: the probe measures nothing during a restart. The same script also runs on a separate Linux machine (LXC, VPS) with `bluetti-probe.sh install` and a systemd timer. You then have to provide the token in a file (`TOKEN_FILE`) and renew it by hand, as it expires.
- **Token**: never use the `refresh_token` in the probe. You would rotate Home Assistant's token behind its back.
- The probe observes; it fixes nothing. The outages themselves are BLUETTI's to fix.
