# Air-Gapped Mirror System

A pod on the internet-connected side of the cluster (the "192 network")
that mirrors Git repos, Python packages, and apt packages for
internet-isolated worker nodes. Plain HTTP where possible, no TLS -- the
network is trusted and internal.

## Components

| Container | Role | Directory |
| --- | --- | --- |
| `git-daemon` | Read-only `git://` on 9418, unauthenticated | [`git-daemon/`](git-daemon) |
| `devpi` | Caching PyPI proxy -- caches on first `pip install` | [`devpi/`](devpi) |
| `apt-cacher-ng` | Caching apt proxy -- caches on first `apt install` | [`apt-cacher-ng/`](apt-cacher-ng) |
| sync | Reconcile loop, a sidecar in the same pod | [`sync-job/`](sync-job) |

All four run as one Deployment sharing volumes -- the sync loop is a
sidecar rather than a separate CronJob, so exactly one pod mounts the
volumes and `ReadWriteOnce` storage is enough. Deploy it with the Helm
chart -- see [`chart/README.md`](chart/README.md).

## Data ingress

| Content | How it's added |
| --- | --- |
| Git repos (public upstream) | Entry in `syncJob.repos` → `helm upgrade` → sync loop `git clone --mirror` / `git remote update` |
| Python / apt packages | Not pre-populated -- devpi/apt-cacher-ng cache on first client request |

## Configuration

The repos to mirror are listed in the chart's values:

```yaml
syncJob:
  enabled: true
  repos:
    - name: widgets
      url: https://github.com/your-org/widgets.git
      dest: your-org/widgets
```

Helm renders that into a ConfigMap and mounts it into the sync sidecar at
`/etc/mirror/git-repos.yaml`. `helm upgrade` is the whole config path:
there is no separate config repo, nothing to clone, and no credentials
anywhere in the system.

Because the manifest is a mounted ConfigMap rather than a file baked into
the image, the kubelet refreshes it in place. The sync loop re-reads it
every pass, so a changed repo list applies without restarting the pod --
though not instantly: the kubelet takes up to ~60s to push the new file
into the container, and the next pass acts on it after that.

**No API, no webhooks, no state.** Every `intervalSeconds`, the sidecar
re-reads the manifest and makes the git volume match it. Nothing is
remembered between passes, so there is no cursor to corrupt and no event
to miss -- a pass that fails just runs again.

## Repo layout

```
air-gapped-mirror/
├── chart/                 Helm chart -- the supported way to deploy
├── test/                  Minikube smoke test (up.sh / verify.sh / down.sh)
├── git-daemon/            Dockerfile
├── devpi/                 Dockerfile + entrypoint
├── apt-cacher-ng/         Dockerfile + acng.conf
└── sync-job/              The sync sidecar's image: source + tests
```

## The sync loop (`sync-job/`)

The only component with real logic, so it's a small Python package rather
than a shell script:

- `mirror_sync/manifest.py` -- loads/validates the git-repo manifest
  (rejects path traversal, bad URL schemes, duplicates)
- `mirror_sync/sync.py` -- git mirror/update reconciliation and the
  `sync_forever` loop the container runs

The subprocess runner and sleep are injected rather than hardcoded, so
the tests run without a cluster.

### Running the tests

```sh
cd air-gapped-mirror/sync-job
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

- `tests/test_manifest.py`, `tests/test_sync.py` -- unit tests against
  fakes/mocks (no network, no real git)
- `tests/test_integration.py` -- runs `run_sync()` end to end against a
  real `git daemon` serving a bare repo over `git://`. Covers first-pass
  population, second-pass idempotency, picking up a new upstream commit,
  and the `sync_forever` loop driving all of it repeatedly.

`tests/test_integration.py` needs a real `git daemon` binary: on Debian/
Ubuntu it ships in `git-daemon-run`, on Alpine in `git-daemon`. Without
it those tests fail with "Connection refused" rather than a
missing-binary error.

## Building the images

```sh
cd air-gapped-mirror
for i in git-daemon devpi apt-cacher-ng sync-job; do
  docker build -t air-gapped-mirror/$i:latest $i
done
```

These bare names are what the chart expects by default. Load them onto
the node afterwards -- see [`chart/README.md`](chart/README.md) step 1.

[`test/`](test) builds all four, deploys the chart to a throwaway
minikube cluster, and exercises every component end to end.

## Deploying

Use the Helm chart -- **[`chart/README.md`](chart/README.md) is the
step-by-step guide**, written for someone new to Kubernetes:

```sh
helm install air-gapped-mirror ./chart \
  --namespace air-gapped-mirror --create-namespace
```

No registry is needed: build the images locally, load them onto the node
(`minikube image load`, `kind load docker-image`, or `k3s ctr images
import`), and the chart's defaults pick them up by bare name.

There are no hand-written manifests to keep in sync -- `helm template`
renders the plain YAML if you want to read or diff it.

`ReadWriteOnce` storage is sufficient: the sync sidecar shares the mirror
pod, so nothing else mounts those volumes.

## Security notes

- `git-daemon`, `devpi`, `apt-cacher-ng` are unauthenticated and
  unencrypted by design -- only safe because the 192 network is internal
  and trusted.
- The mirror holds no credentials at all: everything it mirrors is public
  open source, and the repo list is a plain ConfigMap. What needs guarding
  is write access to the chart values -- changing `syncJob.repos` means
  "can point the sync loop at an arbitrary URL".
- `mirror_sync.manifest` rejects absolute paths, `..` traversal, and
  URL schemes outside http(s)/git/ssh on every entry, so a bad value
  cannot write outside the bare-repo root.
