"""Offline tests for the Telegram channel repair (stubbed ssh, no Gateway)."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/heartbeat/restart-telegram-channel.sh"
STARTED = "2026-11-28T05:44:43.765+01:00 [telegram] [default] starting provider (@bot)"
FAILED = ("2026-11-28T07:42:44.455+01:00 [heartbeat] failed: Session binding owner changed "
          'for telegram:default error="Session binding owner changed for telegram:default"')


class TelegramChannelRepair(unittest.TestCase):
    def run_script(self, log_lines, *args):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "gateway.log").write_text("\n".join(log_lines) + "\n")
        ssh = tmp / "ssh"
        # Plays the remote shell on the fixture log and records every remote command.
        ssh.write_text(f'#!/usr/bin/env bash\necho "${{@: -1}}" >> {tmp}/calls\n'
                       f'cmd="${{@: -1}}"; cmd="${{cmd//sudo -n docker logs --since 24h openclaw-gateway/cat {tmp}/gateway.log}}"\n'
                       'case "$cmd" in *"gateway call"*) echo "{}" ;; *) bash -c "$cmd" ;; esac\n')
        ssh.chmod(0o755)
        result = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=30,
                                env={**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}"})
        calls = (tmp / "calls").read_text() if (tmp / "calls").exists() else ""
        return result, [c for c in ("channels.stop", "channels.start") if c in calls]

    def test_failure_after_last_start_is_broken_but_check_changes_nothing(self):
        result, calls = self.run_script([STARTED, FAILED])
        self.assertEqual(result.returncode, 1)
        self.assertIn("telegram_binding=broken since 2026-11-28T07:42", result.stdout)
        self.assertEqual(calls, [])

    def test_apply_restarts_the_channel_only(self):
        result, calls = self.run_script([STARTED, FAILED], "apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["channels.stop", "channels.start"])
        self.assertNotIn("docker restart", SCRIPT.read_text())

    def test_start_after_the_failure_is_healthy(self):
        result, calls = self.run_script([FAILED, STARTED], "apply")
        self.assertEqual((result.returncode, result.stdout.strip(), calls), (0, "telegram_binding=ok", []))


if __name__ == "__main__":
    unittest.main()
