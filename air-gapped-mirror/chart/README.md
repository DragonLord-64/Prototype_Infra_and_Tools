# Deploying the mirror with Helm

Helm is a package manager for Kubernetes. This directory is a *chart*: a
bundle of templated manifests plus a `values.yaml` of settings.

## 1. Get the images onto the cluster

The cluster must be able to pull the four images:

```sh
cd ..
for i in git-daemon devpi apt-cacher-ng sync-job; do
  docker build -t registry.example.com/air-gapped-mirror/$i:0.1.0 $i
  docker push  registry.example.com/air-gapped-mirror/$i:0.1.0
done
```

## 2. Install

```sh
helm install air-gapped-mirror ./chart \
  --namespace air-gapped-mirror --create-namespace \
  --set image.registry=registry.example.com \
  --set image.tag=0.1.0
```

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
`ImagePullBackOff` means step 1's images aren't reachable; `Pending`
usually means no storage available.

## 4. Turn on mirroring (optional)

Steps 1–3 already give you a working pip and apt cache — they fill
themselves as people use them. Mirroring git repos and files needs your
config repo (the one holding the manifests):

```sh
kubectl -n air-gapped-mirror create secret generic mirror-sync-secrets \
  --from-literal=CONFIG_REPO_URL=https://oauth2:<token>@gitlab.com/your-org/mirror-config.git

helm upgrade air-gapped-mirror ./chart --namespace air-gapped-mirror \
  --reuse-values \
  --set syncJob.enabled=true \
  --set syncJob.existingSecret=mirror-sync-secrets
```

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
