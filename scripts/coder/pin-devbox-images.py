#!/usr/bin/env python3
"""Pin the devbox base images (PYTHON_IMAGE, DEBIAN_IMAGE) to their index digests.

Rewrites deploy/truenas/devbox/compose.yml in place; review and commit the diff.
Resolvers, first success wins, every failure printed on stderr:
  DEVBOX_PIN_<ARG>=sha256:...  explicit digest, e.g. DEVBOX_PIN_PYTHON_IMAGE
  registry_api                 HEAD on the registry v2 API, anonymous token, no Docker
  buildx, crane, docker_pull   local tools, when installed
`--via HOST` resolves on HOST over SSH instead (this script on stdin, then
`sudo -n docker pull`); `--resolve REF...` only prints "REF DIGEST" lines.
"""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PIN = re.compile(r"^(\s+((?:PYTHON|DEBIAN)_IMAGE): )(\S+?)(@sha256:[0-9a-f]{64})?$", re.M)
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
# Index types first: the pin must stay multi-arch.
ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))
HINT = "retry: just devbox-pin --via truenas, or DEVBOX_PIN_<ARG>=sha256:... just devbox-pin"


class Unresolved(RuntimeError):
    pass


def split_reference(reference):
    """python:3.13 -> (registry-1.docker.io, library/python, 3.13)."""
    name, _, tag = reference.rpartition(":")
    if not name or "/" in tag:
        raise Unresolved(f"tag_missing reference={reference}")
    first, _, rest = name.partition("/")
    host, path = (first, rest) if rest and ("." in first or ":" in first or first == "localhost") else ("docker.io", name)
    if host == "docker.io":
        host, path = "registry-1.docker.io", path if "/" in path else "library/" + path
    return host, path, tag


def checked(digest, source):
    digest = (digest or "").strip()
    if not DIGEST.fullmatch(digest):
        raise Unresolved(f"{source} returned no sha256 digest")
    return digest


def registry_api(reference, base=None, timeout=20):
    """Docker-Content-Digest of the tag; HEAD does not count against Docker Hub pull limits."""
    host, path, tag = split_reference(reference)
    base = base or f"https://{host}"
    url = f"{base}/v2/{path}/manifests/{urllib.parse.quote(tag)}"

    def head(headers):
        request = urllib.request.Request(url, method="HEAD", headers={"Accept": ACCEPT, **headers})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return checked(response.headers.get("Docker-Content-Digest"), "registry_api")

    try:
        return head({})
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        challenge = error.headers.get("WWW-Authenticate", "")
    return head({"Authorization": "Bearer " + anonymous_token(challenge, base, path, timeout)})


def anonymous_token(challenge, base, path, timeout):
    scheme, _, params = challenge.partition(" ")
    fields = dict(re.findall(r'(\w+)="([^"]*)"', params))
    realm = fields.pop("realm", "")
    # No credential is ever sent; the realm must still not downgrade the registry scheme.
    if scheme.lower() != "bearer" or urllib.parse.urlparse(realm).scheme not in {"https", urllib.parse.urlparse(base).scheme}:
        raise Unresolved(f"registry_api unsupported auth challenge '{scheme or 'none'}'")
    fields.setdefault("scope", f"repository:{path}:pull")
    with urllib.request.urlopen(f"{realm}?{urllib.parse.urlencode(fields)}", timeout=timeout) as response:
        body = json.load(response)
    token = body.get("token") or body.get("access_token")
    if not token:
        raise Unresolved("registry_api token endpoint returned no token")
    return token


def run(argv, source, timeout=120):
    if shutil.which(argv[0]) is None:
        raise Unresolved(f"{source} {argv[0]} not installed")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise Unresolved(f"{source} timeout after {timeout}s") from None
    if proc.returncode:
        lines = [line.strip() for line in (proc.stderr or proc.stdout).splitlines() if line.strip()]
        raise Unresolved(f"{source} exit={proc.returncode} {lines[-1][:300] if lines else '(no output)'}")
    return proc.stdout


def buildx(reference):
    out = run(["docker", "buildx", "imagetools", "inspect", reference, "--format", "{{json .Manifest}}"], "buildx")
    return checked(json.loads(out).get("digest"), "buildx")


def crane(reference):
    return checked(run(["crane", "digest", reference], "crane"), "crane")


def docker_pull(reference, wrap=list):
    """Pulling by tag records the index digest in RepoDigests."""
    run(wrap(["docker", "pull", "-q", reference]), "docker_pull", timeout=600)
    out = run(wrap(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", reference]), "docker_pull")
    return repo_digest(reference, json.loads(out))


def repo_digest(reference, repo_digests):
    wanted = split_reference(reference)[:2]
    for entry in repo_digests or []:
        name, _, digest = entry.partition("@")
        try:
            if split_reference(name + ":tag")[:2] == wanted:
                return checked(digest, "docker_pull")
        except Unresolved:
            continue
    raise Unresolved(f"docker_pull no RepoDigest for {'/'.join(wanted)}")


LOCAL = (("registry_api", registry_api), ("buildx", buildx), ("crane", crane), ("docker_pull", docker_pull))


def via(host):
    ssh = ["ssh", "-o", "BatchMode=yes", host]

    def remote_script(reference):
        proc = subprocess.run([*ssh, shlex.join(["python3", "-", "--resolve", reference])],
                              input=Path(__file__).read_text(encoding="utf-8"),
                              capture_output=True, text=True, timeout=300, check=False)
        for line in proc.stderr.splitlines():
            print(f"  {host}: {line}", file=sys.stderr)
        if proc.returncode:
            raise Unresolved(f"{host}:script exit={proc.returncode}")
        _, _, digest = proc.stdout.strip().partition(" ")
        return checked(digest, f"{host}:script")

    def remote_pull(reference):
        return docker_pull(reference, lambda argv: [*ssh, shlex.join(["sudo", "-n", *argv])])

    return ((f"{host}:script", remote_script), (f"{host}:docker_pull", remote_pull))


def resolve_first(reference, resolvers):
    for name, resolver in resolvers:
        try:
            digest = resolver(reference)
        except (Unresolved, OSError, ValueError) as error:
            print(f"resolver={name} reference={reference} error={error}", file=sys.stderr)
            continue
        print(f"resolver={name} reference={reference} digest={digest}", file=sys.stderr)
        return digest
    raise Unresolved(f"digest_unavailable reference={reference} ({HINT})")


def pin(text, resolve, env=None):
    env = os.environ if env is None else env

    def replace(match):
        prefix, arg, reference = match.group(1, 2, 3)
        override = env.get(f"DEVBOX_PIN_{arg}")
        digest = checked(override, f"DEVBOX_PIN_{arg}") if override else resolve(reference)
        return f"{prefix}{reference}@{digest}"

    return PIN.sub(replace, text)


def main(args):
    try:
        if args[:1] == ["--resolve"] and len(args) > 1:
            for reference in args[1:]:
                print(reference, resolve_first(reference, LOCAL))
            return 0
        if args and (args[0] != "--via" or len(args) != 2):
            print("usage: pin-devbox-images.py [--via HOST | --resolve REF...]")
            return 2
        resolvers = via(args[1]) if args else LOCAL
        compose = Path(__file__).resolve().parents[2] / "deploy/truenas/devbox/compose.yml"
        pinned = pin(compose.read_text(encoding="utf-8"), lambda reference: resolve_first(reference, resolvers))
    except Unresolved as error:
        print(error)
        return 2
    compose.write_text(pinned, encoding="utf-8")
    for match in PIN.finditer(pinned):
        print(f"pinned={match.group(3)}{match.group(4)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
