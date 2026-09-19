"""Isolated runtime log checks using synthetic files; no IRIS or real logs."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import fieldwork_runtime as runtime


BACKEND_PATH = Path(__file__).resolve().parents[1] / "app" / "backend.py"
sys.path.insert(0, str(BACKEND_PATH.parent))
BACKEND_SPEC = importlib.util.spec_from_file_location("fieldwork_runtime_test_backend", BACKEND_PATH)
backend = importlib.util.module_from_spec(BACKEND_SPEC)
sys.modules[BACKEND_SPEC.name] = backend
BACKEND_SPEC.loader.exec_module(backend)


class RuntimeLogsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fieldwork-runtime-test-")
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.client = backend.IRISClient({"IRIS_USERNAME": "fixture_user", "IRIS_PASSWORD": "fixture_password"})

    def tearDown(self):
        self.temporary.cleanup()

    def collect(self, content):
        source = self.root / "synthetic.log"
        source.write_bytes(content)
        with patch.object(runtime, "SOURCES", [("Synthetic fixture", str(source))]):
            payload = json.loads(runtime.logs())
        self.assertEqual(payload["status"]["errors"], [])
        self.assertEqual(len(payload["result"]), 1)
        return payload["result"][0]

    def test_adapter_to_gateway_redacts_whole_sensitive_lines(self):
        fixtures = [
            "Authorization: Bearer short_fixture_token",
            "Authorization: Basic short_fixture_base64",
            "Authorization: [redacted] old_adapter_fixture_token",
            'password="fixture secret with spaces"',
            '{"access_token": "fixture_token_value", "expires": 3600}',
            "client-secret = fixture_client_value",
            "Cookie: sid=fixture_session_value; extra=fixture_more",
            "Set-Cookie: sid=fixture_session_value; HttpOnly",
            "api_key=fixture_api_value",
        ]
        ordinary = "Ordinary startup completed successfully"
        entry = self.collect(("\n".join([ordinary, *fixtures]) + "\n").encode())
        adapter_lines = [row["line"] for row in entry["records"]]
        gateway_lines = [self.client.clean_log(line) for line in adapter_lines]
        self.assertEqual(adapter_lines[0], ordinary)
        self.assertEqual(gateway_lines[0], ordinary)
        self.assertTrue(all(line == "[sensitive log line withheld]" for line in adapter_lines[1:]))
        self.assertTrue(all(line == "[sensitive log line withheld]" for line in gateway_lines[1:]))
        self.assertNotIn("fixture_", json.dumps(gateway_lines))

    def test_sensitive_assignment_is_checked_before_line_length_clamp(self):
        # A late assignment must not leak its earlier context when the line is clamped.
        line = "ordinary context " * 150 + "password=fixture_late_secret"
        entry = self.collect((line + "\n").encode())
        self.assertEqual(entry["records"], [{"line": "[sensitive log line withheld]"}])

    def test_row_and_byte_tail_limits_keep_only_complete_recent_lines(self):
        old = ("old record " + "x" * 900 + "\n") * 100
        recent = [f"recent record {index:03d}" for index in range(100)]
        entry = self.collect((old + "\n".join(recent) + "\n").encode())
        self.assertEqual(entry["state"], "ok")
        self.assertTrue(entry["truncated"])
        self.assertEqual([row["line"] for row in entry["records"]], recent[-80:])

    def test_single_line_over_byte_limit_does_not_emit_partial_record(self):
        entry = self.collect(b"x" * 70000)
        self.assertEqual(entry["state"], "ok")
        self.assertTrue(entry["truncated"])
        self.assertEqual(entry["records"], [])

    def test_untruncated_ordinary_lines_keep_readable_content(self):
        entry = self.collect(b"Starting service\nRequest completed\n")
        self.assertFalse(entry["truncated"])
        self.assertEqual(entry["records"], [{"line": "Starting service"}, {"line": "Request completed"}])

    def test_missing_source_is_explicit_and_contains_no_records(self):
        with patch.object(runtime, "SOURCES", [("Missing synthetic fixture", str(self.root / "absent.log"))]):
            entry = json.loads(runtime.logs())["result"][0]
        self.assertEqual(entry["state"], "not_present")
        self.assertEqual(entry["records"], [])


if __name__ == "__main__":
    unittest.main()
