# Filebeat role integration test

This harness tests the unmodified `roles/filebeat` role on a disposable
Docker-in-Docker server. It does not change production role defaults.

The test server joins two existing networks:

- `elastic`, so Filebeat can send to the prototype Elasticsearch container as
  `http://elasticsearch:9200` without exposing Elasticsearch externally;
- `monitoring`, so the server retains access to the Minikube lab network.

The test-only `vars.yml` disables Kubernetes collection and the ingest
pipeline, selects unauthenticated HTTP, and removes systemd-specific bind
mounts that do not exist in the lightweight test server. Production inventory
should provide its own Elasticsearch address and security settings and should
not load this variables file.

The test variables also define an unused password placeholder. The role's
validation evaluates its mandatory password default even when authentication
is `none`; the Filebeat template does not render the placeholder in this mode.
The image includes OpenRC only so Ansible's `service_facts` module returns the
service dictionary expected by the role; OpenRC does not manage the nested
Docker daemon. Its service cache is initialized while building the image to
avoid a first-run OpenRC/Ansible discovery failure. `run.sh` waits up to 30
seconds for the nested Docker daemon before starting Ansible.

From this directory, with permission to use Docker:

```sh
./up.sh
./run.sh
```

The server remains running for follow-up tests. Remove it when finished:

```sh
./down.sh
```

The integration check creates a `filebeat-test-server-9.3.3` data stream in
the prototype Elasticsearch instance. It is deliberately named separately
from production indices.
