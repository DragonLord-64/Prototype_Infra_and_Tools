# Lightweight "server" container: standard Prometheus node_exporter +
# a tiny stdlib-only custom exporter with a few fluctuating numeric metrics.
FROM prom/node-exporter:latest AS node_exporter

FROM python:3-alpine

COPY --from=node_exporter /bin/node_exporter /bin/node_exporter
COPY exporter.py /app/exporter.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9100 9101

ENTRYPOINT ["/entrypoint.sh"]
