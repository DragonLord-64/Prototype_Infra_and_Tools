# End-to-end NetBox knowledge

[Knowledge-base change log](../KNOWLEDGE_LOG.md) · [Top-level index](../AGENTS.md)

Follow [the repository workflow](../AGENTS.md) for ingest, query, and lint.
This file is the directory’s knowledge-base index.

Keep discovery, metadata mapping, and export knowledge here. Distinguish simulated-container tests from real hardware verification; never ingest private credentials or inventories.

## Index

- [Module-aware FHS dynamic inventory](development/MODULE_INVENTORY.md)

- [Current portable FHS playbook bundle, FPGA/NIC modules](development/README.md)

- [Pipeline and server metadata](README.md)
- [Real-server run guide](REAL_SERVER_RUN.md)
- [Inventory snapshots](INVENTORY_SNAPSHOT.md)
- [Bifrost export](BIFROST_EXPORT.md)
- [FPGA extension](FPGA_EXTENSION.md)
- [Nexus switch inventory](NEXUS.md)
- [Local NetBox deployment](netbox/README.md)
- [Server metadata example](server-info.example.yaml)

For knowledge changes, update relevant topic pages and this index, then append
to [the knowledge-base log](../KNOWLEDGE_LOG.md).

- [DHCP, POAP SSH bootstrap, and Ansible takeover](NEXUS.md#dhcp-poap-ssh-bootstrap-and-ansible-takeover) — two playbooks and one shared script, using the existing native NetBox inventory.
