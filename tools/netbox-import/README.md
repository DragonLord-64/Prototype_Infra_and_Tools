# NetBox Import

A small Python tool that reads a spreadsheet of your existing lab
inventory and pushes it into a running NetBox instance via its REST API
(`pynetbox`), instead of hand-entering everything through the UI.

Assumes NetBox is already deployed and reachable -- this only talks to
its API.

## Quick start

```sh
cd netbox-import
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

cp template/inventory-template.xlsx my-inventory.xlsx
# fill in my-inventory.xlsx (see "The workbook format" below), then:

export NETBOX_URL=https://netbox.lab.internal
export NETBOX_TOKEN=your-api-token   # needs write access to dcim + ipam

.venv/bin/python -m netbox_import my-inventory.xlsx --dry-run   # preview
.venv/bin/python -m netbox_import my-inventory.xlsx             # apply
```

`--dry-run` looks up everything against the live NetBox instance and
reports what would be created, without writing anything.

## The workbook format

`template/inventory-template.xlsx` is a ready-to-fill starting point --
one tab per object type, headers in row 1, an example row in row 2
(delete it), a `ReadMe` tab summarizing required columns. Regenerate it
with `python3 make_template.py` if you change the schema below.

Every tab is optional -- only fill in the ones you have data for. They're
synced in dependency order regardless of tab order in the file:

| Sheet | Required columns | Optional columns |
| --- | --- | --- |
| `Manufacturers` | `name` | `slug` |
| `DeviceRoles` | `name` | `slug`, `color` (hex, no `#`) |
| `DeviceTypes` | `manufacturer`, `model` | `slug`, `u_height` |
| `Sites` | `name` | `slug`, `status` |
| `Racks` | `name`, `site` | `status`, `u_height` |
| `Devices` | `name`, `device_type`, `role`, `site` | `rack`, `position`, `face`, `status`, `serial` |
| `VLANs` | `vid`, `name` | `site`, `status` |
| `Prefixes` | `prefix` | `site`, `status`, `description` |
| `IPAddresses` | `address` | `device`, `interface` (default `eth0`), `status`, `primary` (`true`/`false`) |

References between sheets are by name (e.g. a `Devices` row's `site`
column is the `Sites` row's `name`) -- the tool resolves those to NetBox
IDs itself. `manufacturer`, `role`, `device_type`, `rack`, `site`, and
`device` values must match a `name`/`model` already defined earlier in
the workbook (or already existing in NetBox).

## Idempotency

Every object is looked up by its natural key first (slug, name+site,
prefix, IP address, etc.) and only created if missing -- **existing
objects are never modified**. Re-running the same or a grown workbook is
safe, and so is hand-editing objects in NetBox afterward; a later import
won't overwrite your changes. Row-level errors (e.g. an unknown site
name) are collected and reported at the end rather than aborting the
whole run -- everything else still gets synced.

## NetBox version note

This tool targets NetBox 4.0+ by default (`role` is a device's role
field). If you're on an older NetBox (< 4.0, where it's `device_role`),
change `DEVICE_ROLE_FIELD` at the top of `netbox_import/sync.py`.

## Running the tests

```sh
cd netbox-import
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

Tests run against `tests/fakes.py` (no network, no real NetBox) and cover
dependency-ordered creation, idempotent re-runs, dry-run writing nothing,
unrecognized references being reported instead of raising, and the
workbook parser's validation/blank-row handling.

## Security notes

- The API token needs write access to `dcim` and `ipam` -- scope it to
  those apps only if your NetBox instance supports token permissions,
  rather than handing this tool a superuser token.
- `NETBOX_URL`/`NETBOX_TOKEN` are read from the environment, never
  written to a file in this repo -- keep them out of the workbook too.
