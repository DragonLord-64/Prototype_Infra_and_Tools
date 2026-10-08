# Repository knowledge base

[Knowledge-base change log](KNOWLEDGE_LOG.md)

This AGENTS.md tree is the knowledge-base index; recent edits are in the log. Existing READMEs and topic documents are
the wiki pages. Keep this a small Markdown layer, not a separate application.
Read the nearest directory's AGENTS.md before working there; preserve its
additional instructions.

## Index

| Area | Index | Overview |
| --- | --- | --- |
| Active Ansible/NetBox | [Pipeline index](end-to-end-netbox/AGENTS.md) | [Latest portable bundle](end-to-end-netbox/development/README.md) |
| Monitoring | [Beginner guide](monitoring/README.md) | [Component values and active chart](monitoring/) |
| Host Filebeat | [Standalone role](monitoring/ansible/README.md) | [Role defaults](monitoring/ansible/roles/filebeat/defaults/main.yml) |
| Historical prototypes | [Archive overview](archive/README.md) | [Original overview](archive/ORIGINAL_REPOSITORY_README.md) |

Inspired by [Karpathy’s LLM Wiki notes](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): persistent, source-grounded Markdown knowledge, ingest/query/lint workflows, and a chronological log. Here AGENTS.md combines the schema and navigation roles.

## Server safety

Never shut down, reboot, suspend, hibernate, halt, or power off the host,
even if asked. Never execute or schedule equivalent commands. Stop or restart
an application or service only when explicitly requested; leave the host running.

## Ingest — the primary workflow

1. Read the changed source and relevant existing documentation before writing.
2. Integrate new facts into the existing topic page; create a focused page only
   when the topic needs one. Link to the code, configuration, or external source
   supporting the claim. Distinguish intended behavior from verified results.
3. Update affected directory indexes and crosslinks. Avoid duplicating detailed
   instructions in indexes. Never ingest credentials, private inventories, or
   generated environment files.
4. Append a dated entry to KNOWLEDGE_LOG.md describing the documentation change,
   linking affected pages, and noting its evidence and any unresolved questions.
   This log records knowledge-base edits, not every provisioning or code event.

## Query

Navigate from this AGENTS.md index to relevant pages and inspect source when needed.
Answer with links to supporting documents; distinguish facts from inference and
report uncertainty. Save useful synthesis into the wiki only when requested.

## Lint

Check links, duplicated guidance, contradictions, stale claims, and missing
coverage. Compact repeated material into one canonical page with links. Replace
obsolete guidance with current evidence and explain the retirement in the log;
retain relevant provenance and Git history. Expand a topic only using evidence,
not guessed operational details. Do not remove unrelated material or rewrite the
whole repository. Documentation edits do not authorize running deployments.
