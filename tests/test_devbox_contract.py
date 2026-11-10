"""Hermetic coder devbox contract: each rule fires on the regression it guards."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("devbox", ROOT / "scripts/check-devbox-contract.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pin_spec = importlib.util.spec_from_file_location("pin", ROOT / "scripts/coder/pin-devbox-images.py")
pin = importlib.util.module_from_spec(pin_spec)
pin_spec.loader.exec_module(pin)

FILES = (mod.CONTRACT, mod.SEED, mod.GATEWAY_COMPOSE, mod.REQUIREMENTS, mod.ALLOWLIST,
         "deploy/truenas/devbox/compose.yml", "deploy/truenas/devbox/sshd_config",
         "deploy/truenas/devbox/egress/squid.conf", "workspaces/coder/AGENTS.md",
         "workspaces/coder/skills/fastapi-sample-dev/SKILL.md")


class DevboxContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in FILES:
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.root / name)

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, name, old, new):
        path = self.root / name
        content = path.read_text()
        self.assertIn(old, content)
        path.write_text(content.replace(old, new, 1))

    def edit_json(self, name, change):
        path = self.root / name
        document = json.loads(path.read_text())
        change(document)
        path.write_text(json.dumps(document))

    def coder(self, change):
        self.edit_json(mod.SEED, lambda seed: change(seed["agents"]["entries"]["coder"]))

    def test_repository_has_no_violation(self):
        self.assertEqual(mod.violations(), [])
        self.assertEqual(mod.violations(self.root), [])

    def test_published_port_is_a_violation(self):
        self.edit("deploy/truenas/devbox/compose.yml", "    networks: [devbox]\n",
                  "    networks: [devbox]\n    ports:\n      - \"2222:2222\"\n")
        self.assertEqual(mod.violations(self.root), ["compose_hardened"])

    def test_docker_socket_mount_is_a_violation(self):
        self.edit("deploy/truenas/devbox/compose.yml", "        target: /home/coder\n",
                  "        target: /home/coder\n      - /var/run/docker.sock:/var/run/docker.sock\n")
        self.assertEqual(mod.violations(self.root), ["compose_hardened"])

    def test_devbox_with_internet_route_is_a_violation(self):
        self.edit("deploy/truenas/devbox/compose.yml", "    internal: true\n", "")
        self.assertEqual(mod.violations(self.root), ["network_internal"])

    def test_password_or_forwarding_is_a_violation(self):
        self.edit("deploy/truenas/devbox/sshd_config", "DisableForwarding yes", "DisableForwarding no")
        self.assertEqual(mod.violations(self.root), ["sshd_locked_down"])

    def test_unreviewed_domain_is_a_violation(self):
        self.edit(mod.ALLOWLIST, "files.pythonhosted.org\n", "files.pythonhosted.org\n.example.com\n")
        self.assertEqual(mod.violations(self.root), ["egress_allowlist_matches_contract"])

    def test_wildcard_or_ip_entry_is_a_violation_even_when_reviewed(self):
        for entry in ("*.example.com", "140.82.112.3", "com"):
            with self.subTest(entry=entry):
                self.tearDown()
                self.setUp()
                self.edit(mod.ALLOWLIST, "files.pythonhosted.org\n", f"files.pythonhosted.org\n{entry}\n")
                self.edit_json(mod.CONTRACT, lambda c: c["egress"]["allowed_domains"].append(entry))
                self.assertEqual(mod.violations(self.root), ["egress_allowlist_matches_contract"])

    def test_ip_literals_and_reverse_dns_must_stay_refused(self):
        for old, new in (("http_access deny ip_literal\n", ""),
                         ('dstdomain -n "/etc/squid/allowed-domains.txt"', 'dstdomain "/etc/squid/allowed-domains.txt"')):
            with self.subTest(old=old):
                self.tearDown()
                self.setUp()
                self.edit("deploy/truenas/devbox/egress/squid.conf", old, new)
                self.assertEqual(mod.violations(self.root), ["egress_allowlist_matches_contract"])

    def test_private_destinations_must_be_denied_before_allow(self):
        self.edit("deploy/truenas/devbox/egress/squid.conf",
                  "http_access deny private_destinations\n", "")
        self.assertEqual(mod.violations(self.root), ["egress_allowlist_matches_contract"])

    def test_elevated_or_unsandboxed_agent_is_a_violation(self):
        for change in (lambda a: a["tools"]["elevated"].update(enabled=True),
                       lambda a: a["sandbox"].update(mode="non-main"),
                       lambda a: a["sandbox"]["ssh"].update(strictHostKeyChecking=False),
                       lambda a: a["tools"]["sandbox"]["tools"]["allow"].append("sessions_send"),
                       lambda a: a["tools"]["deny"].remove("group:automation")):
            with self.subTest(change=change):
                self.tearDown()
                self.setUp()
                self.coder(change)
                self.assertEqual(mod.violations(self.root), ["gateway_agent_sandboxed"])

    def test_coder_key_must_be_its_own_file_secret_ref(self):
        for change in (lambda seed: seed["models"]["providers"]["litellm-coder"].update(
                           apiKey={"source": "env", "provider": "default", "id": "LITELLM_OPENCLAW_MAIN_API_KEY"}),
                       lambda seed: seed["secrets"]["providers"]["litellm-coder-key"].update(path="/tmp/coder.key")):
            with self.subTest(change=change):
                self.tearDown()
                self.setUp()
                self.edit_json(mod.SEED, change)
                self.assertEqual(mod.violations(self.root), ["gateway_agent_sandboxed"])

    def test_gateway_must_join_the_internal_network(self):
        self.edit(mod.GATEWAY_COMPOSE, "    networks: [litellm, devbox]\n", "    networks: [litellm]\n")
        self.assertEqual(mod.violations(self.root), ["gateway_joins_devbox_network"])

    def test_ready_or_active_requires_digest_pinned_base_images(self):
        compose = self.root / "deploy/truenas/devbox/compose.yml"
        # Independent of the repository state: start from unpinned base images.
        compose.write_text(re.sub(r"@sha256:[0-9a-f]{64}", "", compose.read_text()))
        for status in ("ready_to_deploy", "active"):
            self.edit_json(mod.CONTRACT, lambda c, status=status: c.update(status=status))
            self.assertEqual(mod.violations(self.root), ["images_pinned_when_active"])
        digest = "@sha256:" + "0" * 64
        self.edit("deploy/truenas/devbox/compose.yml", "PYTHON_IMAGE: python:3.13-slim-trixie",
                  "PYTHON_IMAGE: python:3.13-slim-trixie" + digest)
        self.edit("deploy/truenas/devbox/compose.yml", "DEBIAN_IMAGE: debian:trixie-slim",
                  "DEBIAN_IMAGE: debian:trixie-slim" + digest)
        self.assertEqual(mod.violations(self.root), [])

    def test_skill_name_must_match_agent_allowlist(self):
        self.edit("workspaces/coder/skills/fastapi-sample-dev/SKILL.md",
                  "name: fastapi-sample-dev", "name: other-skill")
        self.assertEqual(mod.violations(self.root), ["workspace_sources_exist"])


class PinDevboxImages(unittest.TestCase):
    def test_pins_both_base_images_and_repins_idempotently(self):
        compose = (ROOT / "deploy/truenas/devbox/compose.yml").read_text()
        digests = {"python:3.13-slim-trixie": "sha256:" + "a" * 64, "debian:trixie-slim": "sha256:" + "b" * 64}
        once = pin.pin(compose, digests.__getitem__)
        self.assertIn("PYTHON_IMAGE: python:3.13-slim-trixie@sha256:" + "a" * 64 + "\n", once)
        self.assertIn("DEBIAN_IMAGE: debian:trixie-slim@sha256:" + "b" * 64 + "\n", once)
        self.assertEqual(pin.pin(once, digests.__getitem__), once)
        self.assertEqual(len(once.splitlines()), len(compose.splitlines()))


if __name__ == "__main__":
    unittest.main()
