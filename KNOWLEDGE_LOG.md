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

Added the [alert provisioning template](monitoring/node-exporter-slack.yaml), [Helm mount/Secret example](monitoring/grafana-helm-values.example.yaml), and [usage guide](monitoring/README.md). Evidence: current Grafana documentation/provisioning schema and FHS Baremetal node job template. Failed scrapes alert after two minutes; missing inventory targets remain a separate coverage requirement. YAML/schema checks are isolated; no cluster deployment or Slack message was performed.

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
