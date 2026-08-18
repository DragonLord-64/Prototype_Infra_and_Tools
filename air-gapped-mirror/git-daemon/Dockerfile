# ---- Serves bare git repos read-only over the native git:// protocol ----
FROM alpine:3.20

RUN apk add --no-cache git \
 && adduser -D -H -s /sbin/nologin git

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
