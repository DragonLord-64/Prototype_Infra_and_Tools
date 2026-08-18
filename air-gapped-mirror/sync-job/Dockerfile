# ---- Sync job image: polls GitLab, mirrors git repos/tarballs/keys ----
FROM python:3.11-alpine

RUN apk add --no-cache git openssh-client

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mirror_sync ./mirror_sync

# Non-root: the sync job only needs write access to the shared volumes,
# which are mounted with permissions for this uid in the CronJob spec.
RUN adduser -D -u 10001 syncjob
USER syncjob

ENTRYPOINT ["python", "-m", "mirror_sync.sync"]
