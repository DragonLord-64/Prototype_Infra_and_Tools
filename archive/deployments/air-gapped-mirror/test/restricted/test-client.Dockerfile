# ---- Test client with the verify.sh toolchain already installed ----
# ../verify.sh normally runs `apk add git curl py3-pip` inside a stock alpine
# pod. This sandbox blocks Alpine's package mirror, so the tools are baked in
# here instead and verify.sh is pointed at this image with
#   CLIENT_IMAGE=air-gapped-mirror/test-client:test ./verify.sh
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git curl ca-certificates python3-pip \
 && rm -rf /var/lib/apt/lists/*

# verify.sh calls `pip`, which Ubuntu ships only as pip3.
RUN ln -sf /usr/bin/pip3 /usr/local/bin/pip
