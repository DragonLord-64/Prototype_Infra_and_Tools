# Infrastructure prototypes and tools

[Knowledge-base change log](KNOWLEDGE_LOG.md) · [Knowledge-base index](AGENTS.md)

The active work is the portable Ansible/NetBox inventory pipeline and the monitoring design for the SKA FHS bare-metal repository.

| Area | Purpose |
| --- | --- |
| [NetBox pipeline](end-to-end-netbox/README.md) | Existing discovery, simulators, and local NetBox/test-container setup |
| [Portable development bundle](end-to-end-netbox/development/README.md) | Latest reviewed imports, role layout, and offline tests to copy to FHS Baremetal |
| [Monitoring](monitoring/README.md) | Storage/deployment design and Grafana Slack alert template; no deployed chart yet |
| [Historical archive](archive/README.md) | Previous platform, workloads, host automation, utilities, and default environment |

Only source and wiki documents were relocated. Ignored credentials, environments, generated output, and runtime data remain at their original paths. No running service was restarted or redeployed. Some historical directory names may therefore still exist locally.

For the latest inventory work, start with the portable bundle README. The existing end-to-end entrypoints and fixtures remain available for regression testing. Archive scripts are retained for reference; read the archive usage limitations before running them.
