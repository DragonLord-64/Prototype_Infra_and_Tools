# ---- Restricted-network build of ../../devpi/Dockerfile ----
# Identical to the production Dockerfile apart from the CA step: the sandbox's
# egress proxy re-terminates TLS, so pip cannot reach PyPI without trusting it.
FROM python:3.11-alpine

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

RUN pip install --no-cache-dir devpi-server \
 && adduser -D -H -s /sbin/nologin devpi

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && mkdir -p /var/devpi \
 && chown devpi:devpi /var/devpi

VOLUME /var/devpi
EXPOSE 3141

USER devpi
ENTRYPOINT ["/entrypoint.sh"]
