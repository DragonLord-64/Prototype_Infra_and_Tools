# ---- minikube node image for sandboxed hosts ----
# Stock kicbase plus a runc shim. See ../README.md: this sandbox refuses to
# lower oom_score_adj and caps RLIMIT_NOFILE at its own hard limit, both of
# which stock kubelet/dockerd violate on every pod sandbox.
ARG KICBASE=gcr.io/k8s-minikube/kicbase:v0.0.50
FROM ${KICBASE}

RUN mv /usr/bin/runc /usr/bin/runc.real
COPY runc-shim.sh /usr/bin/runc
RUN chmod +x /usr/bin/runc
