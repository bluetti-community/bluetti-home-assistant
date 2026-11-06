#!/usr/bin/env bash
# bluetti-probe.sh - timestamped network probe for the BLUETTI cloud API used
# by Home Assistant (gw.bluettipower.com), to document outages of
# GET /api/bluiotdata/ha/v1/deviceStates layer by layer:
# DNS -> TCP -> TLS -> first byte -> HTTP status -> API msgCode.
#
# Usage:
#   bluetti-probe.sh run              one measurement pass (run every minute)
#   bluetti-probe.sh report [days]    summary of failure windows (default: 1 day),
#                                     also saved to $OUT_DIR/report-last-<days>d.md
#   bluetti-probe.sh install          install config, systemd service and timer
#   bluetti-probe.sh check            check dependencies, config and token
#   bluetti-probe.sh summary          one pass, then the state as JSON on stdout
#                                     (Home Assistant command_line sensor)
#
# Runs on Debian/Ubuntu (LXC) and inside the Home Assistant container
# (Alpine: bash, curl, jq and dig are provided; the rest is BusyBox).
#
# Output: one JSON line per measurement in $OUT_DIR/probe-YYYY-MM-DD.jsonl (UTC).
# The token is never written to the logs; serial numbers are masked.

set -uo pipefail

PROBE_VERSION="1.5.3"

# Config: $BLUETTI_PROBE_CONF, else bluetti-probe.conf next to the script,
# else /etc/bluetti-probe.conf.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${BLUETTI_PROBE_CONF:-}" ]]; then CONF_FILE="$BLUETTI_PROBE_CONF"
elif [[ -r "$SCRIPT_DIR/bluetti-probe.conf" ]]; then CONF_FILE="$SCRIPT_DIR/bluetti-probe.conf"
else CONF_FILE="/etc/bluetti-probe.conf"; fi

# --- Defaults (overridden by $CONF_FILE) -------------------------------------
GATEWAY="https://gw.bluettipower.com"          # the account's gateway
COMPARE_GATEWAYS="https://gwde.bluettipower.com https://gwpry.bluettipower.com"
# Gateways queried WITH the token (deviceStates for SNS). A token-less request
# is answered by the gateway alone, so it says nothing about the data backend.
# gw and gwde resolve to the same IP for EU users, but the front end may route
# by host name to different backends: only an authenticated request tells.
AUTH_COMPARE_GATEWAYS="https://gwde.bluettipower.com"
WS_PATH="/api/edgeiotgw/ws-coordination"
SNS=""                                          # ONE serial number (the API reads only the first)
TOKEN_FILE=""                                   # file holding only the access_token
HA_CONFIG_ENTRIES=""                            # OR path to .storage/core.config_entries
OUT_DIR="/var/log/bluetti-probe"
MAX_TIME=55                                     # s, each request of a normal pass
CONNECT_TIMEOUT=15                              # s, TCP connection setup
DNS_SERVERS="system 1.1.1.1 8.8.8.8 223.5.5.5"  # 223.5.5.5 = AliDNS (BLUETTI's host)
# 1 = also query deviceStates on EACH IP returned by any resolver
# (curl --resolve): BLUETTI's DNS traffic manager does not always point to the
# same node (e.g. 1.1.1.1 -> 47.253.45.39 instead of 47.254.169.86).
PIN_ALL_IPS=1
# An answer slower than this (ms) counts as "slow": a degraded backend that
# still answers. Observed on 3 Nov 2026, 11:05-11:07 UTC: 11-33 s to the first
# byte for authenticated requests, while token-less ones took 0.14 s.
SLOW_MS=5000
LONG_PROBE_MAX_TIME=600                         # s, long request started on failure
# At most one long request per this many seconds. Its answer is known by now:
# the gateway gives up with an nginx 504 after 120 s.
LONG_PROBE_MIN_INTERVAL=1800
MTR_ON_FAILURE=1                                # 1 = TCP/443 mtr on failure (if installed)
MTR_MIN_INTERVAL=600                            # s between two mtr runs
RETENTION_DAYS=30
COMPRESS_OLD=1                                  # 1 = gzip the logs of past days
USER_AGENT="bluetti-probe/$PROBE_VERSION"

# shellcheck source=/dev/null
[[ -r "$CONF_FILE" ]] && . "$CONF_FILE"

STATE_DIR="$OUT_DIR/.state"

