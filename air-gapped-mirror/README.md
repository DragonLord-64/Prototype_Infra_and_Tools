# Air-gapped mirror

This prototype runs Git, Python, and apt mirrors in one Kubernetes pod for
clients that cannot reach the internet. The containers share persistent
volumes; a Python sidecar periodically reconciles configured Git repositories,
while devpi and apt-cacher-ng populate their caches on demand.

## Layout

| Path | Purpose |
| --- | --- |
| [`chart/`](chart/) | Helm chart and deployment instructions |
| [`git-daemon/`](git-daemon/) | Read-only `git://` service |
| [`devpi/`](devpi/) | PyPI caching proxy |
| [`apt-cacher-ng/`](apt-cacher-ng/) | apt caching proxy |
| [`sync-job/`](sync-job/) | Git manifest validation and reconciliation |
| [`test/`](test/) | Disposable Minikube smoke test |
| [`setup-proxy-source.yml`](setup-proxy-source.yml) | Ansible playbook for configuring client hosts |

## Quick start

From the repository root:

```sh
for image in git-daemon devpi apt-cacher-ng sync-job; do
  docker build -t "air-gapped-mirror/$image:latest" "air-gapped-mirror/$image"
  minikube image load "air-gapped-mirror/$image:latest"
done

helm upgrade --install air-gapped-mirror ./air-gapped-mirror/chart \
  --namespace air-gapped-mirror --create-namespace
```

Git synchronization is disabled by default. Enable it in a values file:

```yaml
syncJob:
  enabled: true
  repos:
    - name: widgets
      url: https://github.com/your-org/widgets.git
      dest: your-org/widgets
```

Apply the file with `helm upgrade ... -f my-values.yaml`. See the
[`chart` guide](chart/README.md) for client endpoints and settings.

Client machines can be configured with Ansible after replacing the example
DNS and Git values in `setup-proxy-source.yml`:

```sh
ansible-playbook -i inventory.ini air-gapped-mirror/setup-proxy-source.yml
```

## Tests

```sh
cd air-gapped-mirror/sync-job
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

The integration test requires `git daemon`. For a complete cluster test, use
the scripts documented in [`test/README.md`](test/README.md).

## Security

The services use unauthenticated, unencrypted protocols and must only be
exposed on a trusted network. Restrict who may change Helm values: Git sources
are fetched by the sync sidecar. The manifest parser limits supported URL
schemes and rejects absolute or traversing destination paths, but it is not a
substitute for network policy. Do not place credentials in committed values or
repository URLs.
