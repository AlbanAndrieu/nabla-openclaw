"""Offline contracts for owner-only filesystem primitives."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workstation"))
import private_files as pf  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.file = self.dir / "file"
        self.file.write_bytes(b"data")
        self.file.chmod(0o600)


class FileSafety(Fixture):
    def test_reason_codes(self):
        self.assertEqual(pf.file_safety(self.file), "ok")
        self.assertEqual(pf.file_safety(self.dir / "missing"), "absent")
        (self.dir / "link").symlink_to(self.file)
        self.assertEqual(pf.file_safety(self.dir / "link"), "symlink")
        self.assertEqual(pf.file_safety(self.dir), "not_regular")
        self.file.chmod(0o620)
        self.assertEqual(pf.file_safety(self.file), "writable_by_group")
        self.file.chmod(0o602)
        self.assertEqual(pf.file_safety(self.file), "writable_by_others")
        self.file.chmod(0o600)
        os.link(self.file, self.dir / "hard")
        self.assertEqual(pf.file_safety(self.file), "hardlinked")

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "needs root to chown")
    def test_foreign_owner(self):
        os.chown(self.file, 65534, 65534)
        self.assertEqual(pf.file_safety(self.file), "foreign_owner")


class Reads(Fixture):
    def test_read_regular_refuses_symlink_fifo_and_tolerates_missing(self):
        self.assertEqual(pf.read_regular(self.file), b"data")
        self.assertIsNone(pf.read_regular(self.dir / "missing", allow_missing=True))
        with self.assertRaises(FileNotFoundError):
            pf.read_regular(self.dir / "missing")
        (self.dir / "link").symlink_to(self.file)
        with self.assertRaisesRegex(pf.UnsafePath, "symlink_refused"):
            pf.read_regular(self.dir / "link")
        os.mkfifo(self.dir / "fifo")
        with self.assertRaisesRegex(pf.UnsafePath, "not_regular_file"):
            pf.read_regular(self.dir / "fifo")

    def test_read_owned_enforces_mode_and_size(self):
        self.assertEqual(pf.read_owned(self.file, 10), b"data")
        with self.assertRaisesRegex(pf.UnsafePath, "invalid_file_size"):
            pf.read_owned(self.file, 3)
        self.file.chmod(0o664)
        with self.assertRaisesRegex(pf.UnsafePath, "unsafe_file"):
            pf.read_owned(self.file, 10)


class Writes(Fixture):
    def test_create_private_file_is_exclusive_0600_and_no_follow(self):
        target = self.dir / "new"
        pf.create_private_file(target, b"secret")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            pf.create_private_file(target, b"other")
        (self.dir / "link").symlink_to(self.dir / "elsewhere")
        with self.assertRaises(FileExistsError):
            pf.create_private_file(self.dir / "link", b"x")
        self.assertFalse((self.dir / "elsewhere").exists())

    def test_ensure_private_dir(self):
        leaf = pf.ensure_private_dir(self.dir, "a/b", strict_parents=True)
        self.assertEqual(leaf, self.dir / "a/b")
        self.assertEqual(leaf.stat().st_mode & 0o777, 0o700)
        (self.dir / "a").chmod(0o775)
        with self.assertRaisesRegex(pf.UnsafePath, "shared_parent_directory"):
            pf.ensure_private_dir(self.dir, "a/b", strict_parents=True)
        self.assertEqual(pf.ensure_private_dir(self.dir, "a/b", strict_parents=False), leaf)
        (self.dir / "c").symlink_to(self.dir / "a")
        with self.assertRaisesRegex(pf.UnsafePath, "directory_symlink_refused"):
            pf.ensure_private_dir(self.dir, "c/b", strict_parents=False)
        with self.assertRaisesRegex(pf.UnsafePath, "not_a_directory"):
            pf.ensure_private_dir(self.dir, "file", strict_parents=False)

    def test_atomic_replace_detects_concurrent_change(self):
        pf.atomic_replace(self.file, b"new", expected=b"data", allow_missing=False)
        self.assertEqual(self.file.read_bytes(), b"new")
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(pf.UnsafePath, "target_changed_during_apply"):
            pf.atomic_replace(self.file, b"newer", expected=b"stale", allow_missing=False)
        self.assertEqual(self.file.read_bytes(), b"new")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["file"])


if __name__ == "__main__":
    unittest.main()
