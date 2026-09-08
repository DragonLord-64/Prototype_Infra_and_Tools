# ---- Caching PyPI proxy: pip installs hit this instead of pypi.org ----
FROM python:3.11-alpine

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
