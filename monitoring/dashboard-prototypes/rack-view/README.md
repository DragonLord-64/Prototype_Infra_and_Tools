# Rack elevation prototype

Two synthetic 42U front elevations, 16 servers in 1U, 2U and 4U positions. Green **OK**, red **Fault**, grey **Unknown**. Placement survives absent health readings; inventory alone never means healthy. The banner includes an explicit link to the existing shared synthetic server-detail dashboard; it is not a per-server live detail.

Open [Rack View](http://localhost:3002/d/rack-view-demo) after running the [parent launcher](../README.md#launch-the-containers). No runtime NetBox access or credentials are used.

## Data flow

Intended deployment: **NetBox → provisioning → machine-local file → textfile collector → Prometheus → Grafana**. This prototype starts at the machine-local file stage. It does not modify or integrate the FHS provisioner.

For this demo, each synthetic server-local `.prom` file contains:

```prometheus
server_rack_info{server_id="server-a01",rack="rack-a",position_u="1",height_u="2",face="front"} 1
```

`position_u` means the **lowest occupied U**; a 2U server at U1 occupies U1–U2. Stable `server_id` joins inventory and health. `face` is front/rear; this sample contains front records only. The layout generator creates a separate elevation for each rack/face pair, using a fixed 42U rack height. Rack height should become inventory-driven before supporting other sizes.

Each file in [inventory/](inventory/) represents a file on one synthetic server. The small standard-library [exporter](exporter.py) aggregates these files to stand in for multiple Node Exporter textfile collectors. It exposes metadata and separately loads observed health from [mock-health.json](mock-health.json): **0 OK, 1 Fault, 2 Unknown**; omitted/null health emits no health sample. This aggregation is a demo convenience, not a proposed deployment topology. In a real deployment Prometheus would scrape each server's existing collector.

The source files retain placement after health disappears. Canvas geometry is generated from those files, not from current health samples. If the exporter itself becomes unavailable, static boxes remain and missing readings display Unknown. The current sample: server-a04 and server-b03 Fault; server-b06 has no health reading and shows Unknown. All other servers OK.

## Edit and regenerate

Edit existing `.prom` files to change placement; edit `mock-health.json` to change health. Health reloads each scrape. Placement changes require regenerating the dashboard:

```bash
cd monitoring/dashboard-prototypes/rack-view
python3 generate_dashboard.py
python3 -m unittest -v test_rack_view.py
```

Restarting the exporter is unnecessary for fixture edits. The generator rejects duplicate IDs, overlapping rack-face slots and out-of-bounds placements. `make_sample.py` resets the synthetic fixtures and should only be run intentionally.

Fresh launches mount this dashboard automatically. An existing Docker CLI instance created before rack-view is installed by re-running `python3 run.py`; it copies only the new dashboard into the existing writable Grafana volume when a dedicated rack-view bind mount is absent. After adding the new scrape job to an existing Prometheus instance, restart **only** `grafana-dashboard-prototypes-prometheus`. This application restart does not restart the host.

## Limits

Server-box one-click links are configured but browser click-through remains unverified; use the explicit shared-detail link in the banner.

The prototype uses sample aggregate health rather than real sensor rules. A real collector should retain inventory centrally or generate it from provisioned inventory independently of device reachability; this layout does so through the checked-in files. Device observation timestamps/freshness indicators remain deferred. New metadata must trigger layout regeneration; Grafana Canvas does not automatically reposition boxes from a label update. Real server-local collection, NetBox provisioning extensions and real hardware thresholds are not yet implemented.
