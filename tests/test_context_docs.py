"""Contract tests for context size, path safety and grandfathered LOC enforcement."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_repo_docs import inspect_repo
from context_pack import build_pack, main
from context_policy import inspect_limits, load_policy, safe_file


class ContextDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("AGENTS.md", "CHECKPOINT.md", "CONTEXT-MAP.md", "CONTEXT.md",
                     "docs/features/demo.md", "driver_monitor/demo.py", "tests/test_demo.py"):
            self.write(name, "# Valid fixture\n")
        self.write("driver_monitor/demo.py", "SOURCE_MARKER = 'not included by default'\n")
        self.policy = {"schema_version": 1, "context": {
            "startup_files": ["AGENTS.md", "CHECKPOINT.md", "CONTEXT-MAP.md"],
            "startup_max_bytes": 2000, "pack_max_bytes": 6000,
            "pack_hard_max_bytes": 12000, "max_files": 12}, "rules": [
                {"patterns": ["*.md"], "max_lines": 180, "max_bytes": 18000},
                {"patterns": ["driver_monitor/*", "tests/*", "frontend/*"], "max_lines": 400, "max_bytes": 24000}],
            "legacy_exceptions": {}}
        self.features = {"demo": {"summary": "one feature", "doc": "docs/features/demo.md",
                                  "sources": ["driver_monitor/demo.py"],
                                  "tests": ["tests/test_demo.py"], "related": []}}
        self.save()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def save(self):
        self.write("docs/engineering/limits.json", json.dumps(self.policy))
        self.write("docs/feature-map.json", json.dumps({"schema_version": 1, "features": self.features}))

    def test_default_cli_lists_paths_without_source_contents(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = main(["--root", str(self.root), "--feature", "demo"])
        self.assertEqual(result, 0)
        self.assertNotIn("SOURCE_MARKER", stream.getvalue())
        value = json.loads(stream.getvalue())
        self.assertIsNone(value["token_count"])
        self.assertEqual(value["file_count"], 4)

    def test_selected_source_and_test_are_deduplicated(self):
        self.features["demo"]["sources"].append("AGENTS.md")
        self.save()
        result = build_pack(self.root, "demo", include_source=True, include_tests=True)
        self.assertIn("SOURCE_MARKER", result["text"])
        self.assertEqual(result["file_count"], 6)
        self.assertEqual(result["text"].count("--- FILE: AGENTS.md ---"), 1)

    def test_utf8_budget_counts_full_payload_and_never_truncates(self):
        self.write("docs/features/demo.md", "Tài xế nhắm mắt.\n" * 20)
        packet = build_pack(self.root, "demo")
        self.assertEqual(packet["payload_bytes"], len(packet["text"].encode("utf-8")))
        self.assertGreater(packet["payload_bytes"], len(packet["text"]))
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            build_pack(self.root, "demo", max_bytes=packet["payload_bytes"] - 1)

    def test_expansion_cannot_override_hard_cap(self):
        for value in (0, -1, 12001, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_pack(self.root, "demo", max_bytes=value)

    def test_private_and_outside_paths_are_rejected_before_reading(self):
        for name in ("../outside.py", "/outside.py", "C:/outside.py", ".env", ".env.local",
                     "logs/run.jsonl", ".dashboard-token", "models/model.onnx",
                     "data_collection/eye/video.avi", ".venv/secret.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_file(self.root, name)

    def test_selected_manifest_cannot_smuggle_private_source(self):
        self.features["demo"]["sources"] = ["logs/private.jsonl"]
        self.save()
        with self.assertRaisesRegex(ValueError, "excluded"):
            build_pack(self.root, "demo", include_source=True)

    def test_windows_case_variants_cannot_include_existing_private_files(self):
        for name in ("LOGS/private.json", ".ENV", ".KAGGLE/kaggle.json", "CREDENTIALS/settings.json"):
            self.write(name, "test-only fixture content\n")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "excluded"):
                safe_file(self.root, name)

    def test_missing_feature_and_missing_source_fail(self):
        with self.assertRaisesRegex(ValueError, "Unknown feature"):
            build_pack(self.root, "missing")
        (self.root / "driver_monitor/demo.py").unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            build_pack(self.root, "demo")

    def test_too_many_files_fails_instead_of_silently_dropping_inputs(self):
        self.policy["context"]["max_files"] = 5
        self.save()
        with self.assertRaisesRegex(ValueError, "6 files > 5"):
            build_pack(self.root, "demo", include_source=True, include_tests=True)

    def test_new_large_source_fails_loc_guard(self):
        self.write("driver_monitor/large.py", "value = 1\n" * 401)
        result = inspect_limits(self.root, load_policy(self.root))
        self.assertTrue(any("large.py: 401 lines > 400" in error for error in result["errors"]))

    def test_long_single_line_cannot_bypass_byte_guard(self):
        self.write("driver_monitor/large.py", "x" * 24001)
        result = inspect_limits(self.root, load_policy(self.root))
        self.assertTrue(any("24001 bytes > 24000" in error for error in result["errors"]))

    def test_legacy_ceiling_is_fixed_and_does_not_transfer_to_new_file(self):
        self.write("driver_monitor/legacy.py", "x\n" * 410)
        self.policy["legacy_exceptions"]["driver_monitor/legacy.py"] = {
            "max_lines": 410, "max_bytes": 24000, "reason": "fixture legacy"}
        self.save()
        self.assertFalse(inspect_limits(self.root, load_policy(self.root))["errors"])
        self.write("driver_monitor/legacy.py", "x\n" * 411)
        self.write("driver_monitor/new.py", "x\n" * 410)
        errors = inspect_limits(self.root, load_policy(self.root))["errors"]
        self.assertTrue(any("legacy.py: 411 lines > 410" in error for error in errors))
        self.assertTrue(any("new.py: 410 lines > 400" in error for error in errors))

    def test_guard_checks_links_startup_and_all_feature_packs(self):
        self.assertTrue(inspect_repo(self.root)["passed"])
        self.write("docs/features/demo.md", "[broken](missing.md)\n")
        result = inspect_repo(self.root)
        self.assertFalse(result["passed"])
        self.assertTrue(any("Broken/outside local link" in error for error in result["errors"]))
        self.write("docs/features/demo.md", "# Valid again\n")
        self.policy["context"]["startup_max_bytes"] = 1
        self.save()
        self.assertTrue(any("Startup context" in error for error in inspect_repo(self.root)["errors"]))

    def test_expo_android_is_generated_but_config_plugins_are_source(self):
        generated = "frontend/mobile/android/app/.cxx/CompilerIdCXX.cpp"
        self.write(generated, "generated\n" * 1000)
        self.write("frontend/mobile/plugins/lan.cjs", "const source = 1;\n" * 401)
        errors = inspect_limits(self.root, load_policy(self.root))["errors"]
        self.assertFalse(any("CompilerIdCXX" in error for error in errors))
        self.assertTrue(any("lan.cjs: 401 lines > 400" in error for error in errors))
        with self.assertRaisesRegex(ValueError, "excluded"):
            safe_file(self.root, generated)

    def test_generated_trees_are_outside_source_loc_scan(self):
        self.write("frontend/web/dist/generated.js", "x\n" * 1000)
        self.write("frontend/node_modules/vendor/index.js", "x\n" * 1000)
        self.assertFalse(inspect_limits(self.root, load_policy(self.root))["errors"])


class RepositoryDocumentationTests(unittest.TestCase):
    def test_actual_repository_obeys_docs_loc_and_context_contract(self):
        result = inspect_repo(Path(__file__).resolve().parents[1])
        self.assertTrue(result["passed"], "\n".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
