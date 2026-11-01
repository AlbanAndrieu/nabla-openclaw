#!/usr/bin/env python3
"""Owner-only filesystem primitives shared by the Workstation GitOps scripts.

Helpers never follow a final symlink, never print file contents and report
problems as stable, value-free reason codes (``UnsafePath`` messages).
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
import stat
import tempfile

O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


class UnsafePath(ValueError):
    """Raised with a stable reason code, never with file contents."""


def file_safety(path: Path) -> str:
    """Return ``ok`` or why a file cannot be trusted as owner-controlled."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if not stat.S_ISREG(info.st_mode):
        return "not_regular"
    if info.st_uid != os.geteuid():
        return "foreign_owner"
    if info.st_mode & 0o020:
        return "writable_by_group"
    if info.st_mode & 0o002:
        return "writable_by_others"
    if info.st_nlink != 1:
        return "hardlinked"
    return "ok"


def owned_file(path: Path) -> bool:
    return file_safety(path) == "ok"


def _open_no_follow(path: Path) -> int:
    # O_NONBLOCK: a FIFO planted at the path must not hang the reader.
    try:
        return os.open(path, os.O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise UnsafePath("symlink_refused") from None
        raise


def read_regular(path: Path, *, allow_missing: bool = False) -> bytes | None:
    """Read a regular file (any owner/mode) without following a final symlink."""
    try:
        fd = _open_no_follow(path)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise UnsafePath("not_regular_file")
        return stream.read()


def read_owned(path: Path, max_bytes: int) -> bytes:
    """Read a non-empty, owner-only (see ``file_safety``) file of bounded size."""
    fd = _open_no_follow(path)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or info.st_nlink != 1):
            raise UnsafePath("unsafe_file")
        data = stream.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        raise UnsafePath("invalid_file_size")
    return data


def ensure_private_dir(base: Path, relative: str, *, strict_parents: bool) -> Path:
    """Create ``base/relative`` one component at a time, never through a symlink.

    Missing components are created 0700 and the leaf is forced to 0700. With
    ``strict_parents`` every component must be owned by the caller and not
    group/world-writable (existing unsafe parents are refused, not repaired).
    """
    current = base
    for name in Path(relative).parts:
        current = current / name
        if current.is_symlink():
            raise UnsafePath("directory_symlink_refused")
        if not current.exists():
            current.mkdir(mode=0o700)
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise UnsafePath("not_a_directory")
        if strict_parents and (info.st_uid != os.geteuid() or info.st_mode & 0o022):
            raise UnsafePath("shared_parent_directory")
    os.chmod(current, 0o700)
    return current


def create_private_file(path: Path, data: bytes) -> None:
    """Create ``path`` exclusively with mode 0600 (FileExistsError if present)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_replace(target: Path, data: bytes, *, expected: bytes | None,
                   allow_missing: bool) -> None:
    """Install ``data`` (0600) at ``target`` only if it still holds ``expected``."""
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Re-check just before the rename to avoid clobbering a concurrent edit.
        if read_regular(target, allow_missing=allow_missing) != expected:
            raise UnsafePath("target_changed_during_apply")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    directory = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
