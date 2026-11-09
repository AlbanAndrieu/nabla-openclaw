#!/usr/bin/env python3
"""Pin the devbox base images (PYTHON_IMAGE, DEBIAN_IMAGE) to their index digests.

Run where the registry is reachable (Workstation): rewrites
deploy/truenas/devbox/compose.yml in place, then review and commit the diff.
"""
from pathlib import Path
import re
import subprocess
import sys

COMPOSE = Path(__file__).resolve().parents[2] / "deploy/truenas/devbox/compose.yml"
PIN = re.compile(r"^(\s+(?:PYTHON|DEBIAN)_IMAGE: )(\S+?)(@sha256:[0-9a-f]{64})?$", re.M)


def registry_digest(reference):
    proc = subprocess.run(["docker", "buildx", "imagetools", "inspect", reference,
                           "--format", "{{.Manifest.Digest}}"],
                          capture_output=True, text=True, timeout=60, check=False)
    digest = proc.stdout.strip()
    if proc.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError(f"digest_unavailable reference={reference}")
    return digest


def pin(text, resolve=registry_digest):
    return PIN.sub(lambda m: f"{m.group(1)}{m.group(2)}@{resolve(m.group(2))}", text)


def main():
    original = COMPOSE.read_text(encoding="utf-8")
    try:
        pinned = pin(original)
    except RuntimeError as error:
        print(error)
        return 2
    COMPOSE.write_text(pinned, encoding="utf-8")
    for line in PIN.finditer(pinned):
        print("pinned=" + line.group(2) + line.group(3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
