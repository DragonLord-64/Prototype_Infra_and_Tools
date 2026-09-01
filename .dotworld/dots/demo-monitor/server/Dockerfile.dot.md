---
id: demo-monitor/server/Dockerfile
source_id: Prototype
title: Server container image
tags:
  - docker
  - server
  - node-exporter
  - lightweight
source_path: $DOTWORLD_ROOT/demo-monitor/server/Dockerfile
kind: file
summary: Builds the demo-monitor server container. Stage one is prom/node-exporter:latest, used only as a source to copy the static node_exporter binary out of. Stage two starts from python:3-alpine, copies in that binary plus exporter.py and entrypoint.sh, marks entrypoint.sh executable, exposes ports 9100 (node_exporter) and 9101 (custom exporter), and runs entrypoint.sh as the container's entrypoint. No package manager installs are run, so the only dependencies are what ships in the base images. Final image is about 118MB.
summary_blob: 2ec1cdb6e6f1f849ca45111f21834d3ee381dbd7
---

Multi-stage build: the node_exporter binary is copied straight out of the official prom/node-exporter image rather than curl'd or apt-installed, so there's no extra build-time fetch logic to maintain. Final stage is python:3-alpine plus the copied binary -- deliberately no pip install layer, to keep the image small (118MB) and the build fast/reproducible for running many replicas (target: ~10) side by side on one VM.
