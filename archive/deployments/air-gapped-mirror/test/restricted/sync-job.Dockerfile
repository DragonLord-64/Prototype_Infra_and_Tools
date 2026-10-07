# ---- Restricted-network build of ../../sync-job/Dockerfile ----
# Same runtime contract (same uid 10001, same safe.directory config, same
# entrypoint). Differences, both forced by the sandbox's egress policy:
#   - base is python:3.11 (Debian) rather than python:3.11-alpine, because
#     it already ships git and openssh-client and so needs no apk/apt access
#   - an optional extra CA is installed, so the sync loop can clone from an
#     upstream whose TLS is re-terminated by the sandbox's egress proxy
FROM python:3.11

WORKDIR /app

# Empty unless build.sh was given a CA bundle (see README.md). Installed into
# both the system trust store and the file pip/openssl read directly, so git
# and pip alike trust an egress proxy that re-terminates TLS.
COPY extra-ca.crt /tmp/extra-ca.crt
RUN if [ -s /tmp/extra-ca.crt ]; then \
      mkdir -p /usr/local/share/ca-certificates && \
      cp /tmp/extra-ca.crt /usr/local/share/ca-certificates/extra-ca.crt && \
      { command -v update-ca-certificates >/dev/null && update-ca-certificates || true; } && \
      cat /tmp/extra-ca.crt >> /etc/ssl/certs/ca-certificates.crt; \
    fi; \
    rm -f /tmp/extra-ca.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt

# git and openssh-client come with the base image. Same dubious-ownership
# fix as production, for the same reason.
RUN git config --system --add safe.directory '*'

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mirror_sync ./mirror_sync

RUN useradd --uid 10001 --create-home syncjob
USER syncjob

ENTRYPOINT ["python", "-m", "mirror_sync.sync"]
