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

Two optional extras:

- [`verify-real-repo.sh`](verify-real-repo.sh) runs the git checks against a
  real public upstream on GitHub instead of the in-cluster fixture. It needs
  the chart installed with [`values-real-repo.yaml`](values-real-repo.yaml)
  layered on top of `values-test.yaml`.
- [`restricted/`](restricted) is what to use when the host's egress policy or
  container sandbox is too tight for `up.sh` — blocked distro mirrors, a
  TLS-terminating proxy, no lowering of `oom_score_adj`.

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

`CLIENT_IMAGE=<image> ./verify.sh` swaps the throwaway client pod's image for
one that already has git/curl/pip, for clusters that cannot reach Alpine's
package mirror.

## What `verify-real-repo.sh` checks

Same git path, but against `https://github.com/DragonLord-64/Prototype_Infra_and_Tools.git`
-- a real remote with real branches, tags and pack negotiation:

| # | Check |
| --- | --- |
| 1 | The sync sidecar mirrors the real upstream, untriggered |
| 2 | A client clones it back out over `git://` |
| 3 | The cloned tree really is that repository (files the fixture does not have) |
| 4 | Every upstream branch/tag ref is in the mirror at the same SHA, compared live against GitHub |
| 5 | A commit pushed upstream after the initial clone is picked up by a later pass |

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
