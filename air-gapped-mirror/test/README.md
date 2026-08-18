# Minikube smoke test

Self-contained functional test of the air-gapped mirror. Spins up a
dedicated minikube profile (`air-mirror-test`), deploys the stack plus
fixtures that stand in for the internet and the config repo, exercises
every component, then tears the whole thing down.

Nothing external is required: no real forge, no real upstream repos.
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
| 1 | sync sidecar | Waits for the reconcile loop to mirror the fixture git repo + tarball (nothing triggers it) |
| 2 | `git-daemon` | Clones the just-mirrored repo over `git://` and diffs the content |
| 3 | `nginx` | `/healthz`, plus serving the just-mirrored tarball |
| 4 | `devpi` | Real `pip install six` through the proxy, cached from PyPI |
| 5 | `apt-cacher-ng` | Real Debian `InRelease` fetch through the proxy |
| 6 | Deployment | All 5 containers report Ready |

Checks 4 and 5 need outbound internet from the cluster; without it they
report SKIP, not FAIL.

## Fixtures

`manifests/10-fixtures.yaml` deploys three stand-ins, all in-cluster:

- **`fixture-git`** — a `git-daemon` serving a seeded `hello.git`, playing
  the part of a public upstream repo the mirror pulls from.
- **`fixture-http`** — nginx serving a static file, standing in for a
  public tarball/binary the mirror downloads.
- **`config-repo`** — a `git-daemon` serving the seeded manifests
  (`git-repos.yaml`, `tarballs.yaml`) that the sync loop reconciles
  against, standing in for the real config repo.

The mirror is installed from the production Helm chart (`../chart`), with
`values-test.yaml` overriding only the images, storage sizes, and the sync
loop interval (5s instead of 60s).
