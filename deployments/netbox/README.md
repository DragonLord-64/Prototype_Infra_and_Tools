# NetBox

This deployment installs the official NetBox community Helm chart with its
bundled PostgreSQL and Valkey services. Data is persistent; the web service is
cluster-local and intended to be reached with a port-forward.

## Deploy

Install `helm` and `kubectl`, select the intended Kubernetes context, and run:

```sh
export NETBOX_ADMIN_PASSWORD="$(openssl rand -base64 24)"
export NETBOX_API_TOKEN="$(openssl rand -hex 20)"
./deployments/netbox/deploy.sh
```

Save those values in a password manager. They are passed to Helm and stored as
Kubernetes/Helm secrets, never in this repository. Reuse the same values when
upgrading the release.

Open NetBox locally:

```sh
kubectl -n netbox port-forward service/netbox 8000:80
```

Visit <http://localhost:8000> and sign in as `admin`. The API token can be used
directly by the importer:

```sh
NETBOX_URL=http://localhost:8000 NETBOX_TOKEN="$NETBOX_API_TOKEN" \
  ./tools/netbox/csv-import/import.sh inventory/
```

For Minikube without a standalone `kubectl`, place this wrapper earlier in
`PATH` or run the equivalent commands through `minikube kubectl --`:

```sh
minikube -p monitoring kubectl -- -n netbox get pods,service,pvc
```

This is a lab deployment. Before production use, move credentials to an
external secret manager, pin a reviewed chart version, configure ingress with
TLS, backups, resource sizing, and a highly available external database.
