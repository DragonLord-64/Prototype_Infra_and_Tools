# Running the minikube test on a restricted host

Everything here exists for one reason: to run [`../up.sh`](../up.sh)'s test on
a host whose egress policy and container sandbox are tighter than a laptop's.
Nothing in this directory is part of the mirror system, and none of it changes
what production deploys — the chart, the sync loop, and the four component
Dockerfiles are used as-is.

Skip this directory entirely if `../up.sh` already works for you.

## What was actually blocked

| Blocked | Effect | Handled by |
| --- | --- | --- |
| `dl-cdn.alpinelinux.org`, `deb.debian.org` (403 at the egress proxy) | `apk add` / `apt-get install` fail in every image build | Dockerfile overlays here, built from `ubuntu:24.04`, whose archive *is* reachable |
| Docker Hub blob CDN (`production.cloudfront.docker.com`) | `FROM alpine:3.20` etc. cannot pull | `"registry-mirrors": ["https://mirror.gcr.io"]` in the host's `/etc/docker/daemon.json` |
| TLS re-terminated by the egress proxy | `git clone https://…` and `pip install` fail with "certificate signer not trusted" | `build.sh` takes a CA bundle and bakes it into the images that make outbound calls |
| Lowering `oom_score_adj` (EPERM even for root) | every kubelet pod sandbox dies with `can't get final child's PID from pipe: EOF` | `kicbase/` — a runc shim on the minikube node |
| `RLIMIT_NOFILE` above the sandbox's own hard limit | same failure; kicbase asks dockerd for 1048576 | same runc shim |

## Contents

| Path | What it is |
| --- | --- |
| `build.sh` | Builds all four images at the tags `../up.sh` expects, using the overlays below |
| `git-daemon.Dockerfile`, `apt-cacher-ng.Dockerfile` | Same runtime contract as production; Ubuntu base instead of Alpine/Debian |
| `sync-job.Dockerfile` | Same, on `python:3.11` (which already ships git and openssh-client), plus the CA step |
| `devpi.Dockerfile` | Production Dockerfile plus the CA step — nothing else differs |
| `kicbase/` | `gcr.io/k8s-minikube/kicbase` + a runc shim that strips negative `oomScoreAdj` and clamps `RLIMIT_NOFILE` out of the OCI spec |
| `10-fixtures.yaml` | `../manifests/10-fixtures.yaml` with the seed step taking git from the built image instead of `apk add` |
| `test-client.Dockerfile` | The client pod `../verify.sh` runs, with git/curl/pip preinstalled |

The runc shim rewrites two fields the sandbox refuses to honour and then
`exec`s the real runc. It handles both `runc create` (spec at
`<bundle>/config.json`) and `runc exec` (process block via `--process`) —
without the latter, pods start but `kubectl exec` fails.

## Running it

```sh
cd air-gapped-mirror/test/restricted

# 1. host docker: mirror Docker Hub through a reachable mirror
cat /etc/docker/daemon.json    # {"registry-mirrors": ["https://mirror.gcr.io"]}

# 2. build the four images (pass the proxy CA if TLS is re-terminated)
./build.sh /path/to/ca-bundle.crt

# 3. node image with the runc shim
docker build -t local/kicbase-sandboxed:v0.0.50 kicbase

# 4. cluster
minikube -p air-mirror-test start --driver=docker --force \
  --base-image=local/kicbase-sandboxed:v0.0.50 \
  --cpus=3 --memory=4096mb --disk-size=20g

# 5. load images, deploy, verify
docker build -t air-gapped-mirror/test-client:test -f test-client.Dockerfile .
for i in git-daemon devpi apt-cacher-ng sync-job test-client; do
  minikube -p air-mirror-test image load air-gapped-mirror/$i:test
done
kubectl apply -f ../manifests/00-namespace.yaml
kubectl apply -f 10-fixtures.yaml
helm upgrade --install mirror ../../chart -n air-gapped-mirror \
  -f ../values-test.yaml -f ../values-real-repo.yaml

CLIENT_IMAGE=air-gapped-mirror/test-client:test ../verify.sh
CLIENT_IMAGE=air-gapped-mirror/test-client:test ../verify-real-repo.sh
```

`../verify.sh`'s devpi and apt-cacher-ng checks report SKIP here: they proxy to
`pypi.org` and `deb.debian.org`, and this host's policy does not let the
cluster reach them. That is the documented best-effort behaviour of those two
checks, not a mirror failure. The git checks are unaffected.
