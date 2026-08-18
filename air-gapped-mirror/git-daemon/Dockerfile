# ---- Serves bare git repos read-only over the native git:// protocol ----
FROM alpine:3.20

RUN apk add --no-cache git git-daemon \
 && adduser -D -H -s /sbin/nologin git \
 # Repos arrive from the sync job's CronJob pod, which runs as a
 # different uid (fsGroup only aligns group perms, not ownership) --
 # without this, git >=2.35.2's dubious-ownership check makes git-daemon
 # refuse to serve every repo the sync job populates. System-wide (not
 # --global) since this user has no home directory.
 && git config --system --add safe.directory '*'

VOLUME /var/git/repos
EXPOSE 9418

USER git

# --export-all: serve every repo under base-path without needing a
# git-daemon-export-ok marker file in each one (repos arrive via the sync
# job's `git clone --mirror`, which doesn't create that marker).
# No --enable=receive-pack, so this is read-only by construction.
ENTRYPOINT ["git", "daemon", "--reuseaddr", "--export-all", "--verbose", \
            "--base-path=/var/git/repos", "--listen=0.0.0.0", "--port=9418", \
            "/var/git/repos"]
