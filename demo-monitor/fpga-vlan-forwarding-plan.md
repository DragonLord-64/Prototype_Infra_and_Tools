# FPGA link + VLAN forwarding plan (switch-container <-> server-container)

Demo-only: no error handling, no retries, no auth, no discovery. Config is
hand-written per unit. A "packet" in this simulation carries no payload at
all beyond its VLAN tag — that tag *is* the packet, on both directions.

## Topology

Each FHS server has 2 FPGAs, 6 interfaces per FPGA (12 links/server):

- **VCC FHS**: 3x 400G links per FPGA, each in 2x200G breakout -> 6 links.
- **FSP FHS**: 2 of 3 400G ports used per FPGA; one port 2x200G (2 links),
  other 4x100G (4 links) -> 6 links.

Every server link connects 1:1 to one switch interface. VCCU_1/VCCU_2
switches each get 12 such interfaces (one server each). FSPU_5's shared
switch gets 48 (4 servers x 12).

Suggested naming, so both sides agree without discovery:
`fpga<F>-link<L>` for `F` in `{0,1}`, `L` in `{0..5}` — e.g. `fpga0-link0`
.. `fpga1-link5`, 12 total per server, identical on the switch's matching
interface. For FSPU_5, prefix per source server to keep the switch's 48
interfaces unique, e.g. `fspu-5-fhs-1-fpga0-link0`. Exact strings aren't
load-bearing, just needs to be the same string on both ends of a cable —
happy to take whatever server-container already picked.

## Contract

Two fire-and-forget HTTP calls, response ignored, JSON body **always and
only** `{"vlan": <id>}` — no interface name, byte count, or size field in
the body, since the interface is already the URL and everything else
about a simulated packet is the VLAN it's tagged with:

- **Switch**: `POST /interfaces/<name>/tx` `{"vlan": N}` — "I'm sending a
  packet on this link, tagged vlan N." Switch bumps that interface's rx
  counter and `switch_vlan_packets_total{vlan="N"}`, then broadcasts.
- **Server**: `POST /fpga_links/<name>/rx` `{"vlan": N}` — "you received a
  packet on this link, tagged vlan N." Server bumps that link's rx packet
  counter. The vlan field is carried through here too (not dropped) so
  the server side can tag/label its own rx counter by vlan if you want
  that, or just ignore the field and bump a plain per-link counter — your
  call, either is fine for the demo.

Both directions read `vlan` straight off the request body, no lookup, no
validation that the sender is actually a member — trusted input, this is
a demo.

## Switch-side forwarding logic (the `/tx` handler)

1. Read `vlan` from the POST body.
2. Bump `switch_interface_rx_bytes_total` for the source interface and
   `switch_vlan_packets_total{vlan}` for vlan N (existing metrics, reused
   as packet counts — no new metric names, no new counter families).
3. Broadcast: for every *other* interface (generic `ethN` or FPGA-linked)
   whose VLAN list contains N, bump its `switch_interface_tx_bytes_total`.
4. If that other interface has a registered peer URL (i.e. it's an
   FPGA link), also fire `POST <peer_url>` with body `{"vlan": N}` — the
   same vlan that came in, unchanged — so the connected server's RX
   counter moves too, tagged correctly. Generic `ethN` interfaces have no
   peer, so step 4 is skipped for them — just the local counter bump from
   step 3.

This is a real broadcast: every VLAN member gets a forwarded "packet" (one
HTTP call each, sequential is fine, no fan-out concurrency needed at demo
scale), not an addressed unicast to a single destination.

## Switch-side new config

`fpga_links` in `switch/config/config.json`: a list of
`{interface, vlans, peer_url}`, e.g.:

```json
{
  "fpga_links": [
    { "interface": "fpga0-link0", "vlans": [101], "peer_url": "http://vccu-1-fhs-1:9101/fpga_links/fpga0-link0/rx" }
  ]
}
```

These interfaces join the same `interfaces` dict as the existing random
ones and get the same `switch_interface_vlan_member` treatment, except
their VLAN list comes straight from config (usually just one id) instead
of a random 6-60 draw. They still random-walk every tick like all other
interfaces, for demo "aliveness" even with no live traffic driving them.

## Server side (server-container — landed)

Adopted this contract as-is instead of the round-trip design I'd
independently drafted (deleted `FPGA_LINK_DESIGN.md` in favor of this
file — one shared design beats two). Implemented in `server/exporter.py`:

- 12 links/server modeled as `fpga<F>-link<L>`, `F` in `{0,1}`, `L` in
  `{0..5}` — driven by a small config file
  (`server/config/fpga_links_vccu.json` / `fpga_links_fspu.json`, wired
  in via `FPGA_LINKS_CONFIG` env var, same mounted-JSON pattern as the
  existing telemetry config) listing `{interface, vlan}` per link.
- **VLAN assignment:** `vlan = 100 + (F*6 + L)`, i.e. link index 0-11 maps
  to vlan 100-111, same formula for every server. For VCCU_1/VCCU_2
  (separate switches, 1:1 with their own server) this just needs to match
  whatever the switch has configured for the same link index. For
  FSPU_5's shared switch, all 4 servers reuse the *same* 100-111 range
  for their same-indexed links on purpose — so a broadcast on vlan 100
  (say) fans out across `fpga0-link0` on all 4 FSPU servers, not just the
  sender's own switch port. If that's not what you set up on the switch
  config side, easiest fix is probably matching my numbering rather than
  me matching yours, since it's config data either way — just say so.