# The gateway the integration recorded for this account. A token is only
# honoured by its own data center, so probing another one measures nothing
# but a rejection (msgCode 805).
integration_gateway() {
  [[ -n "$HA_CONFIG_ENTRIES" && -r "$HA_CONFIG_ENTRIES" ]] || return 0
  case "$(jq -r '[.data.entries[] | select(.domain=="bluetti") | .data.gateway // "global"][0] // empty' \
          "$HA_CONFIG_ENTRIES" 2>/dev/null)" in
    global) printf 'https://gw.bluettipower.com' ;;
    eu)     printf 'https://gwde.bluettipower.com' ;;
    us)     printf 'https://gwpry.bluettipower.com' ;;
  esac
}
INTEGRATION_GATEWAY="$(integration_gateway)"
# An empty GATEWAY follows the integration.
[[ -z "$GATEWAY" ]] && GATEWAY="${INTEGRATION_GATEWAY:-https://gw.bluettipower.com}"

# UTC timestamp to the millisecond without `date +%N` (missing in BusyBox):
# $EPOCHREALTIME is provided by bash >= 5.
now_utc() {
  local e="${EPOCHREALTIME:-$(date +%s).000}" ms
  e="${e/,/.}"; ms="${e#*.}000"
  TZ=UTC printf '%(%Y-%m-%dT%H:%M:%S)T.%sZ' "${e%.*}" "${ms:0:3}"
}
day_utc() { TZ=UTC printf '%(%Y-%m-%d)T' "${1:--1}"; }
log_file() { printf '%s/probe-%s.jsonl' "$OUT_DIR" "$(day_utc)"; }
host_of() { local h="${1#*://}"; printf '%s' "${h%%/*}"; }
die() { echo "bluetti-probe: $*" >&2; exit 1; }

# Atomically append one or more lines to today's log.
append() {
  local f; f="$(log_file)"
  { flock -x 9; cat >>"$f"; } 9>>"$f.lock"
}

