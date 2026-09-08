# ---- Restricted-network build of ../../apt-cacher-ng/Dockerfile ----
# Same runtime contract (same config path, volume, port and command); only
# the base distro changes, from debian:bookworm-slim to ubuntu:24.04,
# because the sandbox can reach archive.ubuntu.com but not deb.debian.org.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends apt-cacher-ng \
 && rm -rf /var/lib/apt/lists/*

COPY acng.conf /etc/apt-cacher-ng/acng.conf

VOLUME /var/cache/apt-cacher-ng
EXPOSE 3142

CMD ["/usr/sbin/apt-cacher-ng", "-c", "/etc/apt-cacher-ng", "ForeGround=1"]
