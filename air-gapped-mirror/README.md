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
| `ssh-upload` | No-shell, chrooted SFTP for local-file uploads | [`ssh-upload/`](ssh-upload) |
| sync job | `CronJob`, not a container in the pod | [`sync-job/`](sync-job) |

The first five run as one Deployment (`k8s/mirror.yaml`) sharing
`ReadWriteMany` volumes. The sync job runs on a schedule, polling the
public GitLab API and reconciling those volumes against manifests in a
private GitLab repo (the "config repo").

## Data ingress

| Content | How it's added |
| --- | --- |
| Git repos (public upstream) | Manifest entry in config repo → MR → sync job `git clone --mirror` / `git remote update` |
| Tarballs/binaries (public upstream) | Manifest entry (URL + dest) in config repo → MR → sync job downloads it |
| Local-only (192 network) files | Direct SCP/SFTP into the shared volume, any path -- no manifest, no MR |
| Python / apt packages | Not pre-populated -- devpi/apt-cacher-ng cache on first client request |

## GitLab as the control plane

A **private** GitLab repo holds the three manifests the sync job reads:
the git-repo manifest, the tarball manifest, and the SSH public-key
manifest for everyone with upload access (format documented in
`mirror_sync/manifest.py`). Changes go through merge requests for review
and an audit trail. It must stay private -- merge access there means "can
point the sync job at an arbitrary URL" and "can grant SSH upload access."

GitLab is public SaaS and the sync pod has no public endpoint, so an
inbound webhook isn't viable without a publicly reachable relay (rejected
as unnecessary complexity). The `CronJob` polls the merge-requests API
instead; each run logs what merged since the last one for audit
visibility, then reconciles from the manifests at HEAD regardless (see
`mirror_sync.sync.run_sync`).

## Repo layout

```
air-gapped-mirror/
├── k8s/mirror.yaml        Namespace, storage, deployment, service, CronJob
├── k8s/secret.example.yaml  Template for the sync job's GitLab credentials
├── git-daemon/            Dockerfile
├── nginx/                 nginx.conf (autoindex on, no auth)
├── devpi/                 Dockerfile + entrypoint
├── apt-cacher-ng/         Dockerfile + acng.conf
├── ssh-upload/            Dockerfile, sshd_config, entrypoint
└── sync-job/              The CronJob's image: source + tests
```

## The sync job (`sync-job/`)

The only component with real logic, so it's a small Python package rather
than a shell script:

- `mirror_sync/manifest.py` -- loads/validates the three YAML manifests
  (rejects path traversal, bad URL schemes, malformed keys, duplicates)
- `mirror_sync/sync.py` -- GitLab MR polling, git mirror/update
  reconciliation, tarball diff-and-download with atomic writes,
  `authorized_keys` regeneration, state tracking, and the `run_sync`
  orchestration used by the CronJob's entrypoint

Every side effect (subprocess runner, HTTP downloader, GitLab session) is
passed in rather than hardcoded, which is what makes the tests below
possible without a real cluster.

### Running the tests

```sh
cd air-gapped-mirror/sync-job
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

44 tests, all passing:

- `tests/test_manifest.py`, `tests/test_sync.py` -- unit tests against
  fakes/mocks (no network, no real git)
- `tests/test_integration.py` -- runs `run_sync()` end to end against
  **real** subprocesses and network calls: a real `git daemon` process
  (the same binary the `git-daemon` container runs) serving a bare repo
  over `git://`, a real `http.server` thread serving a tarball, and a
  real config-repo checkout. Covers first-run population, second-run
  idempotency, state advancing past merged MRs, and picking up a new
  upstream commit on the next run.

## Building the images

```sh
cd air-gapped-mirror
docker build -t air-gapped-mirror/git-daemon git-daemon
docker build -t air-gapped-mirror/devpi devpi
docker build -t air-gapped-mirror/apt-cacher-ng apt-cacher-ng
docker build -t air-gapped-mirror/ssh-upload ssh-upload
docker build -t air-gapped-mirror/sync-job sync-job
```

**Sandbox note:** in the environment this was built in, outbound Docker
Hub pulls are blocked by the egress policy (`alpine`/`python`/`nginx` base
image pulls all 403 through the proxy) -- this affects this repo's
pre-existing top-level `Dockerfile` too, not just this feature. So none of
the builds above could actually run here. What *was* verified in this
sandbox: every Dockerfile/config reviewed by hand; `k8s/*.yaml` parses and
structurally validates; and the sync job's actual logic has full unit +
integration coverage, including against a real `git daemon` and a real
HTTP server (above). In an environment with normal registry access, the
builds above should just work.

## Deploying

```sh
kubectl apply -f k8s/mirror.yaml
# copy k8s/secret.example.yaml to k8s/secret.yaml (gitignored), fill in
# real values, then:
kubectl apply -f k8s/secret.yaml
```

Swap `REGISTRY/air-gapped-mirror/*` in `k8s/mirror.yaml` for wherever you
push the images built above. The PVCs need a storage class supporting
`ReadWriteMany` (e.g. NFS-backed) since the Deployment and the CronJob
mount the same volumes concurrently.

## Security notes

- `git-daemon`, `nginx`, `devpi`, `apt-cacher-ng` are unauthenticated and
  unencrypted by design -- only safe because the 192 network is internal
  and trusted.
- Public keys in the config repo aren't a risk -- they're meant to be
  public. The config repo itself is the sensitive asset; keep it private,
  restrict approvers.
- `ssh-upload` trades strict isolation for convenience on purpose: one
  low-privilege `uploader` account, chrooted straight to the nginx-served
  root, so anyone with upload access can write anywhere in that tree.
  Fine for a small, trusted team.
- `mirror_sync.manifest` rejects absolute paths, `..` traversal, and
  non-http(s)/git/ssh URL schemes on every entry; `sync_tarballs`
  re-checks the resolved destination stays under the artifacts root as
  defense in depth.
