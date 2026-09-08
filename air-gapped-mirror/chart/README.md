# Air-gapped mirror Helm chart

This chart deploys one pod containing the Git, PyPI, and apt services plus an
optional Git synchronization sidecar. It expects locally loaded images by
default (`image.pullPolicy: Never`).

## Minikube install

From the repository root:

```sh
for image in git-daemon devpi apt-cacher-ng sync-job; do
  docker build -t "air-gapped-mirror/$image:latest" "air-gapped-mirror/$image"
  minikube image load "air-gapped-mirror/$image:latest"
done

helm upgrade --install air-gapped-mirror ./air-gapped-mirror/chart \
  --namespace air-gapped-mirror --create-namespace
kubectl -n air-gapped-mirror rollout status deployment/air-gapped-mirror
```

For another cluster, load the images with its runtime or set `image.registry`,
`image.tag`, and `image.pullPolicy` for an accessible registry.

## Git repositories

Git synchronization is disabled until a values file enables it:

```yaml
syncJob:
  enabled: true
  intervalSeconds: 60
  repos:
    - name: widgets
      url: https://github.com/your-org/widgets.git
      dest: your-org/widgets
```

```sh
helm upgrade air-gapped-mirror ./air-gapped-mirror/chart \
  --namespace air-gapped-mirror -f my-values.yaml
kubectl -n air-gapped-mirror logs deployment/air-gapped-mirror -c sync -f
```

Each destination is relative to the mirror root; `.git` is appended when
missing. Avoid very short intervals because every pass fetches every upstream.

## Client endpoints

Inside the namespace, using the default release name:

| Service | Endpoint |
| --- | --- |
| Git | `git://air-gapped-mirror/<path>.git` |
| pip | `http://air-gapped-mirror:3141/root/pypi/+simple/` |
| apt | `http://air-gapped-mirror:3142` |

Plain-HTTP pip clients also need `--trusted-host air-gapped-mirror`. The
repository's `setup-proxy-source.yml` playbook can configure apt, pip, DNS, and
Git URL rewrites on client hosts.

Important defaults are in [`values.yaml`](values.yaml): three 50 Gi persistent
volumes, `ReadWriteOnce` access, local `latest` images, and a 60-second sync
interval. Override storage class and sizes for the target cluster.

## Removal

```sh
helm uninstall air-gapped-mirror --namespace air-gapped-mirror
```

Review the PVCs and storage-class reclaim policy before removal if cached data
must be retained.
