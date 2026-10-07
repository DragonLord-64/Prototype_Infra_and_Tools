# Latest upstream switch monitoring setup

[Monitoring overview](../README.md)

Snapshot copied October 6, 2026 from the public [SKA Mid CBF prototyping repository](https://gitlab.com/ska-telescope/ska-mid-cbf/integration/ska-mid-cbf-prototyping), branch `switch-monitoring-john`, commit `647c76f492a765679eb72bdc136f32cc89c21f8b`. The home-directory clone is checked out on that branch and tracks its remote.

- [Telegraf values](telegraf-values.yaml): Cisco DME gRPC input, interface/VLAN/chassis aliases, regex labels, Prometheus endpoint.
- [Prometheus values](prometheus-values.yaml): switch Telegraf scrape target plus packet/octet recording rules.
- [Grafana dashboard](400GSwitchDashboard.json).
- [Upstream deployment notes](https://gitlab.com/ska-telescope/ska-mid-cbf/integration/ska-mid-cbf-prototyping/-/blob/647c76f492a765679eb72bdc136f32cc89c21f8b/k8s/switch-monitoring/README.md).

Newest relevant commits by John So: VLAN broadcast rate October 6; interface packet rate October 3; recording rules October 1. These three copied files match upstream bytes and are reference inputs, not an executed deployment. They preserve upstream six-hour retention and disabled Prometheus persistence; apply the [storage design](../DESIGN.md) before adopting them for durable monitoring. Existing Grafana alert/design files remain unchanged. No cluster resources or Helm releases were changed.

Upstream copyright/license is retained in [LICENSE.SKAPROTOTYPING](LICENSE.SKAPROTOTYPING).
