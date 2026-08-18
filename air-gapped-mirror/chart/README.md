# Deploying the mirror with Helm

Helm is a package manager for Kubernetes. This directory is a *chart*: a
bundle of templated manifests plus a `values.yaml` of settings.

## 1. Get the images onto the cluster

No registry is involved: build the four images locally, then load them
onto the node the cluster runs on.

Build, then load in the same loop — this is the minikube version:

```sh
cd ..
for i in git-daemon devpi apt-cacher-ng sync-job; do
  docker build -t air-gapped-mirror/$i:latest $i
  minikube image load air-gapped-mirror/$i:latest
done
```

Swap the load line for whatever your cluster uses:

| Cluster | Load line |
| --- | --- |
| minikube | `minikube image load air-gapped-mirror/$i:latest` |
| kind | `kind load docker-image air-gapped-mirror/$i:latest` |
| k3s | `docker save air-gapped-mirror/$i:latest \| sudo k3s ctr images import -` |
| Docker Desktop | drop it — the cluster shares the daemon's images |

The chart runs these with `imagePullPolicy: Never`, so a missing image
fails immediately with `ErrImageNeverPull` instead of trying to pull a
name that isn't ours from Docker Hub.

A node with no internet also needs `nginx:1.27-alpine` side-loaded the
same way; it's a stock upstream image and otherwise pulls on its own.

## 2. Install

```sh
helm install air-gapped-mirror ./chart \
  --namespace air-gapped-mirror --create-namespace
```

The defaults expect local images, so there is nothing to configure here.

- `air-gapped-mirror` (first argument) is the **release name** — Helm's
  label for this install. Reuse it to upgrade or uninstall.
- `--namespace` puts everything in its own slice of the cluster;
  `--create-namespace` makes it if missing.

That's it. Four services start: git, files (HTTP), pip, and apt.

## 3. Check it in k9s

```sh
k9s -n air-gapped-mirror
```

One pod, **4/4** containers ready (**5/5** after step 4). Useful keys: `l`
logs, `d` describe, `s` shell, `:svc` services, `:pvc` volumes, `esc` back.
`ErrImageNeverPull` means step 1's images didn't make it onto the node;
`Pending` usually means no storage available.

## 4. Turn on mirroring (optional)

Steps 1–3 already give you a working pip and apt cache — they fill
themselves as people use them. Mirroring git repos and files needs your
config repo (the one holding the manifests):

```sh
helm upgrade air-gapped-mirror ./chart --namespace air-gapped-mirror \
  --reuse-values \
  --set syncJob.enabled=true \
  --set syncJob.configRepoUrl=https://gitlab.com/your-org/mirror-config.git
```

The config repo is public, so its clone URL is a plain value — there is no
Secret to create.

That adds a `sync` sidecar that re-reads the config repo every 60s and
makes the volumes match it — nothing to trigger. It logs only on change or
failure, so an empty log means "up to date":

```sh
kubectl -n air-gapped-mirror logs deploy/air-gapped-mirror -c sync -f
```

## 5. Point clients at it

From inside the cluster (use the port-forward below from outside):

| Use | Setting |
| --- | --- |
| git | `git clone git://air-gapped-mirror/<repo>.git` |
| files | `http://air-gapped-mirror/` |
| pip | `--index-url http://air-gapped-mirror:3141/root/pypi/+simple/ --trusted-host air-gapped-mirror` |
| apt | `Acquire::HTTP::Proxy "http://air-gapped-mirror:3142";` |

`--trusted-host` is required — pip silently ignores plain-HTTP indexes
without it.

```sh
kubectl -n air-gapped-mirror port-forward svc/air-gapped-mirror 8080:80
curl http://localhost:8080/healthz   # -> ok
```

## Common settings

Override with `--set key=value`, or copy `values.yaml` and pass
`-f my-values.yaml`. Full list in `values.yaml`.

| Key | Default | Notes |
| --- | --- | --- |
| `image.tag` | `latest` | Must match the tag you built and loaded |
| `image.registry` | `""` | Empty = local images. Set only if you push to one |
| `storage.sizes.mirrorFiles` | `200Gi` | Largest volume; tarballs/binaries |
| `storage.className` | `""` | Empty = cluster default |
| `storage.accessMode` | `ReadWriteOnce` | Fine as-is; one pod mounts everything |
| `syncJob.intervalSeconds` | `60` | Each pass fetches every mirrored repo — see below |

Lower `intervalSeconds` freely for a few internal repos. Careful across
many *public* ones: each pass fetches every repo, so 10s × 20 repos is
~180k fetches/day and GitHub will rate-limit you.

## Uninstall

```sh
helm uninstall air-gapped-mirror --namespace air-gapped-mirror
```

This deletes the volumes and mirrored data too. Re-running step 2
gives a clean install.
