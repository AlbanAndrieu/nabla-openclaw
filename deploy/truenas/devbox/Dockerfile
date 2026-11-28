# syntax=docker/dockerfile:1
# OpenClaw coder devbox: SSH-only target of the Gateway `ssh` sandbox backend.
# It never holds Gateway, LiteLLM or channel credentials; see docs/coder-agent.md.
# The base image is pinned by digest through PYTHON_IMAGE in compose.yml
# before the contract becomes "active" (just devbox-pin).
ARG PYTHON_IMAGE=python:3.13-slim-trixie
FROM ${PYTHON_IMAGE}
LABEL name="openclaw-devbox" version="0.2.0"

# Debian trixie packages: sshd, the SSH sandbox bridge contract
# (/bin/sh, python3, GNU stat/readlink, tar) and the repositories' toolchain
# (git, gh, jq, just, make; the repos' scripts and tests call jq). Versions
# follow the digest-pinned base: exact apt pins break on each Debian security
# update.
# hadolint ignore=DL3008
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils curl gh git jq just make openssh-server tar tini xz-utils \
 && rm -rf /var/lib/apt/lists/* /etc/ssh/ssh_host_* \
 && groupadd --gid 1001 coder \
 && useradd --uid 1001 --gid coder --home-dir /home/coder --no-create-home --shell /bin/bash coder \
 && install -d -o root -g root -m 0755 /etc/openclaw-devbox

# Node 24 and npm 12 for nabla-site-alban/-bababou (engines: node >=24.22.1 <25,
# npm >=12.2 <13; Debian ships node 20 without npm). Both pinned by SHA-256;
# npm is installed from its verified tarball, without registry access or scripts.
ARG NODE_VERSION=24.22.3
ARG NODE_SHA256=4f2b175a6d53a5c617a80dba2676238a0688cef28c6da4eba35c7d844e66fcfb
ARG NPM_VERSION=12.2.2
ARG NPM_SHA256=07fecbf753e2c3bc10ebeb3e9ed8738f6a0cc1292998b79e2e9f1dd2a5525e0c
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN test "$(dpkg --print-architecture)" = amd64 \
 && curl -fsSLo /tmp/node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
 && echo "${NODE_SHA256}  /tmp/node.tar.xz" | sha256sum -c - \
 && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 --no-same-owner \
      "node-v${NODE_VERSION}-linux-x64/bin" "node-v${NODE_VERSION}-linux-x64/lib" \
 && curl -fsSLo /tmp/npm.tgz "https://registry.npmjs.org/npm/-/npm-${NPM_VERSION}.tgz" \
 && echo "${NPM_SHA256}  /tmp/npm.tgz" | sha256sum -c - \
 && npm install --global --ignore-scripts --no-audit --no-fund --offline /tmp/npm.tgz \
 && rm /tmp/node.tar.xz /tmp/npm.tgz \
 && test "$(node --version)" = "v${NODE_VERSION}" \
 && test "$(npm --version)" = "${NPM_VERSION}"

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
