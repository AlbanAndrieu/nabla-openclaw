# syntax=docker/dockerfile:1
# OpenClaw coder devbox: SSH-only target of the Gateway `ssh` sandbox backend.
# It never holds Gateway, LiteLLM or channel credentials; see docs/coder-agent.md.
# The base image is pinned by digest through PYTHON_IMAGE in compose.yml
# before the contract becomes "active" (just devbox-pin).
ARG PYTHON_IMAGE=python:3.13-slim-trixie
FROM ${PYTHON_IMAGE}
LABEL name="openclaw-devbox" version="0.1.0"

# Debian trixie packages only: sshd, the SSH sandbox bridge contract
# (/bin/sh, python3, GNU stat/readlink, tar) and the fastapi-sample toolchain
# (git, gh, just, make, node for `just ui-quick`). Versions follow the
# digest-pinned base: exact apt pins break on each Debian security update.
# hadolint ignore=DL3008
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils curl gh git just make nodejs openssh-server tar tini \
 && rm -rf /var/lib/apt/lists/* /etc/ssh/ssh_host_* \
 && groupadd --gid 1001 coder \
 && useradd --uid 1001 --gid coder --home-dir /home/coder --no-create-home --shell /bin/bash coder \
 && install -d -o root -g root -m 0755 /etc/openclaw-devbox

COPY --chmod=0444 requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

COPY --chmod=0444 sshd_config /etc/ssh/sshd_config
COPY --chmod=0444 gitconfig /etc/gitconfig
COPY --chmod=0555 entrypoint.sh /usr/local/bin/devbox-entrypoint
COPY --chmod=0555 git-credential-devbox /usr/local/bin/git-credential-devbox
COPY --chmod=0555 gh-wrapper.sh /usr/local/bin/gh

# Must match `user:` in compose.yml and the dataset owner (scripts/coder/bootstrap-truenas.sh).
USER 1001:1001
WORKDIR /home/coder
EXPOSE 2222
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/devbox-entrypoint"]
