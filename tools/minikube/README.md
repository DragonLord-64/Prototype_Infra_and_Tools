# Local Minikube cluster

`setup.sh` creates the single-node Kubernetes cluster used for local
prototyping. Application manifests and Helm releases live elsewhere in the
repository.

## Requirements

- Linux (`amd64` or `arm64`)
- Docker Engine, accessible to the current user
- `curl`, `sha256sum`, and `sudo` if `/usr/local/bin` is not writable

From the repository root, run:

```sh
./tools/minikube/setup.sh
```

The script verifies and installs Minikube `v1.39.0`, then starts the
`monitoring` profile with Docker, containerd, 4 CPUs, and 4096 MiB of memory.
Settings can be overridden through the environment:

```sh
MINIKUBE_PROFILE=dev MINIKUBE_CPUS=2 MINIKUBE_MEMORY=3072 \
  ./tools/minikube/setup.sh
```

`MINIKUBE_VERSION` and `MINIKUBE_INSTALL_DIR` are also supported. Re-running
the script reconciles the same profile.

Use Minikube's bundled `kubectl` to inspect the cluster:

```sh
minikube -p monitoring status
minikube -p monitoring kubectl -- get pods --all-namespaces
minikube -p monitoring stop
```

`stop` preserves the cluster. `minikube delete -p monitoring` permanently
removes that profile and its local state.
