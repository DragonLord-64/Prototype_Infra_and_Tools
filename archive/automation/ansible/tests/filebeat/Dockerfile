FROM docker:28-dind

RUN apk add --no-cache ansible git openrc py3-pip \
    && python3 -m pip install --break-system-packages --no-cache-dir docker \
    && (rc-status -a >/dev/null 2>&1 || true)

WORKDIR /work/automation/ansible
