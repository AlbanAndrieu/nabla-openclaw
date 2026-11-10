"""Hermetic coder devbox contract: each rule fires on the regression it guards."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unittest
import urllib.parse

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


A, B, C = ("sha256:" + c * 64 for c in "abc")


class FakeRegistry(BaseHTTPRequestHandler):
    """Registry v2 with a Bearer challenge, like Docker Hub."""
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        FakeRegistry.requests.append(("GET", url.path, dict(urllib.parse.parse_qsl(url.query))))
        body = json.dumps({"token": "anonymous-pull"}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        FakeRegistry.requests.append(("HEAD", self.path, self.headers.get("Accept", "")))
        if self.path != "/v2/library/python/manifests/3.13-slim-trixie":
            self.send_response(404)
        elif self.headers.get("Authorization") != "Bearer anonymous-pull":
            self.send_response(401)
            realm = f"http://127.0.0.1:{self.server.server_port}/token"
            self.send_header("WWW-Authenticate", f'Bearer realm="{realm}",service="registry.docker.io"')
        else:
            self.send_response(200)
            self.send_header("Docker-Content-Digest", A)
        self.send_header("Content-Length", "0")
        self.end_headers()


class PinDevboxImages(unittest.TestCase):
    def test_pins_both_base_images_and_repins_idempotently(self):
        compose = (ROOT / "deploy/truenas/devbox/compose.yml").read_text()
        digests = {"python:3.13-slim-trixie": A, "debian:trixie-slim": B}
        once = pin.pin(compose, digests.__getitem__, env={})
        self.assertIn("PYTHON_IMAGE: python:3.13-slim-trixie@" + A + "\n", once)
        self.assertIn("DEBIAN_IMAGE: debian:trixie-slim@" + B + "\n", once)
        self.assertEqual(pin.pin(once, digests.__getitem__, env={}), once)
        self.assertEqual(len(once.splitlines()), len(compose.splitlines()))

    def test_explicit_digest_overrides_skip_resolution_and_are_validated(self):
        compose = (ROOT / "deploy/truenas/devbox/compose.yml").read_text()
        env = {"DEVBOX_PIN_PYTHON_IMAGE": C, "DEVBOX_PIN_DEBIAN_IMAGE": B}
        pinned = pin.pin(compose, lambda reference: self.fail("resolver called"), env=env)
        self.assertIn("python:3.13-slim-trixie@" + C, pinned)
        with self.assertRaisesRegex(pin.Unresolved, "DEVBOX_PIN_PYTHON_IMAGE"):
            pin.pin(compose, lambda reference: B, env={"DEVBOX_PIN_PYTHON_IMAGE": "latest"})

    def test_references_resolve_to_registry_repository_and_tag(self):
        self.assertEqual(pin.split_reference("python:3.13-slim-trixie"),
                         ("registry-1.docker.io", "library/python", "3.13-slim-trixie"))
        self.assertEqual(pin.split_reference("docker.io/library/debian:trixie-slim"),
                         ("registry-1.docker.io", "library/debian", "trixie-slim"))
        self.assertEqual(pin.split_reference("ghcr.io/openclaw/openclaw:2026.10.7"),
                         ("ghcr.io", "openclaw/openclaw", "2026.10.7"))
        self.assertEqual(pin.split_reference("localhost:5000/devbox:1"), ("localhost:5000", "devbox", "1"))
        with self.assertRaises(pin.Unresolved):
            pin.split_reference("localhost:5000/devbox")

    def test_registry_api_follows_the_bearer_challenge_and_asks_for_the_index(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRegistry)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        FakeRegistry.requests = []
        base = f"http://127.0.0.1:{server.server_port}"
        self.assertEqual(pin.registry_api("python:3.13-slim-trixie", base=base), A)
        (_, _, accept), token, _ = FakeRegistry.requests
        self.assertTrue(accept.startswith("application/vnd.oci.image.index.v1+json"))
        self.assertEqual(token[2], {"service": "registry.docker.io", "scope": "repository:library/python:pull"})
        with self.assertRaises(pin.urllib.error.HTTPError):
            pin.registry_api("python:missing", base=base)

    def test_token_realm_cannot_downgrade_an_https_registry(self):
        with self.assertRaisesRegex(pin.Unresolved, "unsupported auth challenge"):
            pin.anonymous_token('Bearer realm="http://auth.example/token"', "https://registry", "library/python", 5)
        with self.assertRaisesRegex(pin.Unresolved, "unsupported auth challenge"):
            pin.anonymous_token('Basic realm="registry"', "https://registry", "library/python", 5)

    def test_resolver_chain_reports_each_failure_and_stops_at_first_digest(self):
        def broken(reference):
            raise pin.Unresolved("buildx exit=1 ERROR: permission denied")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(pin.resolve_first("python:3", [("one", broken), ("two", lambda r: B),
                                                           ("three", lambda r: self.fail("not reached"))]), B)
            with self.assertRaisesRegex(pin.Unresolved, "digest_unavailable reference=python:3 .*--via truenas"):
                pin.resolve_first("python:3", [("one", broken), ("two", lambda r: (_ for _ in ()).throw(OSError("dns")))])
        self.assertIn("resolver=one reference=python:3 error=buildx exit=1 ERROR: permission denied", stderr.getvalue())
        self.assertIn("resolver=two reference=python:3 digest=" + B, stderr.getvalue())
        self.assertIn("resolver=two reference=python:3 error=dns", stderr.getvalue())

    def test_repo_digest_matches_the_pulled_repository(self):
        entries = ["registry.example/python@" + C, "python@" + A]
        self.assertEqual(pin.repo_digest("docker.io/library/python:3.13", entries), A)
        with self.assertRaises(pin.Unresolved):
            pin.repo_digest("debian:trixie-slim", entries)

    def test_cli_rejects_unknown_arguments_without_touching_compose(self):
        compose = ROOT / "deploy/truenas/devbox/compose.yml"
        before = compose.read_text()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pin.main(["--via"]), 2)
            self.assertEqual(pin.main(["--resolve"]), 2)
        self.assertEqual(compose.read_text(), before)


if __name__ == "__main__":
    unittest.main()
