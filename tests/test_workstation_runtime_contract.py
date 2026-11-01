"""Offline contracts: Workstation Gateway runtime pin, diagnostics and wiring."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workstation"))
import openclaw_runtime as runtime  # noqa: E402


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alignment = load("oc_alignment", "scripts/workstation/check-openclaw-runtime-alignment.py")
host_context = load("oc_host", "scripts/workstation/openclaw-host-context.py")
CONTRACT = runtime.Contract("24.22.1", "2026.10.7")


def contract(directory, **override):
    repo = Path(directory)
    data = {"schema": runtime.SCHEMA, "node_version": "24.22.1",
            "openclaw_version": "2026.10.7", "systemd_unit": runtime.UNIT,
            "port": runtime.PORT}
    data.update(override)
    (repo / "deploy/workstation").mkdir(parents=True, exist_ok=True)
    (repo / runtime.CONTRACT).write_text(json.dumps(data))
    return repo


def install(home, version="24.22.1", mode=0o644, release="2026.10.7"):
    target = runtime.Install.for_version(version, home)
    target.entry.parent.mkdir(parents=True)
    target.node.parent.mkdir(parents=True)
    target.node.write_text("node")
    target.entry.write_text("cli")
    target.manifest.write_text(json.dumps({"name": "openclaw", "version": release,
                                           "bin": {"openclaw": "openclaw.mjs"}}))
    for path in (target.node, target.entry, target.manifest):
        path.chmod(mode)
    return target


class Contract(unittest.TestCase):
    def test_repository_contract_is_valid(self):
        self.assertEqual(runtime.load_contract(ROOT), CONTRACT)
        node, _ = runtime.pinned_cli_paths(ROOT, Path("/nonexistent"))
        self.assertEqual(node, Path("/nonexistent/.local/share/mise/installs/node/24.22.1/bin/node"))

    def test_invalid_contract_has_stable_reason_and_fails_closed(self):
        for override, reason in (({"schema": "x"}, "unexpected_contract_schema"),
                                 ({"node_version": "../24.22.1"}, "invalid_node_pin"),
                                 ({"openclaw_version": None}, "pin_mismatch"),
                                 ({"port": 8080}, "unexpected_service_contract")):
            with tempfile.TemporaryDirectory() as d:
                repo = contract(d, **override)
                with self.assertRaisesRegex(runtime.ContractError, reason):
                    runtime.load_contract(repo)
                node, _ = runtime.pinned_cli_paths(repo)
                self.assertIn(runtime.UNVERIFIED, str(node), override)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(runtime.ContractError, "unreadable_contract"):
                runtime.load_contract(Path(d))

    def test_install_issues_names_each_unsafe_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo, home = contract(d), Path(d) / "home"
            self.assertEqual(runtime.install_issues(repo, home),
                             "node:absent,openclaw_mjs:absent,package_json:absent")
            install(home, mode=0o664)
            self.assertEqual(runtime.install_issues(repo, home),
                             "node:writable_by_group,openclaw_mjs:writable_by_group,"
                             "package_json:writable_by_group")

    def test_read_cron_job_refuses_unsafe_install_without_executing(self):
        with tempfile.TemporaryDirectory() as d:
            node = Path(d) / "node"
            node.write_text("#!/bin/sh\nexit 0\n")
            node.chmod(0o775)
            self.assertEqual(runtime.read_cron_job("id", node, node),
                             ("unverified_installation", None))


class HostDetection(unittest.TestCase):
    def runner(self, version="", load_state="loaded"):
        return lambda argv: version if argv[0] == "midclt" else load_state

    def test_classification(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            self.assertEqual(runtime.detect_host(home, self.runner("TrueNAS-26.0.0")), "truenas")
            self.assertEqual(runtime.detect_host(home, self.runner()), "unknown")
            (home / ".openclaw").mkdir()
            (home / ".openclaw/openclaw.json").write_text("{}")
            self.assertEqual(runtime.detect_host(home, self.runner()), "workstation")
            self.assertEqual(runtime.detect_host(home, self.runner(load_state="not-found")), "unknown")

    def test_cli_output(self):
        with unittest.mock.patch.object(host_context, "detect_host", return_value="unknown"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(host_context.main([]), 2)
        self.assertIn("cross_host_openclaw_probe=blocked_unknown_host", output.getvalue())


class AlignmentGate(unittest.TestCase):
    def test_absent_install_reports_systemd_version_and_hint(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            install(home, version="24.23.0")
            unit = ("{ path=%s/.local/share/mise/installs/node/24.23.0/bin/node ; argv[]=... }" % home)
            report = alignment.classify(CONTRACT, home, runner=lambda argv: (0, unit))
        self.assertEqual(report["checks"]["node_binary"], "unsafe_or_absent")
        self.assertEqual(report["files"]["node"], "absent")
        self.assertEqual(report["systemd_node_version"], "24.23.0")
        self.assertEqual(report["installed_node_versions"], ["24.23.0"])
        self.assertEqual(report["hint"], "systemd_uses_other_node_update_contract_by_pr")

    def test_group_writable_install_is_blocked_not_executed(self):
        def runner(argv):
            if argv[0] != "systemctl":
                self.fail("unsafe install must not be executed")
            return 0, ""
        with tempfile.TemporaryDirectory() as d:
            install(Path(d), mode=0o775)
            report = alignment.classify(CONTRACT, Path(d), runner=runner)
        self.assertEqual(report["files"]["node"], "writable_by_group")
        self.assertEqual(report["hint"], "remove_group_and_other_write_on_install")
        self.assertEqual(report["systemd_node_version"], "unavailable")

    def test_pass_requires_versions_and_systemd_exec(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            target = install(home)
            unit = f"{{ path={target.node} ; argv[]={target.node} {target.entry} gateway --port 18789 ; }}"
            answers = {"systemctl": (0, unit), "--version": (0, "v24.22.1\n")}

            def runner(argv):
                if argv[0] == "systemctl":
                    return answers["systemctl"]
                return (0, "OpenClaw 2026.10.7\n") if len(argv) == 3 else answers["--version"]

            report = alignment.classify(CONTRACT, home, runner=runner)
            self.assertEqual(set(report["checks"].values()), {"match"})
            self.assertNotIn("hint", report)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = alignment.main([], repo=ROOT, home=home, runner=runner)
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual((result["alignment"], result["mutations"], result["model_requests"]),
                         ("PASS", 0, 0))

    def test_unverified_contract_is_reported(self):
        with tempfile.TemporaryDirectory() as d, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(alignment.main([], repo=Path(d), home=Path(d)), 2)
        self.assertEqual(json.loads(output.getvalue())["contract"], "unreadable_contract")

    def test_systemd_version_parsing(self):
        self.assertEqual(alignment.systemd_node_version(""), "unavailable")
        self.assertEqual(alignment.systemd_node_version("/usr/bin/node gateway"), "not_mise_managed")
        self.assertEqual(alignment.systemd_node_version(
            "/h/.local/share/mise/installs/node/24.1.0/bin/node /h/.local/share/mise/installs/node/24.2.0/bin/node"),
            "ambiguous")


class WorkstationWiring(unittest.TestCase):
    def test_no_tool_reads_nabla_compose_paths(self):
        for script in (ROOT / "scripts/workstation").glob("*.py"):
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("ops/openclaw-workstation", text, script.name)
            self.assertNotIn("mise.toml", text, script.name)
            self.assertNotIn("run_path", text, script.name)

    def test_systemd_start_gate_uses_this_checkout(self):
        unit = (ROOT / "deploy/workstation/systemd/30-nabla-runtime-alignment.conf.example").read_text()
        self.assertIn("ExecStartPre=/usr/bin/python3 %h/w/nabla-openclaw/scripts/workstation/"
                      "check-openclaw-runtime-alignment.py", unit)
        self.assertNotIn("nabla-compose", unit)

    def test_scripts_are_value_blind_and_shell_free(self):
        for script in (ROOT / "scripts/workstation").glob("*.py"):
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", text, script.name)
            self.assertNotIn("os.system", text, script.name)
            self.assertNotIn("set -x", text, script.name)


class SandboxImport(unittest.TestCase):
    def test_sandbox_files_at_submodule_root(self):
        compose = (ROOT / "compose.yml").read_text()
        self.assertIn("name: openclaw", compose)
        self.assertIn("openclaw-sandbox:", compose)
        self.assertIn("com.albandrieu.nabla.entity-ref: component:default/openclaw-sandbox", compose)
        self.assertTrue((ROOT / "Dockerfile").is_file())
        self.assertTrue(os.access(ROOT / "test-docker.sh", os.X_OK))

    def test_catalog_points_to_this_repository(self):
        catalog = (ROOT / "catalog-info.yaml").read_text()
        self.assertIn("name: openclaw-sandbox", catalog)
        self.assertIn("github.com/project-slug: AlbanAndrieu/nabla-openclaw", catalog)
        self.assertNotIn("nabla-compose", catalog)


if __name__ == "__main__":
    unittest.main()
