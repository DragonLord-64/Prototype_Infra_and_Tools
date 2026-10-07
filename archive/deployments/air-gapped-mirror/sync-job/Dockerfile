# ---- Sync job image: mirrors the git repos listed in the manifest ----
FROM python:3.11-alpine

RUN apk add --no-cache git openssh-client \
 # The repos under /var/git/repos may be owned by a different uid across
 # restarts/redeploys -- git >=2.35.2's dubious-ownership check would
 # otherwise refuse to touch them (same fix as git-daemon's Dockerfile,
 # same reason). --system, not --global: syncjob has no home directory.
 && git config --system --add safe.directory '*'

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mirror_sync ./mirror_sync

# Non-root: the sync job only needs write access to the shared volumes,
# which the CronJob's fsGroup makes group-writable for this uid.
RUN adduser -D -u 10001 syncjob
USER syncjob

ENTRYPOINT ["python", "-m", "mirror_sync.sync"]
