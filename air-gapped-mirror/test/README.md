# Minikube smoke test

Self-contained functional test of the air-gapped mirror. Spins up a
dedicated minikube profile (`air-mirror-test`), deploys the stack plus a
fixture that stands in for a public upstream repo, exercises every
component, then tears the whole thing down.

Nothing external is required: no real upstream repos.
Outbound internet is used only by the devpi/apt-cacher-ng checks, which
are the point of those two components.

```sh
./up.sh       # build images, start cluster, deploy   (~80s from scratch)
./verify.sh   # run the functional checks             (~60s)
./down.sh     # delete the whole profile              (~15s)
```

`up.sh` is idempotent — re-run it after changing code to rebuild and
redeploy into the existing cluster. `down.sh` deletes the minikube
profile outright (container, disk, and every image loaded into it), so
nothing is left consuming resources between test runs.

## What `verify.sh` checks

| # | Component | Check |
| --- | --- | --- |
| 1 | sync sidecar | Waits for the reconcile loop to mirror the fixture git repo (nothing triggers it) |
| 2 | `git-daemon` | Clones the just-mirrored repo over `git://` and diffs the content |
| 3 | `devpi` | Real `pip install six` through the proxy, cached from PyPI |
| 4 | `apt-cacher-ng` | Real Debian `InRelease` fetch through the proxy |
| 5 | Deployment | All 4 containers report Ready |

Checks 3 and 4 need outbound internet from the cluster; without it they
report SKIP, not FAIL.

## Fixture

`manifests/10-fixtures.yaml` deploys one stand-in, in-cluster:

- **`fixture-git`** — a `git-daemon` serving a seeded `hello.git`, playing
  the part of a public upstream repo the mirror pulls from.

The repo list is not a fixture: it comes from the chart's ConfigMap,
seeded by `values-test.yaml`, which is the same path production uses.

The mirror is installed from the production Helm chart (`../chart`), with
`values-test.yaml` overriding only the images, storage sizes, the repo
list, and the sync loop interval (5s instead of 60s).