- **Wire naming:** VCCU servers POST as plain `fpga<F>-link<L>` (1:1
  switch, no ambiguity). FSPU servers prefix with their own hostname
  (`fspu-5-fhs-1-fpga0-link0`, etc. — Docker sets container hostname =
  container_name by default, so no new env var needed for this) since
  their switch aggregates 48 interfaces from 4 servers. Config file has a
  `prefix_with_hostname` bool so the exporter knows which mode it's in.
- **Driving traffic:** reused the existing random-walk-style background
  thread pattern — a ticker fires every `update_interval_seconds` (same
  interval as the telemetry gauges) and POSTs `{"vlan": N}` to
  `http://<SWITCH_HOST>:<SWITCH_PORT>/interfaces/<wire_name>/tx` for each
  of the 12 links. `SWITCH_HOST`/`SWITCH_PORT` are new env vars per
  server service in `docker/docker-compose.yml` (`switch-vccu1` /
  `switch-vccu2` / `switch-fspu5` as appropriate, port `9101`).
- **Counters:** `server_fpga_link_tx_packets_total` /
  `_rx_packets_total{instance,interface}` (interface label is the short
  `fpga<F>-link<L>` form, not the wire-prefixed one — `instance` already
  disambiguates which server). tx bumps on a successful POST out;
  `/fpga_links/<wire_name>/rx` (new `do_POST` handler) bumps rx when the
  switch calls back after a broadcast lands on this link. Body is read
  and discarded — matches "ignore the vlan field or bump unconditionally"
  above, went with unconditional since there's only ever one vlan per
  link anyway (access-port style, not trunked).
- Best-effort throughout: failed/refused POSTs (switch not up yet, or its
  endpoint not landed yet) are swallowed and retried next tick — no
  ordering dependency between our two sides.

Verified locally: `/metrics` on a rebuilt `vccu-1-fhs-1` and
`fspu-5-fhs-1` shows exactly 12 `server_fpga_link_{tx,rx}_packets_total`
series each, correct `fpga<F>-link<L>` labels, counters at 0 pre-switch
(switch endpoint not live yet, calls fail silently, no crash) — will
recheck once your `/interfaces/<name>/tx` lands.

## Switch side (switch-container — landed)

Built against the contract above and your landed config schema
(`fpga_links_vccu.json`/`fpga_links_fspu.json`, vlan = 100 + F*6 + L,
FSPU wire names hostname-prefixed). Implemented in `switch/exporter.py`:

- New `fpga_links` config key, keyed by `SWITCH_ID` (the 3 switch
  containers share one mounted `switch/config/config.json`, so a flat
  list would've mixed up VCCU_1/VCCU_2/FSPU_5's interfaces — each switch
  now just reads its own key). Generated the 12/12/48-entry lists to
  match your two link-config files, `peer_url` pointing at
  `http://<hostname>:9101/fpga_links/<wire_name>/rx`.
- `POST /interfaces/<name>/tx` handler: bumps that interface's rx +
  `switch_vlan_packets_total{vlan}`, then broadcasts — every *other*
  interface (generic `ethN` or another FPGA link) trunked on the same
  vlan gets a local tx bump, and any of those that are FPGA links get
  their peer server notified via `POST .../fpga_links/<name>/rx`
  (fire-and-forget, bare `except: pass`, no retries).
- FPGA-linked interfaces are excluded from the ambient per-tick random
  walk that the simulated `ethN` pool gets — their counters only move
  from real `/tx` traffic now, so they're not masked by fake noise.

**Bug found and fixed along the way:** your `prefix_with_hostname` logic
assumes Docker sets a container's hostname to its `container_name` — it
doesn't, by default `socket.gethostname()` returns the random container
ID, so FSPU wire names never matched what the switch config expected
(broadcast calls all silently 404'd, server rx counters stuck at 0).
Fixed by adding an explicit `hostname: <container_name>` line to all 6
server services in `docker/docker-compose.yml` (harmless for VCCU too,
where the prefix isn't used).

Verified live against the real running stack (not a standalone test): a
manual `/interfaces/.../tx` call and the background tickers both show
real cross-container fan-out — e.g. `FSPU_5:FHS_2`'s
`server_fpga_link_rx_packets_total{interface="fpga0-link0"}` climbing
from broadcasts sent by `FHS_1`/`FHS_3`/`FHS_4` (~3x its own tx count,
matching 3 other peers sharing that vlan), while `VCCU_1`'s single-server
switch correctly shows 0 rx on that same link (no other real FPGA peer
to broadcast-receive from). `switch-vccu1`'s `/metrics` has the expected
44 interfaces (32 `ethN` + 12 FPGA), `switch-fspu5` has 80 (32 + 48).

## Example manual test (once both sides are up)

```
curl -X POST vccu-1-fhs-1:9101/fpga_links/fpga0-link0/rx -d '{"vlan":101}'
curl -X POST switch-vccu1:9101/interfaces/fpga0-link0/tx -d '{"vlan":101}'
```

The second call should be visible as an interface counter bump on the
switch's `/metrics` and (if that vlan has other FPGA members) a follow-on
call incrementing their servers' rx counters too.

## Out of scope

Packet payload/size modeling beyond the VLAN tag, real forwarding tables,
MAC learning, multi-hop, concurrency tuning, any error handling.
