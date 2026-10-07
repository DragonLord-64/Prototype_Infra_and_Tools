# Restricted-host Minikube test

This directory contains test-only image overlays for hosts where package
mirrors, Docker Hub blobs, proxy certificates, or container runtime settings
prevent the normal [`../up.sh`](../up.sh) workflow. It is not part of the
production deployment.

The overlays use reachable Ubuntu/Python bases, optionally install a proxy CA,
and provide a custom Minikube base image whose runc shim removes unsupported
`oomScoreAdj` and file-limit settings. Review these host-specific workarounds
before using them elsewhere.

From this directory:

```sh
./build.sh /path/to/ca-bundle.crt
docker build -t local/kicbase-sandboxed:v0.0.50 kicbase
minikube -p air-mirror-test start --driver=docker --force \
  --base-image=local/kicbase-sandboxed:v0.0.50 \
  --cpus=3 --memory=4096mb --disk-size=20g

docker build -t air-gapped-mirror/test-client:test -f test-client.Dockerfile .
for image in git-daemon devpi apt-cacher-ng sync-job test-client; do
  minikube -p air-mirror-test image load "air-gapped-mirror/$image:test"
done

kubectl apply -f ../manifests/00-namespace.yaml
kubectl apply -f 10-fixtures.yaml
helm upgrade --install mirror ../../chart --namespace air-gapped-mirror \
  -f ../values-test.yaml -f ../values-real-repo.yaml

CLIENT_IMAGE=air-gapped-mirror/test-client:test ../verify.sh
CLIENT_IMAGE=air-gapped-mirror/test-client:test ../verify-real-repo.sh
```

If Docker Hub itself is blocked, configure an approved registry mirror before
building. Passing a CA file to `build.sh` embeds it in images that make outbound
requests; treat that CA as trusted security configuration. The apt check may be
skipped when host policy blocks Debian mirrors.
