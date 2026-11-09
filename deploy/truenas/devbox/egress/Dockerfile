# syntax=docker/dockerfile:1
# Allowlisting egress proxy of the OpenClaw coder devbox (Debian squid, non-root).
# The base image is pinned by digest through DEBIAN_IMAGE in ../compose.yml
# before the contract becomes "active" (just devbox-pin).
ARG DEBIAN_IMAGE=debian:trixie-slim
FROM ${DEBIAN_IMAGE}
LABEL name="openclaw-devbox-egress" version="0.1.0"

# Version follows the digest-pinned base (see ../Dockerfile).
# hadolint ignore=DL3008
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends squid \
 && rm -rf /var/lib/apt/lists/*

COPY --chmod=0444 squid.conf /etc/squid/squid.conf
RUN squid -k parse -f /etc/squid/squid.conf

USER 13:13
EXPOSE 3128
ENTRYPOINT ["squid", "-N", "-f", "/etc/squid/squid.conf"]
