# ---- Caching apt proxy: apt on air-gapped nodes points here instead of ----
# ---- reaching the real Debian/Ubuntu mirrors directly ----
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends apt-cacher-ng \
 && rm -rf /var/lib/apt/lists/*

COPY acng.conf /etc/apt-cacher-ng/acng.conf

VOLUME /var/cache/apt-cacher-ng
EXPOSE 3142

CMD ["/usr/sbin/apt-cacher-ng", "-c", "/etc/apt-cacher-ng", "ForeGround=1"]
