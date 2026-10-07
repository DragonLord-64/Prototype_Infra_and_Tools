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

Moved older tracked platform, deployments, automation, utilities, and default-environment source into [archive](archive/README.md), preserving their wiki indexes and history. Kept the existing [NetBox pipeline](end-to-end-netbox/README.md) and latest development bundle active. Added the source-grounded [monitoring design](monitoring/DESIGN.md). Ignored private/runtime files stayed at their original paths; no deployment or service action occurred. Relative documentation links were updated; historical scripts still require a path review before reuse.

## 2026-10-06 — Grafana node-exporter Slack template

Added the [alert provisioning template](monitoring/node-exporter-slack.yaml), [Helm mount/Secret example](monitoring/reference/grafana-helm-values.example.yaml), and [usage guide](monitoring/README.md). Evidence: current Grafana documentation/provisioning schema and FHS Baremetal node job template. Failed scrapes alert after two minutes; missing inventory targets remain a separate coverage requirement. YAML/schema checks are isolated; no cluster deployment or Slack message was performed.

## 2026-10-06 — FPGA SDK parser formatting compatibility

Aligned [portable FHS SDK parser defaults](end-to-end-netbox/development/README.md) with the known-working source grammar (variable indentation and index suffixes). Added field-name-only diagnostics and a regression test using packaged defaults; physical output confirmation remains pending.

## 2026-10-06 — Published SDK sample validation

Validated the [FHS parser](end-to-end-netbox/development/README.md) against the newly published public SDK/QSFP sample. Corrected full alphanumeric serial matching and retained variable indentation. Added sanitized output-shape fixtures and copied-layout tests using them; FPGA optics remain unimported. No live hardware commands were run.

## 2026-10-06 — Opt-in SDK discovery debugging

Added [SDK debugging instructions](end-to-end-netbox/development/README.md), gated command-output diagnostics before normalization, and explicit failed-exit validation. Restored the source target PATH after venv prefixes and documented how old generic error wording identifies a stale filter copy. Synthetic tests cover debug output and stopping before parse/API changes on SDK failure.

## 2026-10-06 — Physical NIC module discovery

Extended [the portable FHS bundle](end-to-end-netbox/development/README.md) with sample-grounded ethtool driver/firmware/PCI/link parsing and existing PCI VPD card identity. Documented verified serial+part grouping, explicit virtual-port exclusions, safe interface adoption and partial-data preservation. No automatic optics/DAC/cable imports or destructive legacy migration. Synthetic parser, multiport and copied-layout check/apply/idempotence tests cover the change; physical NIC smoke verification remains pending.

## 2026-10-06 — Latest John switch setup

Fetched the public SKA prototyping repository and selected John So's monitoring branch. Copied its current [switch monitoring inputs](monitoring/upstream-switch/README.md), preserving source identity and unchanged values/dashboard. No cluster deployment or persistence change was performed.

## 2026-10-06 — Persistent monitoring configuration and Elastic chart

Added [Prometheus persistence values](monitoring/PERSISTENCE.md) with a 50G requested PVC, editable nfss1 candidate class, retention headroom, and a single writer. Storage backend is unverified; Prometheus NFS incompatibility is explicit. Added a [fresh-install Elastic Helm chart](monitoring/elastic-small/README.md), matching Docker Hub Elasticsearch/Kibana9.5.5 digests, existing Secret references, and bounded Kibana service-user setup. Helm lint/render/schema and isolated resource checks passed. No cluster deployment, existing-data upgrade, volume migration, or log delivery test occurred.

## 2026-10-06 — NetBox manufacturer IDs and bounded service retries

Updated [both portable imports](end-to-end-netbox/development/README.md) to ensure reported manufacturers and use returned vendor/type IDs, preserving custom slugs and avoiding guessed vendor aliases. Added server write serialization, object-loop pacing and current-result bounded transient502/503/504 retries; permanent400 remains immediate. Synthetic manufacturer and actual Ansible retry/copy-layout/Nexus task tests passed. Underlying live503 cause remains unconfirmed; imports should run separately.

## 2026-10-06 — First implementation run guide

Shortened the [portable FHS bundle guide](end-to-end-netbox/development/README.md) to real-environment setup and execution: whole-directory copying including shared module utilities, Bifrost credential paths, inventory overrides, scoped imports and export handoff. Removed explanatory code comments and outdated task labels without changing functionality. Python syntax-tree equivalence and YAML equivalence apart from task labels verified behavior preservation; published implementation tests remain intact. The operator confirmed FPGA/NIC import on one server; fleet and cluster validation remain separate.

## 2026-10-06 — Nexus manufacturer query contract

Corrected [Nexus module-type lookup](end-to-end-netbox/development/README.md): numeric manufacturer IDs use the manufacturer_id filter, while manufacturer is a slug filter. Restored native installed-module ID filter defaults to avoid the same override problem for module bays. Added real installed-collection builder and strict isolated request/copy-layout regressions; no live cluster actions or manufacturer deletion.

## 2026-10-06 — Unified monitoring Helm bundle

Consolidated [the monitoring stack](monitoring/reference/umbrella/README.md) into a dependency-locked umbrella chart for namespace mid-cbf-monitoring. One values list contains the eight supplied server addresses with node9100/custom9101(provisional), separate scrape jobs, and no added server-side exporters. Updated persistence to user-confirmed bds1 Ceph RBD: Prometheus requests50G and retains blocks up to37GB. Preserved John's queries/tables in a classic dashboard provisioning adaptation with a stable data-source UID. Slack remains disabled pending administrator Secret; no live releases/data/volumes changed. Helm lint/render/contracts validate targets, service/namespace wiring, storage limits, pinned Docker Hub images, optionalSlack and disabled components.

## 2026-10-06 — Transparent per-component monitoring values

Replaced the default umbrella interface with [visible component values](monitoring/README.md) and a render-only helper. All eight node/custom target pairs are explicit in the Prometheus file; bds1/50G/37GB/15d settings are retained. Existing Grafana is excluded by default and optional values do not adopt its release. The prior umbrella and samples remain [historical references](monitoring/reference/umbrella/README.md). Documented that Prometheus/Telegraf endpoints currently have no authentication and Telegraf has no UI/default login. Local rendering/contracts validate unchanged targets/storage and absence of Grafana from default output; no live cluster operation occurred.
