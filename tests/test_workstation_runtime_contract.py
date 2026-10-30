"""Offline contracts: Workstation Gateway runtime pin and wiring point to this repo."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paths = load("oc_runtime_paths", "scripts/workstation/openclaw_runtime_paths.py")
alignment = load("oc_alignment", "scripts/workstation/check-openclaw-runtime-alignment.py")


def contract(directory, **override):
    repo = Path(directory)
    data = {"schema": "openclaw-workstation-runtime/v1", "node_version": "24.22.1",
            "openclaw_version": "2026.10.7", "systemd_unit": "openclaw-gateway.service",
            "port": 18789}
    data.update(override)
    target = repo / "deploy/workstation"
    target.mkdir(parents=True, exist_ok=True)
    (target / "runtime-contract.json").write_text(json.dumps(data))
    return repo


class RuntimePaths(unittest.TestCase):
    def test_match(self):
        with tempfile.TemporaryDirectory() as d:
            node, cli = paths.pinned_cli_paths(contract(d), Path(d) / "home")
            self.assertEqual(node, Path(d) / "home/.local/share/mise/installs/node/24.22.1/bin/node")
            self.assertTrue(str(cli).endswith("24.22.1/lib/node_modules/openclaw/openclaw.mjs"))

    def test_malformed_or_missing_contract_fails_closed(self):
        for override in ({"node_version": "../24.22.1"}, {"port": 8080},
                         {"schema": "other"}, {"openclaw_version": "latest"}):
            with tempfile.TemporaryDirectory() as d:
                node, _ = paths.pinned_cli_paths(contract(d, **override))
                self.assertIn("__unverified_openclaw_runtime__", str(node), override)
        with tempfile.TemporaryDirectory() as d:
            node, _ = paths.pinned_cli_paths(Path(d))
            self.assertIn("__unverified_openclaw_runtime__", str(node))

    def test_repository_contract_is_valid(self):
        node, _ = paths.pinned_cli_paths(ROOT, Path("/nonexistent"))
        self.assertNotIn("__unverified_openclaw_runtime__", str(node))
        self.assertEqual(alignment.expected(ROOT), ("24.22.1", "2026.10.7"))


class AlignmentGate(unittest.TestCase):
    def test_expected_rejects_invalid_contract(self):
        for override, reason in (({"schema": "x"}, "unexpected_contract_schema"),
                                 ({"node_version": "24"}, "invalid_node_pin"),
                                 ({"openclaw_version": None}, "pin_mismatch"),
                                 ({"port": 1}, "unexpected_service_contract")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(ValueError, reason):
                    alignment.expected(contract(d, **override))

    def test_absent_install_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            checks = alignment.classify("24.22.1", "2026.10.7", Path(d),
                                        runner=lambda argv: self.fail("must not execute"))
        self.assertEqual(checks["node_binary"], "unsafe_or_absent")


class WorkstationWiring(unittest.TestCase):
    def test_no_tool_reads_nabla_compose_paths(self):
        for script in (ROOT / "scripts/workstation").glob("*.py"):
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("ops/openclaw-workstation", text, script.name)
            self.assertNotIn("mise.toml", text.replace("(no duplicated mise.toml)", ""), script.name)

    def test_systemd_start_gate_uses_this_checkout(self):
        unit = (ROOT / "deploy/workstation/systemd/30-nabla-runtime-alignment.conf.example").read_text()
        self.assertIn("ExecStartPre=/usr/bin/python3 %h/w/nabla-openclaw/scripts/workstation/"
                      "check-openclaw-runtime-alignment.py", unit)
        self.assertNotIn("nabla-compose", unit)
        self.assertTrue((ROOT / "scripts/workstation/check-openclaw-runtime-alignment.py").is_file())


class SandboxImport(unittest.TestCase):
    def test_sandbox_files_at_submodule_root(self):
        # Mounted later as nabla-compose/apps/openclaw: paths stay apps/openclaw/<file>.
        compose = (ROOT / "compose.yml").read_text()
        self.assertIn("name: openclaw", compose)
        self.assertIn("openclaw-sandbox:", compose)
        self.assertIn("com.albandrieu.nabla.entity-ref: component:default/openclaw-sandbox", compose)
        self.assertTrue((ROOT / "Dockerfile").is_file())
        self.assertTrue((ROOT / "test-docker.sh").stat().st_mode & 0o111)

    def test_catalog_points_to_this_repository(self):
        catalog = (ROOT / "catalog-info.yaml").read_text()
        self.assertIn("name: openclaw-sandbox", catalog)
        self.assertIn("github.com/project-slug: AlbanAndrieu/nabla-openclaw", catalog)
        self.assertNotIn("nabla-compose", catalog)


if __name__ == "__main__":
    unittest.main()
