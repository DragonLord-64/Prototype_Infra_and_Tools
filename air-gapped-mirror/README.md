# Air-Gapped Mirror System

A pod on the internet-connected side of the cluster (the "192 network")
that mirrors Git repos, tarballs/binaries, Python packages, and apt
packages for internet-isolated worker nodes. Plain HTTP where possible, no
TLS -- the network is trusted and internal.

## Components

| Container | Role | Directory |
| --- | --- | --- |
| `git-daemon` | Read-only `git://` on 9418, unauthenticated | [`git-daemon/`](git-daemon) |
| `nginx` | Directory listing of tarballs/binaries over HTTP | [`nginx/`](nginx) |
| `devpi` | Caching PyPI proxy -- caches on first `pip install` | [`devpi/`](devpi) |
| `apt-cacher-ng` | Caching apt proxy -- caches on first `apt install` | [`apt-cacher-ng/`](apt-cacher-ng) |
| sync | Reconcile loop, a sidecar in the same pod | [`sync-job/`](sync-job) |

All five run as one Deployment sharing volumes -- the sync loop is a
sidecar rather than a separate CronJob, so exactly one pod mounts the
volumes and `ReadWriteOnce` storage is enough. Deploy it with the Helm
chart -- see [`chart/README.md`](chart/README.md).

The mirror covers git, apt, and pip. An earlier design also had an
`ssh-upload` container (a no-shell, chrooted SFTP endpoint for pushing
local-only files straight into the nginx-served volume); it was never
deployed and has been removed. It needed `/var/mirror/files` pinned to
`root:root 755` for sshd's `ChrootDirectory` check, which conflicts with
the non-root sync loop writing to that same volume. The code is preserved
on the `archive/ssh-upload` branch.

## Data ingress

| Content | How it's added |
| --- | --- |
| Git repos (public upstream) | Manifest entry in config repo → MR → sync loop `git clone --mirror` / `git remote update` |
| Tarballs/binaries (public upstream) | Manifest entry (URL + dest) in config repo → MR → sync loop downloads it |
| Python / apt packages | Not pre-populated -- devpi/apt-cacher-ng cache on first client request |

## The config repo as the control plane

A **private** git repo holds the two manifests the sync loop reads: the
git-repo manifest and the tarball manifest (format documented in
`mirror_sync/manifest.py`). Changes go through merge
requests for review and an audit trail. It must stay private -- merge
access there means "can point the sync loop at an arbitrary URL."

**No GitLab API, no webhooks, no state.** The sync sidecar re-clones (then
re-fetches) the config repo every `intervalSeconds`, reads the manifests at
HEAD, and makes the volumes match. Nothing is remembered between passes, so
there is no cursor to corrupt and no event to miss -- a pass that runs
after a change picks it up, and a pass that fails just runs again.

That also means the only credential the mirror needs is whatever `git
clone` needs for the config repo. An earlier version polled GitLab's
merge-requests API for an audit log; it was removed because it added a
token that could expire (and once did, aborting the whole sync) in
exchange for information already in the config repo's git history.

## Repo layout

```
air-gapped-mirror/
├── chart/                 Helm chart -- the supported way to deploy
├── test/                  Minikube smoke test (up.sh / verify.sh / down.sh)
├── git-daemon/            Dockerfile
├── nginx/                 nginx.conf (autoindex on, no auth)
├── devpi/                 Dockerfile + entrypoint
├── apt-cacher-ng/         Dockerfile + acng.conf
└── sync-job/              The sync sidecar's image: source + tests
```

## The sync loop (`sync-job/`)

The only component with real logic, so it's a small Python package rather
than a shell script:

- `mirror_sync/manifest.py` -- loads/validates the two YAML manifests
  (rejects path traversal, bad URL schemes, duplicates)
- `mirror_sync/sync.py` -- git mirror/update reconciliation, tarball
  diff-and-download with atomic writes, and the `sync_forever` loop the
  container runs

Every side effect (subprocess runner, HTTP downloader, sleep) is passed in
rather than hardcoded, which is what makes the tests below possible
without a real cluster.

### Running the tests

```sh
cd air-gapped-mirror/sync-job
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

`tests/test_integration.py` shells out to a real `git daemon`. On Debian/
Ubuntu that binary ships in `git-daemon-run`; on Alpine it's the separate
`git-daemon` package. Without it those tests fail with a confusing
"Connection refused" rather than a missing-binary error.

30 tests, all passing:

- `tests/test_manifest.py`, `tests/test_sync.py` -- unit tests against
  fakes/mocks (no network, no real git)
- `tests/test_integration.py` -- runs `run_sync()` end to end against
  **real** subprocesses and network calls: a real `git daemon` process
  (the same binary the `git-daemon` container runs) serving a bare repo
  over `git://`, a real `http.server` thread serving a tarball, and a
  real config-repo checkout. Covers first-pass population, second-pass
  idempotency, picking up a new upstream commit on the next pass, and the
  `sync_forever` loop driving all of it repeatedly.

## Building the images

```sh
cd air-gapped-mirror
docker build -t air-gapped-mirror/git-daemon git-daemon
docker build -t air-gapped-mirror/devpi devpi
docker build -t air-gapped-mirror/apt-cacher-ng apt-cacher-ng
docker build -t air-gapped-mirror/sync-job sync-job
```

All four images have since been built and run for real: see
[`test/`](test), which deploys this chart to a throwaway minikube cluster
and exercises every component end to end (`test/verify.sh`).

## Deploying

Use the Helm chart -- **[`chart/README.md`](chart/README.md) is the
step-by-step guide**, written for someone new to Kubernetes:

```sh
helm install air-gapped-mirror ./chart \
  --namespace air-gapped-mirror --create-namespace \
  --set image.registry=registry.example.com --set image.tag=0.1.0
```

There are no hand-written manifests to keep in sync -- `helm template`
renders the plain YAML if you want to read or diff it.

`ReadWriteOnce` storage is sufficient: the sync sidecar shares the mirror
pod, so nothing else mounts those volumes.

## Security notes

- `git-daemon`, `nginx`, `devpi`, `apt-cacher-ng` are unauthenticated and
  unencrypted by design -- only safe because the 192 network is internal
  and trusted.
- The config repo is the sensitive asset -- merge access there means "can
  point the sync loop at an arbitrary URL". Keep it private, restrict
  approvers.
- `mirror_sync.manifest` rejects absolute paths, `..` traversal, and
  non-http(s)/git/ssh URL schemes on every entry; `sync_tarballs`
  re-checks the resolved destination stays under the artifacts root as
  defense in depth.
