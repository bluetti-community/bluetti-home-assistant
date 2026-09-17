#!/usr/bin/env python3
# ruff: noqa: T201 - a command-line tool; print is its output
"""
Ask the BLUETTI cloud which firmware versions it holds for your devices.

Read-only feasibility check for firmware updates through this integration.
The BLUETTI app checks for new firmware with a "firmwareVerList" request to
the cloud and, once the user confirms, asks the cloud to send the update to
the device over MQTT (endpoints and payloads documented from the app by
https://mikemccllstr.github.io/voltkeeper/reference/firmware-updates/). This
integration's own endpoints all sit under /api/bluiotdata/ha/; the firmware
ones under /api/blusmartprod/. Whether the OAuth token this integration
holds is accepted there is the question this script answers. It sends only
the version check - it never asks for an upgrade and never downloads
firmware - and it needs nothing beyond the Python standard library.

    python3 probe_firmware_versions.py --config-entries /config/.storage/core.config_entries
    BLUETTI_ACCESS_TOKEN=... python3 probe_firmware_versions.py

The access token is the one in the integration's config entry
(data.token.access_token), which Home Assistant keeps in
.storage/core.config_entries; --config-entries reads it from a copy of that
file. Tokens expire: if the first request already answers with msgCode 803
(invalid token) or 805 (expired), reload the integration (or reconfigure
it) and copy the file again. The firmware routes sit behind the same
gateway and validate the token first (2026-09-17: an invalid token gets
803 on every one of them), so an accepted token is the whole question.

By default every component is reported to the cloud as version 0, so its
answer is simply the latest version it has for each. To also get the
hasNewVersion/currVersion the app would show, pass the installed versions
as the device page in Home Assistant prints them ("IoT v50012.01.19, ARM
v50011.01.12, DSP v50014.01.10", and "BMS v50008.01.10" on the battery):

    --ver iot=50012.01.19 --ver arm=50011.01.12 --ver dsp=50014.01.10 --ver bms=50008.01.10

The app sends a fixed per-endpoint "gwcredentials" query parameter with
these requests (constants in the app, published by voltkeeper). Whether the
gateway insists on it, and whether the token alone is enough, are part of
the question, so several variants are tried in order until one is accepted
(--all tries every one and reports each):

  1. v3 batch, gwcredentials, x-app-* headers   (what the app sends)
  2. v3 batch, gwcredentials, Authorization only
  3. v3 batch, no gwcredentials, x-app-* headers
  4. v3 batch, no gwcredentials, Authorization only
  5. v2 batch, gwcredentials, x-app-* headers
  6. v1 single-device, gwcredentials, x-app-* headers

x-app-key/x-app-ver/x-os are the headers this integration already sends on
its websocket connection, so the gateway sees the same client identity
here - not the app's.

Result on a Balco 260 on 2026-09-17: every batch variant is accepted, the
token alone included - neither gwcredentials nor the x-app-* headers are
required. The v1 single-device endpoint wants the versions as top-level
armVer/dspVer/... fields instead (msgCode 20100067 "The current version
number of ARM cannot be empty") and is not needed. With the installed
versions reported, the cloud answered with a single entry, the IoT module
(firmwareType 0) at 500120120 against the installed 500120119 - i.e. it
lists only the components it has something newer for, and leaves
currVersion/hasNewVersion null: comparing is the client's job, as in the
app. Each entry also carries a firmwareId (a record id, not the component
number), fileSize, encrypted, forcedUpdate, upgradeInstruction (empty),
creTime, upgradeRangeType and upgradeMin/MaxVersion. Run without --ver
(every component at 0) to have the cloud list its latest for all of them.

Download URLs in the cloud's answer are printed and saved with their query
string removed (it may carry a credential); --keep-urls keeps them whole.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_GATEWAY = "https://gw.bluettipower.com"
DEVICES_PATH = "/api/bluiotdata/ha/v1/devices"

# This integration's own client identity on the cloud (see const.py and the
# websocket CONNECT headers in pybluetti) - deliberately not the app's.
APP_KEY = "1A08E300701BC91B273A417414E"
APP_VER = "1.4.0"

# firmwareId values of the app's DeviceFirmware enum, for the components a
# Balco 260 reports over Modbus. Packs (PACK_BMS = 7) are queried with their
# own serial number and "masterDeviceModel", which the /devices list does
# not give - out of scope here.
FIRMWARE_IDS: dict[str, int] = {"iot": 0, "arm": 1, "dsp": 2, "bms": 3}
FIRMWARE_NAMES: dict[int, str] = {
    0: "IOT",
    1: "ARM",
    2: "DSP",
    3: "BMS",
    4: "BA",
    5: "PACK_BCU",
    6: "PACK_BMU",
    7: "PACK_BMS",
    8: "PACK_M1",
    9: "PACK_SAFETY",
    10: "PACK_HIGH_VOLTAGE",
    11: "HMI",
    13: "RF",
    14: "DC_HUB",
    15: "AC_HUB",
    16: "DC_DC",
    17: "ATS",
    18: "PANEL",
    19: "PARALLEL_BOX",
    20: "INV_DSP2",
    253: "PPS",
    254: "BOOT",
}

# Per-endpoint constants the app sends as ?gwcredentials=... (SmartProductService
# in the app; tabulated by voltkeeper, see the module docstring).
GWCREDENTIALS = {
    "batch": "osUZ8ygqt1s/awsURLTwupGKN/CH8sRRODw/lZLlrv49jdBtu7UuRqxUkYHH6jWswlLPybPJ2WShH/r928K10amSgY0pWE2+eeijxYovV9DIcRgwZhBbSQ==",
    "single": "46qdFOnnZBoUxpEDVl/MSP0RDCe0PJGdAedIYCokg793SQddlu++dMJoaFLrexKdB6Y9Tk24XbWes5rcDHasgzZGEmQ+9f2FZqH0Jrm8Ltc=",
}

# (label, path, batch?, gwcredentials key or None, app headers?)
VARIANTS: list[tuple[str, str, bool, str | None, bool]] = [
    (
        "v3 batch + gwcredentials + app headers",
        "/api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch",
        True,
        "batch",
        True,
    ),
    (
        "v3 batch + gwcredentials",
        "/api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch",
        True,
        "batch",
        False,
    ),
    (
        "v3 batch + app headers",
        "/api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch",
        True,
        None,
        True,
    ),
    (
        "v3 batch, token only",
        "/api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch",
        True,
        None,
        False,
    ),
    (
        "v2 batch + gwcredentials + app headers",
        "/api/blusmartprod/device/firmware/v2/latest/firmwareVerList/batch",
        True,
        "batch",
        True,
    ),
    (
        "v1 single + gwcredentials + app headers",
        "/api/blusmartprod/device/firmware/v1/latest/firmwareVerList",
        False,
        "single",
        True,
    ),
]


def parse_version(text: str) -> int:
    """
    '50012.01.19' -> 500120119 (major*10000 + minor*100 + patch, the
    packing bluetti-modbus's dotted_version() decodes); a bare integer is
    taken as already packed.
    """
    if text.isdigit():
        return int(text)
    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        msg = f"version must be N.NN.NN or an integer, got {text!r}"
        raise argparse.ArgumentTypeError(msg)
    major, minor, patch = (int(p) for p in parts)
    return major * 10000 + minor * 100 + patch


def parse_ver_option(text: str) -> tuple[int, int]:
    """'iot=50012.01.19' or '0=500120119' -> (firmwareId, packed version)."""
    name, sep, version = text.partition("=")
    if not sep:
        msg = f"--ver expects component=version, got {text!r}"
        raise argparse.ArgumentTypeError(msg)
    key = name.strip().lower()
    firmware_id = int(key) if key.isdigit() else FIRMWARE_IDS.get(key)
    if firmware_id is None:
        msg = f"unknown component {name!r}; use one of {sorted(FIRMWARE_IDS)} or a firmwareId"
        raise argparse.ArgumentTypeError(msg)
    return firmware_id, parse_version(version.strip())


def token_from_config_entries(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        store = json.load(fh)
    for entry in store.get("data", {}).get("entries", []):
        if entry.get("domain") == "bluetti":
            token = entry.get("data", {}).get("token", {}).get("access_token")
            if token:
                return str(token)
    msg = f"no bluetti config entry with a token in {path}"
    raise SystemExit(msg)


def strip_urls(obj: Any) -> Any:
    """Drop the query string of every *Url value, recursively."""
    if isinstance(obj, dict):
        return {
            k: (
                v.split("?", 1)[0] + ("?..." if "?" in v else "")
                if isinstance(v, str) and k.lower().endswith("url")
                else strip_urls(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [strip_urls(v) for v in obj]
    return obj


class Cloud:
    def __init__(self, gateway: str, token: str, timeout: float) -> None:
        self.gateway = gateway.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: Any = None,
        app_headers: bool = False,
    ) -> tuple[int, Any]:
        """(HTTP status, parsed JSON or raw text)."""
        url = self.gateway + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"Authorization": self.token, "Accept": "application/json"}
        if app_headers:
            headers.update({"x-os": "open", "x-app-key": APP_KEY, "x-app-ver": APP_VER})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if not url.startswith("https://"):
            msg = f"refusing a non-https gateway: {self.gateway}"
            raise SystemExit(msg)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 - https enforced just above
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            status, text = err.code, err.read().decode("utf-8", "replace")
        try:
            return status, json.loads(text)
        except ValueError:
            return status, text


def describe(status: int, payload: Any) -> str:
    if isinstance(payload, dict):
        return f"HTTP {status}, msgCode {payload.get('msgCode')!r}, msg {payload.get('msg') or payload.get('message')!r}"
    return f"HTTP {status}, non-JSON body ({len(str(payload))} chars)"


def accepted(status: int, payload: Any) -> bool:
    return status == 200 and isinstance(payload, dict) and payload.get("msgCode") == 0


def print_versions(payload: Any) -> None:
    """
    Print the DeviceFmVer entries of a firmwareVerList answer, whatever
    its shape (list of {model, sn, versions}, or a bare list of versions).
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if data is None:
        print("  (no data)")
        return
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    if isinstance(data, dict):
        data = [data]
    for item in data:
        if isinstance(item, dict) and "versions" in item:
            groups.append(
                (f"{item.get('model')} {item.get('sn')}", item.get("versions") or [])
            )
        elif isinstance(item, dict):
            groups.append(("", [item]))
    for label, versions in groups:
        if label:
            print(f"  {label}")
        if not versions:
            print("    (no firmware entries)")
        for fm in versions:
            # firmwareType is the component number; firmwareId in an answer
            # is a record id (the request uses firmwareId for the component -
            # the two are not the same thing).
            ftype = fm.get("firmwareType")
            name = (
                FIRMWARE_NAMES.get(ftype, str(ftype))
                if isinstance(ftype, int)
                else str(ftype)
            )
            print(
                f"    {name:10s} latest {fm.get('version')!s:>12}  current {fm.get('currVersion')!s:>12}"
                f"  new={fm.get('hasNewVersion')}  size={fm.get('fileSize')}  encrypted={fm.get('encrypted')}"
                f"  broadcast={fm.get('supportBroadcastUpgrade')}  strategy={fm.get('upgradeStrategy')}"
                f"  id={fm.get('firmwareId')}"
            )
            extra = {
                k: v
                for k, v in fm.items()
                if k
                not in {
                    "firmwareId",
                    "firmwareType",
                    "version",
                    "currVersion",
                    "hasNewVersion",
                    "fileSize",
                    "encrypted",
                    "supportBroadcastUpgrade",
                    "upgradeStrategy",
                    "downloadUrl",
                    "fileMd5",
                }
            }
            if extra:
                print(f"    {'':10s} also: {json.dumps(extra, ensure_ascii=False)}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1],
    )
    p.add_argument(
        "--config-entries",
        help="path to a copy of Home Assistant's .storage/core.config_entries, to read the token from",
    )
    p.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"cloud gateway base URL (default {DEFAULT_GATEWAY})",
    )
    p.add_argument(
        "--sn",
        action="append",
        help="only this device serial (repeatable; default: every device on the account)",
    )
    p.add_argument(
        "--ver",
        action="append",
        type=parse_ver_option,
        default=[],
        metavar="COMPONENT=VERSION",
        help="installed version to report, e.g. iot=50012.01.19 (default: 0 for iot, arm, dsp, bms)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="try every variant instead of stopping at the first accepted one",
    )
    p.add_argument(
        "--keep-urls",
        action="store_true",
        help="do not strip query strings from download URLs in the output",
    )
    p.add_argument(
        "--json", metavar="FILE", help="write every request/response pair to this file"
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds (default 20)",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    token = os.environ.get("BLUETTI_ACCESS_TOKEN")
    if args.config_entries:
        token = token_from_config_entries(args.config_entries)
    if not token:
        print("no token: set BLUETTI_ACCESS_TOKEN or pass --config-entries")
        return 2
    cloud = Cloud(args.gateway, token, args.timeout)
    log: list[dict[str, Any]] = []

    status, payload = cloud.request("GET", DEVICES_PATH)
    log.append({"step": "devices", "status": status, "response": payload})
    print(f"{DEVICES_PATH}: {describe(status, payload)}")
    if not accepted(status, payload):
        print(
            "the token is not accepted on the integration's own endpoint - nothing else will work; see the docstring about expired tokens"
        )
        return 1
    devices = [
        d
        for d in payload.get("data") or []
        if not args.sn or d.get("sn") in set(args.sn)
    ]
    for d in devices:
        print(
            f"  {d.get('model')!s:12s} {d.get('sn')}  online={d.get('online')}  name={d.get('name')!r}"
        )
    if not devices:
        print("no device matches")
        return 1

    versions = dict.fromkeys(FIRMWARE_IDS.values(), 0)
    versions.update(dict(args.ver))
    firmware_vers = [
        {"firmwareId": fid, "ver": ver} for fid, ver in sorted(versions.items())
    ]
    batch_body = [
        {"sn": d["sn"], "model": d.get("model"), "firmwareVers": firmware_vers}
        for d in devices
    ]
    print(
        f"\nreporting versions {', '.join(f'{FIRMWARE_NAMES[f]}={v}' for f, v in sorted(versions.items()))}"
    )

    any_ok = False
    for label, path, batch, cred, app_headers in VARIANTS:
        query = {"gwcredentials": GWCREDENTIALS[cred]} if cred else None
        bodies = (
            [batch_body]
            if batch
            else [{**entry, "mobileId": "home-assistant"} for entry in batch_body]
        )
        for body in bodies:
            status, payload = cloud.request(
                "POST", path, query=query, body=body, app_headers=app_headers
            )
            ok = accepted(status, payload)
            log.append(
                {
                    "step": label,
                    "path": path,
                    "gwcredentials": bool(cred),
                    "app_headers": app_headers,
                    "request": body,
                    "status": status,
                    "response": payload,
                }
            )
            print(f"\n[{label}] {describe(status, payload)}")
            if ok:
                any_ok = True
                print_versions(payload if args.keep_urls else strip_urls(payload))
            elif isinstance(payload, str) and payload.strip():
                print(f"  {payload.strip()[:300]}")
        if any_ok and not args.all:
            break

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                log if args.keep_urls else strip_urls(log),
                fh,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nwrote {args.json}")
    print(
        "\nresult:",
        "the firmware version check is reachable with this integration's token"
        if any_ok
        else "no variant was accepted - the firmware endpoints need something this integration does not have",
    )
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
