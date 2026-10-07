#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly venv="${script_dir}/.venv"

: "${NETBOX_URL:?Set NETBOX_URL to the NetBox base URL}"
: "${NETBOX_TOKEN:?Set NETBOX_TOKEN to a NetBox API token}"

if [[ ! -x "${venv}/bin/python" ]]; then
  python3 -m venv "${venv}"
  "${venv}/bin/pip" install -r "${script_dir}/requirements.txt"
fi

PYTHONPATH="${script_dir}" "${venv}/bin/python" -m netbox_import.cli "$@"
