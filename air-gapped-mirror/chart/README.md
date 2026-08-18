# Deploying the mirror with Helm

Helm is a package manager for Kubernetes. This directory is a *chart*: a
bundle of templated manifests plus a `values.yaml` of settings.

## 1. Get the images onto the cluster

No registry is involved: build the four images locally, then load them
onto the node the cluster runs on. (Four images, three services — the
fourth is the sync sidecar.)

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

That's it. Three services start: git, pip, and apt.

## 3. Check it in k9s

```sh
k9s -n air-gapped-mirror
```

One pod, **3/3** containers ready (**4/4** after step 4). Useful keys: `l`
logs, `d` describe, `s` shell, `:svc` services, `:pvc` volumes, `esc` back.
`ErrImageNeverPull` means step 1's images didn't make it onto the node;
`Pending` usually means no storage available.

## 4. Turn on git mirroring (optional)

Steps 1–3 already give you a working pip and apt cache — they fill
themselves as people use them. Mirroring git repos means listing the ones
you want. Put them in a values file:

```yaml
# my-values.yaml
syncJob:
  enabled: true
  repos:
    - name: widgets
      url: https://github.com/your-org/widgets.git
      dest: your-org/widgets
    - name: tooling
      url: https://github.com/someone/tooling.git
      dest: vendor/tooling
```

```sh
helm upgrade air-gapped-mirror ./chart --namespace air-gapped-mirror \
  --reuse-values -f my-values.yaml
```

Each entry needs three fields:

| Field | Meaning |
| --- | --- |
| `name` | Label only — what shows up in the sync log |
| `url` | Upstream to mirror. `http://`, `https://`, `git://`, `ssh://`, or `git@` |
| `dest` | Path under the mirror. Relative, no `..`; `.git` is appended if missing |

`dest` is also the path clients clone from, so `dest: your-org/widgets`
becomes `git clone git://air-gapped-mirror/your-org/widgets.git`.

That adds a `sync` sidecar that re-reads the list every 60s and makes the
git volume match it — nothing to trigger. It logs only on change or
failure, so an empty log means "up to date":

```sh
kubectl -n air-gapped-mirror logs deploy/air-gapped-mirror -c sync -f
```

The list is rendered into a ConfigMap and mounted into the sidecar. To
change it, edit the values and `helm upgrade` again — the mounted file
refreshes in place, so the next pass picks it up with no restart.

## 5. Point clients at it

From inside the cluster (use the port-forward below from outside):

| Use | Setting |
| --- | --- |
| git | `git clone git://air-gapped-mirror/<repo>.git` |
| pip | `--index-url http://air-gapped-mirror:3141/root/pypi/+simple/ --trusted-host air-gapped-mirror` |
| apt | `Acquire::HTTP::Proxy "http://air-gapped-mirror:3142";` |

`--trusted-host` is required — pip silently ignores plain-HTTP indexes
without it.

```sh
kubectl -n air-gapped-mirror port-forward svc/air-gapped-mirror 9418:9418
git clone git://localhost:9418/<repo>.git
```

## Common settings

Override with `--set key=value`, or copy `values.yaml` and pass
`-f my-values.yaml`. Full list in `values.yaml`.

| Key | Default | Notes |
| --- | --- | --- |
| `image.tag` | `latest` | Must match the tag you built and loaded |
| `image.registry` | `""` | Empty = local images. Set only if you push to one |
| `syncJob.repos` | `[]` | The repos to mirror; required if `syncJob.enabled` |
| `storage.sizes.gitRepos` | `50Gi` | Holds every mirrored bare repo |
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
