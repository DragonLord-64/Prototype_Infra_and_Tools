# ---- Restricted-network build of ../../git-daemon/Dockerfile ----
# Identical runtime contract (same user, same safe.directory config, same
# volume, port and entrypoint) -- only the package source differs: this one
# takes git from Ubuntu's archive instead of Alpine's, because the sandbox
# this test runs in can reach archive.ubuntu.com but not
# dl-cdn.alpinelinux.org. See README.md in this directory.
FROM ubuntu:24.04

# Ubuntu's `git` package ships git-daemon (/usr/lib/git-core/git-daemon),
# so there is no separate git-daemon package to install as there is on Alpine.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --no-create-home --shell /usr/sbin/nologin git \
 # Same reason as the production image: repos on the shared volume are
 # written by the sync sidecar under a different uid, and git >=2.35.2
 # would otherwise refuse to serve them as "dubious ownership".
 && git config --system --add safe.directory '*'

VOLUME /var/git/repos
EXPOSE 9418

USER git

ENTRYPOINT ["git", "daemon", "--reuseaddr", "--export-all", "--verbose", \
            "--base-path=/var/git/repos", "--listen=0.0.0.0", "--port=9418", \
            "/var/git/repos"]
