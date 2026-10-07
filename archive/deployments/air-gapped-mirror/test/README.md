# Minikube smoke test

These scripts create a disposable Minikube profile named `air-mirror-test`,
build and load the four mirror images, install the production Helm chart, and
add an in-cluster Git fixture.

Run from this directory:

```sh
./up.sh
./verify.sh
./down.sh
```

`up.sh` can be rerun after code changes. `down.sh` deletes the complete test
profile, including its volumes and loaded images. The scripts expect Docker,
Minikube, kubectl, Helm, and access to `sudo -g docker`.

`verify.sh` checks Git synchronization and cloning, then makes best-effort
requests through devpi and apt-cacher-ng. Those proxy checks are skipped when
the cluster lacks outbound access. It finally verifies that all four mirror
containers are ready.

If the default Alpine client cannot install its tools, provide a prepared
image:

```sh
CLIENT_IMAGE=air-gapped-mirror/test-client:test ./verify.sh
```

For an optional live GitHub check, install the chart with
`values-real-repo.yaml` in addition to `values-test.yaml`, then run
`./verify-real-repo.sh`. This test requires cluster internet access.

Hosts with restricted image or package egress may need the overlays described
in [`restricted/README.md`](restricted/README.md).
