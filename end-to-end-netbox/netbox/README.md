# Empty NetBox deployment

This folder captures the community container configuration used for this demo,
with pinned images, localhost-only HTTP, persistent volumes, and restart policies.
Configuration files derive from netbox-community/netbox-docker release branch;
its Apache license is included. No private service environments are checked in.

Prerequisites: Docker and Docker Compose. From this folder:

```sh
python3 prepare-env.py
docker compose -p netbox-bootstrap -f compose.yml up -d
docker compose -p netbox-bootstrap -f compose.yml ps
```

First startup initializes the schema and can take several minutes. The web
service is available at http://127.0.0.1:8000. It starts without inventory or
an administrator. Create an administrator interactively:

```sh
docker compose -p netbox-bootstrap -f compose.yml exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py createsuperuser
```

Log in, create a write-enabled API token, and place its complete authentication
value in `../private/netbox.json` with the URL, as described in the demo README.
Modern tokens use the complete `nbt_...` value, not only the secret suffix.
Private files must be owner-readable only. Do not publish service secrets or tokens.

`prepare-env.py` refuses to replace existing secrets. Keep the `env` directory
and named volumes when restarting; never rotate these values accidentally.

## Existing verified instance

The current running instance still uses its original configuration in the
Codex workspace `netbox-runtime` directory. This copy does not restart or
replace it. Do not launch a second stack with the same project name and port.
To migrate the existing instance later, preserve its private environment and
volume identities, plan the application restart, and use this configuration.
The host must remain running.

The current instance has the one explicitly authorized Ubuntu demo device
and a private demo administrator/API token. HTTP is bound to localhost; use
an SSH tunnel to reach it from another computer.

Source: https://github.com/netbox-community/netbox-docker