# Mask a serial number: AC3000000000001234 -> AC30…1234
mask_sn() { local s="$1"; ((${#s} > 8)) && printf '%s…%s' "${s:0:4}" "${s: -4}" || printf '%s' "$s"; }

get_token() {
  local t=""
  if [[ -n "$TOKEN_FILE" && -r "$TOKEN_FILE" ]]; then
    t="$(tr -d ' \t\r\n' <"$TOKEN_FILE")"
  elif [[ -n "$HA_CONFIG_ENTRIES" && -r "$HA_CONFIG_ENTRIES" ]]; then
    # Token re-read on every pass: Home Assistant renews it itself.
    t="$(jq -r '[.data.entries[] | select(.domain=="bluetti") | .data.token.access_token][0] // empty' \
         "$HA_CONFIG_ENTRIES" 2>/dev/null)"
  fi
  printf '%s' "$t"
}

# --- DNS ---------------------------------------------------------------------
# Record the status (NOERROR/NXDOMAIN/SERVFAIL) and the answer for A and AAAA,
# with the CNAME chain, for each resolver. NOERROR without a record of the
# queried type = NODATA (seen in bluetti-community#65).
dns_probe() {
  local run="$1" host="$2" server="$3" qtype="$4" ts out status answer qtime at=""
  ts="$(now_utc)"
  [[ "$server" != system ]] && at="@$server"
  out="$(dig $at +time=5 +tries=1 +noall +comments +answer +stats "$host" "$qtype" 2>&1)"
  status="$(sed -n 's/.*status: \([A-Z]*\).*/\1/p' <<<"$out" | head -1)"
  [[ -z "$status" ]] && status="NO_RESPONSE"
  answer="$(awk '$0 !~ /^;/ && NF>=5 {print $4" "$5}' <<<"$out" | paste -sd ',' -)"
  qtime="$(sed -n 's/^;; Query time: \([0-9]*\) msec.*/\1/p' <<<"$out" | head -1)"
  # NODATA = NOERROR without a record of the queried type, even when the CNAME
  # chain is present (real case: AAAA of gw.bluettipower.com).
  [[ "$status" == NOERROR ]] && ! grep -q "^$qtype " <<<"${answer//,/$'\n'}" && status="NODATA"
  jq -cn --arg ts "$ts" --arg run "$run" --arg host "$host" --arg server "$server" \
        --arg qtype "$qtype" --arg status "$status" --arg answer "$answer" --arg qtime "${qtime:-}" \
    '{ts:$ts, run:$run, kind:"dns", host:$host, resolver:$server, qtype:$qtype,
      status:$status, answer:($answer|split(",")|map(select(.!=""))),
      query_ms:($qtime|tonumber? // null)}'
}

# --- HTTP --------------------------------------------------------------------
# curl -w '%{json}' gives every timing: namelookup, connect (TCP),
# appconnect (TLS), starttransfer (first byte), total. Exit 28 = curl timeout.
http_probe() {
  local run="$1" name="$2" url="$3" auth="$4" maxtime="$5"; shift 5
  local tmp body hdr wjson rc ts token
  tmp="$(mktemp -d)"; body="$tmp/body"; hdr="$tmp/hdr"
  ts="$(now_utc)"
  local args=(-sS --http1.1 -o "$body" -D "$hdr" -A "$USER_AGENT"
              --connect-timeout "$CONNECT_TIMEOUT" --max-time "$maxtime" -w '%{json}')
  if [[ "$auth" == 1 ]]; then
    token="$(get_token)"
    [[ -z "$token" ]] && { rm -rf "$tmp"; return 0; }
    # Token passed through a header file so it never shows in `ps`.
    printf 'Authorization: %s\n' "$token" >"$tmp/auth"; chmod 600 "$tmp/auth"
    args+=(-H "@$tmp/auth")
  fi
  wjson="$(curl "${args[@]}" "$@" "$url" 2>"$tmp/err")"; rc=$?
  [[ -z "$wjson" || "${wjson:0:1}" != "{" ]] && wjson='{}'

  # Useful response headers (request ids, server, retry-after…)
  local headers
  headers="$(tr -d '\r' <"$hdr" 2>/dev/null \
    | grep -iE '^(server|date|via|x-[a-z0-9-]*(id|trace|request)[a-z0-9-]*|eagleeye-traceid|retry-after|content-type|upgrade|connection):' \
    | jq -R 'capture("^(?<k>[^:]+):\\s*(?<v>.*)$") | {(.k|ascii_downcase): .v}' 2>/dev/null \
    | jq -cs 'add // {}')"
  [[ -z "$headers" ]] && headers='{}'

  # Body summary: msgCode and, for deviceStates, each device's state
  # (online, number of values) - catches "empty" answers.
  local app='{}'
  if [[ -s "$body" ]] && jq -e . "$body" >/dev/null 2>&1; then
    app="$(jq -c '{msgCode, message,
      devices: (if (.data|type)=="array" then
                  [.data[] | {sn: (.sn // "" | tostring), online,
                              values: ((.stateList // []) | length)}]
                else null end)}' "$body" 2>/dev/null || echo '{}')"
    # mask serial numbers
    app="$(jq -c '.devices |= (if . then map(.sn |= (if length>8 then .[0:4]+"…"+.[-4:] else . end)) else . end)' <<<"$app")"
  elif [[ -s "$body" ]] && [[ "$(od -An -tu1 -N1 "$body" | tr -d ' ')" == 136 ]]; then
    # Websocket close frame (0x88): 2-byte code, then the reason.
    local b; read -r _ _ b1 b2 _ < <(od -An -tu1 -N4 "$body")
    b="$(tail -c +5 "$body" | head -c 120 | tr -d '\000-\037')"
    app="$(jq -cn --argjson c "$(( b1 * 256 + b2 ))" --arg r "$b" '{ws_close_code:$c, ws_close_reason:$r}')"
  elif [[ -s "$body" ]]; then
    app="$(head -c 200 "$body" | tr -d '\000-\037' | jq -Rc '{body_head: .}')"
  fi

  local err; err="$(head -c 300 "$tmp/err" | tr '\n' ' ')"
  jq -cn --arg ts "$ts" --arg run "$run" --arg name "$name" --arg host "$(host_of "$url")" \
        --argjson rc "$rc" --arg err "$err" --argjson w "$wjson" \
        --argjson h "$headers" --argjson app "$app" --arg maxtime "$maxtime" '
    {ts:$ts, run:$run, kind:"http", probe:$name, host:$host, max_time:($maxtime|tonumber),
     curl_exit:$rc, curl_error:(if $err=="" then null else $err end),
     http_code:($w.http_code // 0), http_version:($w.http_version // null),
     remote_ip:($w.remote_ip // null), remote_port:($w.remote_port // null),
     t_dns:($w.time_namelookup // null), t_tcp:($w.time_connect // null),
     t_tls:($w.time_appconnect // null), t_first_byte:($w.time_starttransfer // null),
     t_total:($w.time_total // null), size_download:($w.size_download // null),
     ssl_verify:($w.ssl_verify_result // null),
     stage:( if $rc==0 then "answered"
             elif ($w.time_connect // 0)==0 then "no_tcp"
             elif (($w.scheme // "https")|ascii_downcase)=="https"
                  and ($w.time_appconnect // 0)==0 then "no_tls"
             elif ($w.time_starttransfer // 0)==0 then "no_first_byte"
             else "body_incomplete" end),
     headers:$h} + $app'
  rm -rf "$tmp"
}

# Websocket handshake (HTTP 101 expected). Cut after 8 s: all that matters is
# whether the gateway answers the upgrade.
ws_probe() {
  local run="$1" key; key="$(head -c 16 /dev/urandom | base64)"
  http_probe "$run" ws_upgrade "$GATEWAY$WS_PATH" 1 8 \
    -H "Connection: Upgrade" -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: $key" \
    | jq -c 'if .http_code==101 then .stage="answered" | .curl_exit_note="101 received, cut on purpose" else . end'
}

# TCP/443 traceroute on failure, at most one every MTR_MIN_INTERVAL s.
maybe_mtr() {
  local run="$1" host="$2" stamp="$STATE_DIR/last_mtr" now last=0
  [[ "$MTR_ON_FAILURE" == 1 ]] && command -v mtr >/dev/null || return 0
  now="$(date +%s)"; [[ -r "$stamp" ]] && last="$(cat "$stamp")"
  (( now - last < MTR_MIN_INTERVAL )) && return 0
  echo "$now" >"$stamp"
  local ts out; ts="$(now_utc)"
  out="$(mtr -rwzbc 10 -T -P 443 "$host" 2>&1 | head -60)"
  jq -cn --arg ts "$ts" --arg run "$run" --arg host "$host" --arg out "$out" \
    '{ts:$ts, run:$run, kind:"mtr", host:$host, report:($out|split("\n"))}' | append
}

# Detached long request: measures how long the gateway holds the connection
# before a 504 or a reset. One at a time.
maybe_long_probe() {
  local run="$1" url="$2"
  # 0 = disabled (for curl, --max-time 0 would mean "no limit")
  (( LONG_PROBE_MAX_TIME > 0 )) || return 0
  local stamp="$STATE_DIR/last_long_probe" now last=0
  now="$(date +%s)"; [[ -r "$stamp" ]] && last="$(cat "$stamp")"
  (( now - last < LONG_PROBE_MIN_INTERVAL )) && return 0
  echo "$now" >"$stamp"
  (
    # Home Assistant waits until nothing holds its output pipe, and bash keeps
    # a saved copy of it in a higher descriptor during cmd_run's redirection.
    # Inherited here, that copy would hold the sensor for the whole request.
    for fd in /proc/$BASHPID/fd/*; do
      fd="${fd##*/}"
      (( fd > 2 )) && eval "exec $fd>&-" 2>/dev/null
    done
    exec 8>"$STATE_DIR/long_probe.lock"
    flock -n 8 || exit 0
    http_probe "$run" deviceStates_long "$url" 1 "$LONG_PROBE_MAX_TIME" | append
  ) </dev/null >/dev/null 2>&1 &
  disown
}

cmd_run() {
  command -v curl >/dev/null && command -v jq >/dev/null && command -v dig >/dev/null \
    || die "missing dependencies: curl, jq, dig (package dnsutils / bind9-dnsutils)"
  mkdir -p "$OUT_DIR" "$STATE_DIR"
  local run host tmp url_states url_states_noauth
  run="$(TZ=UTC printf '%(%Y%m%dT%H%M%SZ)T' -1)-$$"
  host="$(host_of "$GATEWAY")"
  tmp="$(mktemp -d)"
  url_states="$GATEWAY/api/bluiotdata/ha/v1/deviceStates"
  [[ -n "$SNS" ]] && url_states+="?sns=$SNS"
  url_states_noauth="$GATEWAY/api/bluiotdata/ha/v1/deviceStates"

  # DNS in parallel (8 queries x 5 s in a row would exceed the time budget)
  local s q n=0
  for s in $DNS_SERVERS; do
    for q in A AAAA; do
      dns_probe "$run" "$host" "$s" "$q" >"$tmp/dns.$n" & n=$((n + 1))
    done
  done
  wait   # DNS is bounded to ~5 s; PIN_ALL_IPS needs its answers

  # HTTP in parallel so the timings are comparable at the same instant
  http_probe "$run" deviceStates     "$url_states"         1 "$MAX_TIME" >"$tmp/1" &
  http_probe "$run" deviceStates_noauth "$url_states_noauth" 0 "$MAX_TIME" >"$tmp/2" &
  http_probe "$run" devices          "$GATEWAY/api/bluiotdata/ha/v1/devices" 1 "$MAX_TIME" >"$tmp/3" &
  ws_probe   "$run" >"$tmp/4" &
  local i=5 g ip port=443
  [[ "$host" == *:* ]] && port="${host##*:}"
  if [[ "$PIN_ALL_IPS" == 1 ]]; then
    for ip in $(cat "$tmp"/dns.* 2>/dev/null \
                | jq -r 'select(.qtype=="A") | .answer[] | select(startswith("A ")) | .[2:]' | sort -u); do
      http_probe "$run" "deviceStates@$ip" "$url_states" 1 "$MAX_TIME" \
        --resolve "${host%%:*}:$port:$ip" >"$tmp/$i" &
      i=$((i + 1))
    done
  fi
  for g in $COMPARE_GATEWAYS; do
    [[ "$g" == "$GATEWAY" ]] && continue
    http_probe "$run" "deviceStates_noauth@$(host_of "$g")" \
      "$g/api/bluiotdata/ha/v1/deviceStates" 0 "$MAX_TIME" >"$tmp/$i" &
    i=$((i + 1))
  done
  for g in $AUTH_COMPARE_GATEWAYS; do
    [[ "$g" == "$GATEWAY" ]] && continue
    http_probe "$run" "deviceStates_auth@$(host_of "$g")" \
      "$g/api/bluiotdata/ha/v1/deviceStates${SNS:+?sns=$SNS}" 1 "$MAX_TIME" >"$tmp/$i" &
    i=$((i + 1))
  done
  wait

  cat "$tmp"/dns.* "$tmp"/[0-9]* 2>/dev/null | grep -v '^$' | append
  # Keep the last pass for `summary`
  cat "$tmp"/dns.* "$tmp"/[0-9]* 2>/dev/null | grep -v '^$' >"$STATE_DIR/last_run.jsonl"

  # Network-level failure of authenticated deviceStates (no complete answer,
  # or a gateway 5xx) -> mtr + long request. API msgCode errors don't qualify:
  # the long request would just get the same quick answer.
  if [[ -s "$tmp/1" ]] && jq -e '.stage!="answered" or .http_code>=500' "$tmp/1" >/dev/null; then
    maybe_mtr "$run" "$host"
    maybe_long_probe "$run" "$url_states"
  fi
  rm -rf "$tmp"

  housekeeping
  return 0
}

# Compress past days and apply retention (matters in /config, which is part
# of Home Assistant backups).
housekeeping() {
  local today f; today="$(log_file)"
  if [[ "$COMPRESS_OLD" == 1 ]] && command -v gzip >/dev/null; then
    for f in "$OUT_DIR"/probe-*.jsonl; do
      [[ -e "$f" && "$f" != "$today" ]] || continue
      gzip -f "$f" && rm -f "$f.lock"
    done
  fi
  find "$OUT_DIR" -maxdepth 1 -name 'probe-*.jsonl*' -mtime +"$RETENTION_DAYS" -exec rm -f {} + 2>/dev/null
}

# One pass, then a compact JSON summary on stdout for a command_line sensor:
# state = how far deviceStates got (ok / empty / no_tcp / no_tls /
# no_first_byte / auth_error / http_XXX / msgcode_XX), the rest as attributes.
cmd_summary() {
  cmd_run >/dev/null 2>&1
  local f="$STATE_DIR/last_run.jsonl"
  [[ -s "$f" ]] || { echo '{"state":"no_data"}'; return 0; }
  jq -cs --argjson slow "$SLOW_MS" --arg gateway "$(host_of "$GATEWAY")" \
        --arg integration "$(host_of "$INTEGRATION_GATEWAY")" '
    def p($n): (map(select(.kind=="http" and .probe==$n)) | .[0]) // {};
    def st: if .stage==null then "skipped"
            elif .stage!="answered" then .stage
            elif .http_code==101 then "answered"
            elif .http_code!=200 then "http_\(.http_code)"
            elif .msgCode==805 then "auth_error"
            elif (.msgCode // 0)!=0 then "msgcode_\(.msgCode)"
            elif ((.t_total // 0) * 1000) > $slow then "slow"
            elif ((.devices // []) | any(.values==0)) then "empty"
            else "ok" end;
    p("deviceStates") as $d
    | (map(select(.kind=="dns" and .resolver=="system" and .qtype=="A")) | .[0]) as $dns
    | {state: ($d|st),
       ts: $d.ts, gateway: $gateway,
       integration_gateway: (if $integration=="" then null else $integration end),
       http_code: $d.http_code, msg_code: $d.msgCode,
       remote_ip: $d.remote_ip,
       t_tcp_ms: (($d.t_tcp // 0)*1000|floor), t_tls_ms: (($d.t_tls // 0)*1000|floor),
       t_first_byte_ms: (($d.t_first_byte // 0)*1000|floor),
       t_total_ms: (($d.t_total // 0)*1000|floor),
       request_id: ($d.headers // {} | to_entries | map(select(.key|test("id|trace"))) | .[0].value // null),
       noauth: (p("deviceStates_noauth")|.stage),
       devices_endpoint: (p("devices")|st),
       websocket: (p("ws_upgrade")|st),
       per_ip: (map(select(.kind=="http" and (.probe|startswith("deviceStates@"))))
                # 805 from a node other than the one the system resolver gives:
                # the token belongs to another data center, not an outage.
                | map({key:(.probe|ltrimstr("deviceStates@")),
                       value:(if .msgCode==805 and .remote_ip!=$d.remote_ip
                              then "wrong_datacenter" else st end)}) | from_entries),
       other_gateways_auth: (map(select(.kind=="http" and (.probe|startswith("deviceStates_auth@"))))
                        | map({key:(.host),
                               value:(if .msgCode==805 and $d.msgCode!=805
                                      then "wrong_datacenter" else st end)}) | from_entries),
       other_gateways: (map(select(.kind=="http" and (.probe|startswith("deviceStates_noauth@"))))
                        | map({key:(.host), value:.stage}) | from_entries),
       dns_status: $dns.status, dns_answer: ($dns.answer // [] | join(" "))}' "$f"
}

# --- Report ------------------------------------------------------------------
# Merges consecutive failed passes into UTC windows, ready to paste into a
# GitHub issue (Markdown).
# Reads logs, compressed or not (BusyBox's `zcat -f` does not read plain files).
read_logs() {
  local f
  for f in "$@"; do
    case "$f" in *.gz) gzip -dc "$f" ;; *) cat "$f" ;; esac
  done
}

cmd_report() {
  local days="${1:-1}" files=()
  local d
  for ((d = days - 1; d >= 0; d--)); do
    local f; f="$OUT_DIR/probe-$(day_utc "$(( $(date +%s) - d * 86400 ))").jsonl"
    [[ -r "$f" ]] && files+=("$f")
    [[ -r "$f.gz" ]] && files+=("$f.gz")
  done
  ((${#files[@]})) || die "no log in $OUT_DIR for the last $days day(s)"

  echo "Probe $PROBE_VERSION, gateway $GATEWAY, last $days day(s), generated $(now_utc)"
  echo

  read_logs "${files[@]}" | jq -rs --argjson slow "$SLOW_MS" '
    def ok: .stage=="answered" and .http_code==200 and (.msgCode==0)
            and ((.t_total // 0) * 1000) <= $slow;
    def stagename: if .stage!="answered" then .stage
               elif .http_code==101 then "ok"
               elif .http_code!=200 then "http_\(.http_code)"
               elif (.msgCode // 0)!=0 then "msgcode_\(.msgCode)"
               elif ((.t_total // 0) * 1000) > $slow then "slow"
               else "ok" end;
    def empty_devices: (.devices // []) | any(.values==0);
    def fmt: if .==null then "-" else (.*1000|floor|tostring)+" ms" end;
    [ .[] | select(.kind=="http" and .probe=="deviceStates") ] | sort_by(.ts) as $p
    | ($p|length) as $n
    | [ $p[] | select(ok|not) ] as $bad
    | "## deviceStates: \($n) measurements, \($bad|length) failed or slow (> \($slow) ms), " +
      "\([ $p[] | select(ok and empty_devices) ]|length) OK but empty\n",
      "| Window (UTC) | Passes | Stage | HTTP | msgCode | IP | TCP | TLS | First byte |",
      "|---|---|---|---|---|---|---|---|---|",
      ( reduce $p[] as $x ([];
          if ($x|ok) then .
          elif (length>0) and (.[-1].open) then .[-1] |= (.end=$x.ts | .n+=1 | .last=$x)
          else . + [{start:$x.ts, end:$x.ts, n:1, last:$x, open:true}] end
          | if ($x|ok) and (length>0) then .[-1].open=false else . end)
        | .[]
        | "| \(.start[0:19])Z → \(.end[0:19])Z | \(.n) | \(.last|stagename) | \(.last.http_code) | \(.last.msgCode // "-") | \(.last.remote_ip // "-") | \(.last.t_tcp|fmt) | \(.last.t_tls|fmt) | \(.last.t_first_byte|fmt) |" )
  '
  echo
  # During failures: state of the other probes in the same pass
  read_logs "${files[@]}" | jq -rs --argjson slow "$SLOW_MS" '
    def ok: .stage=="answered" and .http_code==200 and (.msgCode==0)
            and ((.t_total // 0) * 1000) <= $slow;
    def stagename: if .stage!="answered" then .stage
               elif .http_code==101 then "ok"
               elif .http_code!=200 then "http_\(.http_code)"
               elif (.msgCode // 0)!=0 then "msgcode_\(.msgCode)"
               elif ((.t_total // 0) * 1000) > $slow then "slow"
               else "ok" end;
    (group_by(.run) | map(select(any(.kind=="http" and .probe=="deviceStates" and (ok|not))))) as $runs
    | if ($runs|length)==0 then "No failed pass." else
      "## Comparison during failures (\($runs|length) passes)\n",
      ( [ $runs[][] | select(.kind=="http") ] | group_by(.probe)[]
        | "- \(.[0].probe): " + ( map(stagename) | group_by(.) | map("\(.[0]) ×\(length)") | join(", ") )
          + "; HTTP codes " + ( map(.http_code|tostring) | unique | join("/") ) ),
      ( [ $runs[][] | select(.kind=="dns") ] | group_by(.resolver+" "+.qtype)[]
        | "- DNS \(.[0].resolver) \(.[0].qtype): " + ( map(.status) | unique | join("/") )
          + " → " + ( map(.answer|join(" ")) | unique | join(" | ") ) )
      end'
  echo
  read_logs "${files[@]}" | jq -rs '
    [ .[] | select(.kind=="http" and .probe=="deviceStates_long") ]
    | if length==0 then empty else
      "## Long requests (actual hang duration)\n",
      ( .[] | "- \(.ts[0:19])Z: \(.stage), HTTP \(.http_code), \((.t_total // 0)|floor) s, exit \(.curl_exit)" )
    end'
}

cmd_check() {
  local okk=1 c
  echo "probe   bluetti-probe $PROBE_VERSION"
  for c in curl jq dig flock; do
    command -v "$c" >/dev/null && echo "ok      $c" || { echo "MISSING $c"; okk=0; }
  done
  command -v mtr >/dev/null && echo "ok      mtr (optional)" || echo "absent  mtr (optional: apt install mtr-tiny)"
  echo "config  $CONF_FILE $( [[ -r $CONF_FILE ]] && echo found || echo MISSING)"
  echo "gateway $GATEWAY"
  if [[ -n "$INTEGRATION_GATEWAY" && "$INTEGRATION_GATEWAY" != "$GATEWAY" ]]; then
    echo "        WARNING: the integration uses $INTEGRATION_GATEWAY; leave GATEWAY empty to follow it"
  fi
  local t; t="$(get_token)"
  if [[ -n "$t" ]]; then
    echo "token   present (${#t} characters)"
    # expiry, if the token is a JWT
    local exp; exp="$(cut -d. -f2 <<<"$t" | tr '_-' '/+' | base64 -d 2>/dev/null | jq -r '.exp // empty' 2>/dev/null)"
    [[ -n "$exp" ]] && echo "        expires $(date -u -d "@$exp" '+%F %T') UTC"
  else
    echo "token   MISSING: set TOKEN_FILE or HA_CONFIG_ENTRIES"; okk=0
  fi
  check_sns "$t" || okk=0
  ((okk)) && echo "=> ready" || { echo "=> incomplete"; return 1; }
}

# Validates SNS against the account's own device list, and compares what
# deviceStates says about it with what devices says. Serial numbers are only
# ever printed masked.
check_sns() {
  local t="$1" list states mine hf
  if [[ -z "$SNS" ]]; then
    echo "sns     EMPTY: deviceStates would answer msgCode 400 (missing parameter)"; return 1
  fi
  if [[ "$SNS" =~ [[:space:],\"\'] ]]; then
    echo "sns     INVALID: $(mask_sn "$SNS") contains a space, comma or quote; use ONE serial number"; return 1
  fi
  echo "sns     $(mask_sn "$SNS")"
  [[ -n "$t" ]] || return 1
  # Token through a header file, never on the command line (`ps`).
  hf="$(mktemp)"; chmod 600 "$hf"; printf 'Authorization: %s\n' "$t" >"$hf"
  list="$(curl -sS --max-time 20 -A "$USER_AGENT" -H "@$hf" \
          "$GATEWAY/api/bluiotdata/ha/v1/devices" 2>/dev/null)"
  if ! jq -e '.msgCode==0 and (.data|type)=="array"' <<<"$list" >/dev/null 2>&1; then
    echo "devices could not list the account's devices (msgCode $(jq -r '.msgCode // "?"' <<<"$list" 2>/dev/null))"
    rm -f "$hf"; return 1
  fi
  jq -r '.data[] | "        account device \(.sn|tostring|if length>8 then .[0:4]+"…"+.[-4:] else . end): online=\(.online)"' <<<"$list"
  mine="$(jq -c --arg sn "$SNS" '[.data[] | select(.sn==$sn)][0] // empty' <<<"$list")"
  if [[ -z "$mine" ]]; then
    echo "sns     NOT FOUND among the account's devices: check every character"; rm -f "$hf"; return 1
  fi
  states="$(curl -sS --max-time 40 -A "$USER_AGENT" -H "@$hf" \
            "$GATEWAY/api/bluiotdata/ha/v1/deviceStates?sns=$SNS" 2>/dev/null)"
  rm -f "$hf"
  jq -r --argjson m "$mine" '
    (.data // [])[0] as $d
    | if .msgCode!=0 then "states  deviceStates answered msgCode \(.msgCode): \(.message)"
      else "states  deviceStates: online=\($d.online), \(($d.stateList // [])|length) values; devices: online=\($m.online), \(($m.stateList // [])|length) values"
        + (if ($d.online!=$m.online) or ((($d.stateList // [])|length)==0 and (($m.stateList // [])|length)>0)
           then "\n        WARNING: the two endpoints disagree about this device" else "" end)
      end' <<<"$states"
  [[ "$(jq -r '.online' <<<"$mine")" == 1 ]] || echo "        note: this device is offline; an online one measures the live path better"
  return 0
}

cmd_install() {
  [[ $EUID -eq 0 ]] || die "install must be run as root"
  local self; self="$(readlink -f "$0")"
  install -m 0755 "$self" /usr/local/bin/bluetti-probe.sh
  if [[ ! -e /etc/bluetti-probe.conf ]]; then
    cat >/etc/bluetti-probe.conf <<'EOF'
# bluetti-probe.sh configuration
GATEWAY="https://gw.bluettipower.com"   # or https://gwde.bluettipower.com (eu), https://gwpry.bluettipower.com (us)
SNS=""                                  # serial number of ONE online device, e.g. AC3000000000001234
# Token: ONE of the two options
TOKEN_FILE="/etc/bluetti-probe.token"   # file holding only the access_token
#HA_CONFIG_ENTRIES="/mnt/ha-config/.storage/core.config_entries"
OUT_DIR="/var/log/bluetti-probe"
MAX_TIME=55
EOF
    chmod 600 /etc/bluetti-probe.conf
  fi
  cat >/etc/systemd/system/bluetti-probe.service <<'EOF'
[Unit]
Description=BLUETTI cloud API probe (deviceStates)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/bluetti-probe.sh run
# The long request started on failure must outlive the pass
KillMode=process
TimeoutStartSec=90
Nice=10
EOF
  cat >/etc/systemd/system/bluetti-probe.timer <<'EOF'
[Unit]
Description=Run the BLUETTI probe every minute

[Timer]
OnCalendar=*-*-* *:*:00
AccuracySec=1s
Persistent=false

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  echo "Installed. Next steps:"
  echo "  1. edit /etc/bluetti-probe.conf (SNS, token)"
  echo "  2. bluetti-probe.sh check"
  echo "  3. systemctl enable --now bluetti-probe.timer"
}

case "${1:-run}" in
  run)     cmd_run ;;
  report)
    # Also saved as a file: Home Assistant shows action responses as YAML,
    # which folds long lines and breaks the Markdown tables when copied.
    days="${2:-1}"; [[ "$days" =~ ^[0-9]+$ ]] || die "days must be a number"
    mkdir -p "$OUT_DIR"
    cmd_report "$days" | tee "$OUT_DIR/report-last-${days}d.md" ;;
  check)   cmd_check ;;
  summary) cmd_summary ;;
  install) cmd_install ;;
  *)       sed -n '2,20p' "$0"; exit 2 ;;
esac
