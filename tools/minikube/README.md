# Local Minikube cluster

This directory defines the repeatable single-node Kubernetes environment used
for local monitoring experiments. It currently creates the cluster only; add
application manifests or Helm releases separately as they are decided.

## Prerequisites

- Linux on `amd64` or `arm64`
- Docker Engine running and usable by the current user
- `curl`, `sha256sum`, and `sudo` (unless `/usr/local/bin` is writable)

## Create or reconcile the cluster

From the repository root:

```sh
./tools/minikube/setup.sh
```

The script installs the pinned Minikube release after verifying its published
SHA-256 checksum, then creates a profile named `monitoring` with the Docker
driver, containerd runtime, 4 CPUs, and 4096 MiB of memory. It is safe to run
again: Minikube reconciles the existing profile instead of creating a second
cluster.

Override a setting for a smaller host or another profile:

```sh
MINIKUBE_PROFILE=dev MINIKUBE_CPUS=2 MINIKUBE_MEMORY=3072 ./tools/minikube/setup.sh
```

`MINIKUBE_VERSION` and `MINIKUBE_INSTALL_DIR` are also configurable. Change the
default version in `setup.sh` deliberately when upgrading so every machine uses
the same release.

## Operate the cluster

No separate `kubectl` install is required:

```sh
minikube -p monitoring status
minikube -p monitoring kubectl -- get pods --all-namespaces
minikube -p monitoring pause
minikube -p monitoring unpause
minikube -p monitoring stop
```

`stop` preserves the cluster. To permanently remove its containers and local
state, explicitly run:

```sh
minikube delete -p monitoring
```
