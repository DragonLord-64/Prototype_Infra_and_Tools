#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

python3 -m venv "$script_dir/.venv"
"$script_dir/.venv/bin/python" -m pip install -r "$script_dir/requirements.txt"
"$script_dir/.venv/bin/ansible-galaxy" collection install -r "$script_dir/requirements.yml"

printf 'Ansible environment is ready at %s/.venv\n' "$script_dir"
