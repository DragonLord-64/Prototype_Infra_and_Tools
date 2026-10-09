# Knowledge-base change log

[Knowledge-base index](AGENTS.md)

Append dated entries in chronological order. Record what changed in the wiki,
which pages changed, the source of the information, and material open questions.
Git retains detailed edit history; this log is a readable guide to knowledge changes.

## 2026-10-06 — Basic wiki structure

- Added an [AGENTS.md index and maintenance workflow](AGENTS.md), with six
  area AGENTS.md indexes, for ingest, query, and lint. No separate index files
  are needed: AGENTS.md provides both navigation and maintenance guidance.
- Kept existing READMEs as canonical topic pages and preserved the monitoring
  demo's existing local instructions. Added a discovery link to the root README.
- Sources: existing repository layout, READMEs, and source file names. This entry
  records documentation organization; no deployment or live-service verification
  was performed for this change.
- Structure inspired by [Karpathy's LLM Wiki notes](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## 2026-10-06 — Optional FPGA SDK inventory scaffold

Expanded [FPGA discovery](end-to-end-netbox/FPGA_EXTENSION.md) with existing-venv
BMC-display configuration, per-card serial/firmware, explicit Altera/Arkville PCI
mappings, and separate NIC endpoint metadata. Evidence: playbook/adapter source
and synthetic parser/safety tests. Dedicated-container compare/apply/repeat and
NetBox API assertions passed; repeat changed nothing. Real vendor argv, SDK root and output patterns
remain user-supplied; synthetic fixtures do not verify real SDK behavior.

## [2026-10-06] ingest | Nexus switch inventory

Added [Nexus discovery guidance](end-to-end-netbox/NEXUS.md) and linked the
separate playbook from the pipeline overview/index. Cisco show-command schemas
and Ansible NX-OS documentation ground the mappings; tests use synthetic output,
and physical Nexus validation remains pending. DAC local-end policy is explicit.

## 2026-10-06 — Portable FHS NetBox pipeline

Added [the current self-contained FHS bundle](end-to-end-netbox/development/README.md), sourced from the public SKA development playbooks. Documented retained fleet/SDK defaults, per-card FPGA modules with three interfaces, check/apply and Bifrost handoff limits, and synthetic portability verification. Live hardware verification remains pending. Older demo sources remain available until archive organization completes.

## 2026-10-06 — Active portable work and historical archive

Moved older tracked platform, deployments, automation, utilities, and default-environment source into [archive](archive/README.md), preserving their wiki indexes and history. Kept the existing [NetBox pipeline](end-to-end-netbox/README.md) and latest development bundle active. Added the source-grounded [monitoring design](archive/monitoring/DESIGN.md). Ignored private/runtime files stayed at their original paths; no deployment or service action occurred. Relative documentation links were updated; historical scripts still require a path review before reuse.

## 2026-10-06 — Grafana node-exporter Slack template

Added the [alert provisioning template](archive/monitoring/node-exporter-slack.yaml), [Helm mount/Secret example](archive/monitoring/reference/grafana-helm-values.example.yaml), and [usage guide](archive/monitoring/README.md). Evidence: current Grafana documentation/provisioning schema and FHS Baremetal node job template. Failed scrapes alert after two minutes; missing inventory targets remain a separate coverage requirement. YAML/schema checks are isolated; no cluster deployment or Slack message was performed.

## 2026-10-06 — FPGA SDK parser formatting compatibility

Aligned [portable FHS SDK parser defaults](end-to-end-netbox/development/README.md) with the known-working source grammar (variable indentation and index suffixes). Added field-name-only diagnostics and a regression test using packaged defaults; physical output confirmation remains pending.

## 2026-10-06 — Published SDK sample validation

Validated the [FHS parser](end-to-end-netbox/development/README.md) against the newly published public SDK/QSFP sample. Corrected full alphanumeric serial matching and retained variable indentation. Added sanitized output-shape fixtures and copied-layout tests using them; FPGA optics remain unimported. No live hardware commands were run.

## 2026-10-06 — Opt-in SDK discovery debugging

Added [SDK debugging instructions](end-to-end-netbox/development/README.md), gated command-output diagnostics before normalization, and explicit failed-exit validation. Restored the source target PATH after venv prefixes and documented how old generic error wording identifies a stale filter copy. Synthetic tests cover debug output and stopping before parse/API changes on SDK failure.

## 2026-10-06 — Physical NIC module discovery

Extended [the portable FHS bundle](end-to-end-netbox/development/README.md) with sample-grounded ethtool driver/firmware/PCI/link parsing and existing PCI VPD card identity. Documented verified serial+part grouping, explicit virtual-port exclusions, safe interface adoption and partial-data preservation. No automatic optics/DAC/cable imports or destructive legacy migration. Synthetic parser, multiport and copied-layout check/apply/idempotence tests cover the change; physical NIC smoke verification remains pending.

## 2026-10-06 — Latest John switch setup

Fetched the public SKA prototyping repository and selected John So's monitoring branch. Copied its current [switch monitoring inputs](archive/monitoring/upstream-switch/README.md), preserving source identity and unchanged values/dashboard. No cluster deployment or persistence change was performed.

## 2026-10-06 — Persistent monitoring configuration and Elastic chart

Added [Prometheus persistence values](archive/monitoring/PERSISTENCE.md) with a 50G requested PVC, editable nfss1 candidate class, retention headroom, and a single writer. Storage backend is unverified; Prometheus NFS incompatibility is explicit. Added a [fresh-install Elastic Helm chart](archive/monitoring/elastic-small/README.md), matching Docker Hub Elasticsearch/Kibana9.5.5 digests, existing Secret references, and bounded Kibana service-user setup. Helm lint/render/schema and isolated resource checks passed. No cluster deployment, existing-data upgrade, volume migration, or log delivery test occurred.

## 2026-10-06 — NetBox manufacturer IDs and bounded service retries

Updated [both portable imports](end-to-end-netbox/development/README.md) to ensure reported manufacturers and use returned vendor/type IDs, preserving custom slugs and avoiding guessed vendor aliases. Added server write serialization, object-loop pacing and current-result bounded transient502/503/504 retries; permanent400 remains immediate. Synthetic manufacturer and actual Ansible retry/copy-layout/Nexus task tests passed. Underlying live503 cause remains unconfirmed; imports should run separately.

## 2026-10-06 — First implementation run guide

Shortened the [portable FHS bundle guide](end-to-end-netbox/development/README.md) to real-environment setup and execution: whole-directory copying including shared module utilities, Bifrost credential paths, inventory overrides, scoped imports and export handoff. Removed explanatory code comments and outdated task labels without changing functionality. Python syntax-tree equivalence and YAML equivalence apart from task labels verified behavior preservation; published implementation tests remain intact. The operator confirmed FPGA/NIC import on one server; fleet and cluster validation remain separate.

## 2026-10-06 — Nexus manufacturer query contract

Corrected [Nexus module-type lookup](end-to-end-netbox/development/README.md): numeric manufacturer IDs use the manufacturer_id filter, while manufacturer is a slug filter. Restored native installed-module ID filter defaults to avoid the same override problem for module bays. Added real installed-collection builder and strict isolated request/copy-layout regressions; no live cluster actions or manufacturer deletion.

## 2026-10-06 — Unified monitoring Helm bundle

Consolidated [the monitoring stack](archive/monitoring/reference/umbrella/README.md) into a dependency-locked umbrella chart for namespace mid-cbf-monitoring. One values list contains the eight supplied server addresses with node9100/custom9101(provisional), separate scrape jobs, and no added server-side exporters. Updated persistence to user-confirmed bds1 Ceph RBD: Prometheus requests50G and retains blocks up to37GB. Preserved John's queries/tables in a classic dashboard provisioning adaptation with a stable data-source UID. Slack remains disabled pending administrator Secret; no live releases/data/volumes changed. Helm lint/render/contracts validate targets, service/namespace wiring, storage limits, pinned Docker Hub images, optionalSlack and disabled components.

## 2026-10-06 — Transparent per-component monitoring values

Replaced the default umbrella interface with [visible component values](archive/monitoring/README.md) and a render-only helper. All eight node/custom target pairs are explicit in the Prometheus file; bds1/50G/37GB/15d settings are retained. Existing Grafana is excluded by default and optional values do not adopt its release. The prior umbrella and samples remain [historical references](archive/monitoring/reference/umbrella/README.md). Documented that Prometheus/Telegraf endpoints currently have no authentication and Telegraf has no UI/default login. Local rendering/contracts validate unchanged targets/storage and absence of Grafana from default output; no live cluster operation occurred.

## 2026-10-06 — Five YAML files only

Flattened [monitoring](monitoring/) to exactly five component values files, as requested. Moved every extra tracked monitoring document, helper, and chart into [the archive](archive/monitoring/README.md). Root navigation preserves chart compatibility: Elastic overlays require the archived local chart. Values and targets are unchanged; existing running Grafana and the cluster were untouched. YAML and local Helm rendering checks validate the resulting files.

## 2026-10-06 — Module-aware FHS dynamic inventory

Added [the read-only module inventory extension](end-to-end-netbox/development/MODULE_INVENTORY.md), preserving existing NetBox inventory auth/Vault, filters, role groups and native host variables. Supplies FPGA/NIC module lists and the existing BIST serial aliases without PSU/BDF discovery or importer changes. Actual ansible-inventory/Vault/filter/group tests passed against a synthetic API; existing BDF/interface role defaults remain unchanged.

## 2026-10-06 — Active chart and beginner setup

Added the [beginner monitoring guide](monitoring/README.md) and restored required [Elasticsearch/Kibana templates](monitoring/charts/elasticsearch-kibana/Chart.yaml) to the active folder. Kept five visible values; local chart uses the same release-based services and adds an explicit private LoadBalancer option. Guide covers Secret generation, dedicated Filebeat publisher, real host-reachable endpoint, actual FHS role output variables, and version/input compatibility. Existing Grafana and all live cluster resources remain untouched. Local chart render/lint and targeted contract/document checks passed.

## 2026-10-07 — Filebeat publisher bootstrap from a pre-created Secret

Updated [the active Elastic chart](monitoring/charts/elasticsearch-kibana/Chart.yaml) to 0.3.0 and [the beginner monitoring guide](monitoring/README.md): generate `filebeat-password` beforehand in `elastic-credentials`, let the chart create the scoped `filebeat_writer` role/user, and provision the same value to eight host Filebeats through Ansible Vault. Chart defaults keep bootstrap optional; [the active Elasticsearch overlay](monitoring/elasticsearch.yaml) enables it. Moved service-user setup to an independent bounded, idempotent Job so Filebeat works without Kibana. Documented separate account purposes, existing Secret handling, upgrade-based publisher/Kibana password reconciliation, and the still-required administrator template/lifecycle setup. Helm lint passed for default/combined/Elasticsearch-only values; [six render/mock contract tests](monitoring/tests/test_elastic_bootstrap.py) passed for component combinations, Secret references, bounded retries, least-privilege role payload, invalid-password/schema rejection, failure ordering, and credential-free output. No live deployment or host service action was performed.

## 2026-10-07 — Initial PDU HTTP push receiver

Extended [the existing Telegraf values](monitoring/telegraf.yaml) with HTTP JSON input on TCP8080 `/pdu`, exposed through its existing Service and container. Cisco gRPC57000, switch-only processors, and Prometheus9273 remain in place. Added [private endpoint and synthetic POST verification guidance](monitoring/README.md), with explicit separation between initial receiving connectivity and later actual Raritan payload mapping. The receiver is not durable raw-message capture; real firmware/payload compatibility, units and per-sensor identities remain unverified. Pinned upstream chart 1.8.77 Helm lint/render and rendered TOML/Kubernetes port/input/output/processor contracts passed. Telegraf runtime was not available locally (no binary and Docker socket inaccessible), so synthetic POST behavior remains a deployment check. No live deployment or PDU connection was performed.

## 2026-10-07 — Kibana ingress with editable placeholders

Added optional Kibana-only ingress to [the active Elastic chart](monitoring/charts/elasticsearch-kibana/Chart.yaml), version 0.4.0. [The Kibana overlay](monitoring/kibana.yaml) enables routing with placeholder hostname/class, optional annotations and existing TLS Secret; chart defaults disable it. [The guide](monitoring/README.md#kibana-ingress) explains replacement, controller/DNS prerequisites, HTTPS and disabling ingress. Local Helm rendering verifies backend port/service, TLS, disabled Kibana/ingress and schema rejection; existing bootstrap checks pass. No cluster changes performed.

## 2026-10-07 — Kibana subpath routing

Updated [chart 0.5.0](monitoring/charts/elasticsearch-kibana/Chart.yaml) and [Kibana values](monitoring/kibana.yaml) to serve `/mid-cbf-kibana`. Ingress preserves the path; Kibana strips it internally and probes include it. Optional publicBaseUrl supports full external URLs; chart defaults retain root routing. [The guide](monitoring/README.md#kibana-ingress) explains URLs and avoiding proxy rewrites, grounded in Elastic's base-path documentation. Helm lint/render contracts verify paths, environment, probes, root defaults and invalid-path rejection; bootstrap regressions pass. No deployment performed.

## 2026-10-08 — Local-package host Filebeat role

Added [the standalone Debian/Ubuntu role and guide](monitoring/ansible/README.md), with controller-local apt package installation, Vault-compatible credentials-file loading and a root-only Jinja config. Documented system/auth defaults, optional journal/audit inputs, chart-compatible `filebeat-*` publishing, required per-version administrator setup and two-host troubleshooting. Linked it from [monitoring](monitoring/README.md) and the index. Local syntax/render checks are recorded in the task result; no live package installation, deployment or indexed delivery has been verified.

## 2026-10-08 — Journal-only Filebeat collection

Updated [the standalone role](monitoring/ansible/README.md) to collect only the systemd journal, retaining priority metadata and adding readable `log.level` values for priorities 0–7. Removed separate file/audit/application input defaults. Verified the PRIORITY translation against Elastic Beats v9.5.5 source; local syntax/render and executable priority mapping checks passed. No live deployment or delivery was verified.

## 2026-10-09 — NetBox-driven switch POAP starter

Added [the switch POAP bundle](end-to-end-netbox/development/switch-poap/README.md), using the existing NetBox lookup/credentials pattern. User-tested DHCP host-tag and option-67 forms define the templates; management-interface screenshots establish the MAC/IP source. All deployment paths, bootfile, gateway, credentials and NX-OS staging settings are variables. Cisco POAP references support serial-environment selection, checksum formatting and scheduled configuration. Offline tests and local HTTP-fixture execution verify rendering, validation, check mode and idempotence. Model/version compatibility and real DHCP, SSH login and configuration persistence remain unverified. No live Bifrost or switch changes were made.
