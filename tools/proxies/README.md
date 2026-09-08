# Minikube package proxies

This manifest runs the `ska-mid-cbf-prototyping` Git, APT, and pip proxy
images in the `monitoring` Minikube cluster. It does not deploy the Git mirror.

Build the images from a sibling checkout, load them into Minikube, and deploy:

```sh
./tools/proxies/deploy.sh
```

Set `PROTOTYPING_REPO` if the source checkout is elsewhere, or
`MINIKUBE_PROFILE` if the profile is not `monitoring`.

The proxies are exposed on the Minikube node at:

- Git (Squid): `http://$(minikube -p monitoring ip):30128`
- APT (apt-cacher-ng): `http://$(minikube -p monitoring ip):30142`
- pip (devpi): `http://$(minikube -p monitoring ip):30141/root/pypi/+simple/`

APT and pip cache data use 2 GiB persistent volume claims. The services remain
available after `minikube stop` / `minikube start`; deleting the cluster removes
their data.
