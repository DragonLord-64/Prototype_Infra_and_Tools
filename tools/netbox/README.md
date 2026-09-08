# NetBox tools

- [`csv-import/`](csv-import/) imports inventory workbooks into an existing
  NetBox instance.
- [`inventory-collector/`](inventory-collector/) uses Ansible to collect Linux
  server hardware and produces CSV files for that importer.

Add future CSV exporters beside the importer so deployment configuration and
data operations remain independent.
