# Grafana dashboard prototypes

Four synthetic monitoring views, captured on 2026-10-19. These are independent examples, separate from the repository's infrastructure monitoring deployment. No real hardware connection or production compatibility is claimed.

| View | Dashboard UID | Source and screenshot |
| --- | --- | --- |
| Server health | `server-health-demo` | [Source](server-health/) · [Overview](server-health/screenshots/updated-overview.jpg) |
| Cisco switch overview and port detail | `cisco-switch-demo`, `cisco-switch-detail` | [Source](cisco-switch/) · [All ports](cisco-switch/screenshots/compact-overview.jpg) |
| VCCU–FSPU link matrix | `vccu-fspu-demo` | [Source](vccu-fspu/) · [Matrix](vccu-fspu/screenshots/matrix.jpg) |
| Network VLAN viewer | `vlan-net-viewer-demo` | [Source](vlan-net-viewer/) · [VLAN 55](vlan-net-viewer/screenshots/overview.jpg) |

## Launch the containers

Requirements: Docker Engine running, permission to use Docker, and Python 3. Run these commands from the repository root:

```bash
cd monitoring/dashboard-prototypes
python3 run.py
```

This is the launcher verified on the current machine, which does not have the Compose plugin installed. It starts Grafana, Prometheus and four mock exporters in the background. Re-running it starts any stopped containers belonging to this prototype; it does not replace existing containers or apply changed launcher settings.

Open http://localhost:3002 and follow Grafana's normal first-run login flow. Dashboard links:

- [Server health](http://localhost:3002/d/server-health-demo)
- [Switch ports](http://localhost:3002/d/cisco-switch-demo)
- [VCCU–FSPU matrix](http://localhost:3002/d/vccu-fspu-demo)
- [VLAN viewer](http://localhost:3002/d/vlan-net-viewer-demo?var-vlan=55)

Check running containers:

```bash
docker ps --filter label=org.dashboard-prototypes.owner=grafana-dashboard-prototypes
```

Stop only this prototype, retaining its data:

```bash
docker ps -q --filter label=org.dashboard-prototypes.owner=grafana-dashboard-prototypes | xargs -r docker stop
```

To select a different port before the first launch, use `GRAFANA_DEMO_PORT=3003 python3 run.py`. The default port 3002 leaves the existing Desktop demos on 3001 running. Only Grafana is published, on loopback; Prometheus and exporters remain internal. No credentials or private inventory are bundled. Images are pinned to the digests used by the working Desktop demos (Grafana 13.2.4); Docker may download them on another machine.

### Alternative: Docker Compose

If the Compose plugin is installed, use this launcher instead:

```bash
cd monitoring/dashboard-prototypes
docker compose config --quiet
docker compose up -d
```

Use one launcher per instance. Compose has separate container names, network and volumes from `run.py`; running both on the same port will fail. Override the port with `GRAFANA_DEMO_PORT=3003 docker compose up -d`. Stop the Compose instance with `docker compose down`; named volumes retain settings and history. Compose YAML and mount paths were checked, but Compose itself was not available for execution on the current host.

## Edit the samples

Each exporter reloads its adjacent `mock-*.json` every five seconds. Edit those files directly to preserve your scenarios. The source generators can overwrite sample data: `cisco-switch/make_mock.py` and `vlan-net-viewer/build.py` reset their respective fixtures. Existing dashboard JSON is ready to use; generation is optional.

Run `generate_dashboard.py` from the server, switch or matrix directory after changing layout. For VLAN names/routes, run `vlan-net-viewer/refine_dashboard.py`; it reads the current fixture without replacing it. Mounted dashboard files reload automatically. Changes to provisioning may require `docker compose restart grafana`.

### Server health

14 components: Component 1–2, PSU 1–2, NIC, six fans, motherboard, BMC and network LAN, plus an Everything else table. A status square accompanies the key readings. Metric limits derive component health; failed takes precedence over unknown and degraded. Missing readings remain unknown. Fan 4 is degraded in the sample. See [exporter schema](server-health/EXPORTER.md).

### Cisco switch

32 physical ports, each with four interfaces: 128 interface boxes. Parent ports show link state and aggregate OK/Fault; interfaces show link state and Good/Error/Drop. Any unhealthy/overtemperature component or recent interface CRC/drop activity makes the parent red. Link-down alone is separate from hardware health. Error takes precedence over Drop. Details retain mode, named VLANs, traffic/counters and shared transceiver temperature/voltage once per port. Unavailable DOM remains N/A. The 75°C/85°C optical limits are illustrative, not verified module specifications. Fixture recent-error windows are supplied observations, not computed live rates.

### VCCU–FSPU matrix

24 VCC units × 27 FSP units = 648 links in fixed row/column order. Cells show rounded Gbit/s; blue intensity encodes rate, × means down, ! means degraded, and ? means unknown. Zero traffic can still be up. Select a cell or the endpoint dropdowns for exact rate, state, capacity and history. All sample capacities are 100 Gbit/s; the matrix's display mapping assumes that capacity. Display-only sentinels are separate from actual rate/state metrics. No Server A topology is inferred.

### VLAN viewer

24 VCCU and 27 FSPU attachments, with one logical switch interface per unit across two demo switches. VCC units are on the left and FSP units on the right. Green means directly allowed; blue means an explicitly configured directed translation on that exact switch and interface. No inverse/transitive inference is performed. VLAN 55 matches 35 direct and five translated interfaces. Additional interface records can represent multiple or transit attachments. This is configured allowance, not proof of an operational end-to-end path.

## Validation and deferred work

The Desktop originals were visually checked in Grafana, including switch/matrix click-through and VLAN dropdown filtering. Component screenshots capture those originals. The copied stack was started with `python3 run.py` on port 3002 and its switch overview was visually verified; [running repo screenshot](screenshots/repository-switch-online.jpg). All five dashboard definitions are available through Grafana, and all four Prometheus targets report up. Verified series counts: 14 server components, 128 switch interfaces, 648 matrix links, and 40 VLAN-55 matches. YAML and mount paths validate; the Compose plugin is unavailable on this host, so Compose itself was not executed. Seven existing VLAN tests pass. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) records the exact copied sources and SHA-256 hashes. Packaging validation is recorded in the repository knowledge log.

Device-data freshness was discussed but is deliberately deferred. A future collector should export last successful device collection timestamps; scrape success alone does not establish device freshness. Other review findings: improve the matrix's small-text contrast, agree error/drop thresholds and fault duration, expose fault reasons and sensor histories in detail views, and test real hardware telemetry. These remain prototype limitations.
