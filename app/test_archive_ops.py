"""Archive gateway tests using synthetic responses and a local HTTP server."""
import copy
import http.client
import json
import threading
import unittest
from unittest.mock import patch

import archive_ops as a
import backend as b
from test_backend import FakeClient, Response, success


NAME = "messages.old_20260924_1"
REVISION = "a" * 64
FILE = {"name": NAME, "revision": REVISION, "sizeBytes": 1000, "modifiedAt": "2026-09-24T04:00:00+00:00"}
INVENTORY = {"state": "ok", "files": [FILE], "offset": 0, "nextOffset": None, "total": 1, "scope": "Synthetic archive inventory"}
PAGE = {"state": "ok", "name": NAME, "revision": REVISION, "sizeBytes": 1000, "offset": 0, "nextOffset": 100,
        "records": [{"line": "Synthetic startup completed"}], "omitted": {"oversizeSegments": 0, "partialSegments": 0, "binaryRecords": 0},
        "skippedBytes": 0, "scope": "Synthetic byte page"}


class ArchiveGatewayTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.gateway = b.Gateway(self.client)
        self.client.reads[a.INVENTORY] = success({"result": copy.deepcopy(INVENTORY)})
        self.client.reads[a.CONTENT] = success({"result": copy.deepcopy(PAGE)})

    def read(self, **overrides):
        return self.gateway.message_archives({"name": NAME, "revision": REVISION, **overrides}, content=True)

    def test_only_exact_archive_reads_are_allowlisted(self):
        real = b.IRISClient({"IRIS_USERNAME": "fixture", "IRIS_PASSWORD": "fixture-password"})
        with patch.object(b.http.client, "HTTPConnection") as connection:
            connection.return_value.getresponse.return_value = Response({"result": PAGE})
            real.fetch("GET", a.CONTENT, {"name": NAME, "revision": REVISION, "offset": "0"})
            route = connection.return_value.request.call_args.args[1]
            self.assertTrue(route.startswith(a.CONTENT + "?"))
            self.assertNotIn("/api/admin", route)
            connection.reset_mock()
            for query in ({"name": "../messages.old_1", "revision": REVISION, "offset": "0"},
                          {"name": "messages.old_a..b", "revision": REVISION, "offset": "0"},
                          {"name": NAME, "revision": REVISION, "offset": "0", "path": "/etc/passwd"},
                          {"name": NAME, "revision": REVISION, "offset": "-1"},
                          {"name": NAME, "revision": REVISION, "offset": "00"},
                          {"name": NAME, "revision": "unverified", "offset": "0"}):
                with self.subTest(query=query), self.assertRaises(ValueError):
                    real.fetch("GET", a.CONTENT, query)
            for method in ("POST", "PUT", "DELETE"):
                with self.subTest(method=method), self.assertRaises(ValueError):
                    real.fetch(method, a.CONTENT, {"name": NAME, "revision": REVISION, "offset": "0"})
            connection.assert_not_called()

    def test_inventory_projects_only_listed_metadata(self):
        self.client.reads[a.INVENTORY]["payload"]["result"]["files"][0]["private"] = "fixture-hidden"
        answer = self.gateway.message_archives({})
        self.assertEqual(answer["state"], "ok")
        self.assertEqual(answer["data"]["files"], [FILE])
        self.assertNotIn("fixture-hidden", json.dumps(answer))

    def test_read_keeps_two_thousand_character_lines_and_redacts_full_context(self):
        raw = self.client.reads[a.CONTENT]["payload"]["result"]
        ordinary = "normal log text " * 100
        raw["records"] = [{"line": ordinary}, {"line": "x " * 400 + "password=fixture-late-secret"},
                          {"line": "Authorization: Bearer fixture-token"}, {"line": "Cookie: fixture-session"},
                          {"line": "fixture_password_98"}]
        lines = [r["line"] for r in self.read()["data"]["records"]]
        self.assertEqual(lines[0], ordinary)
        self.assertTrue(all("fixture" not in value for value in lines[1:]))
        self.assertIn("withheld", lines[1])

    def test_mismatched_identity_and_non_advancing_cursor_fail_closed(self):
        for field, value in (("name", "messages.old_other"), ("revision", "b" * 64), ("nextOffset", 0),
                             ("nextOffset", 1001), ("nextOffset", True), ("offset", False)):
            with self.subTest(field=field):
                self.client.reads[a.CONTENT] = success({"result": {**copy.deepcopy(PAGE), field: value}})
                answer = self.read()
                self.assertEqual(answer["state"], "invalid_response")
                self.assertIsNone(answer["data"])

    def test_error_metadata_is_fixed_and_does_not_relay_server_paths(self):
        for state in a.MESSAGES:
            self.client.reads[a.CONTENT] = success({"result": {"state": state, "message": "/private/fixture-secret"}})
            answer = self.read()
            self.assertEqual(answer["data"]["message"], a.MESSAGES[state])
            self.assertNotIn("fixture-secret", json.dumps(answer))
        self.client.reads[a.CONTENT] = b.failure("forbidden", 403)
        self.assertEqual(self.read()["state"], "forbidden")

    def test_malformed_records_and_inventories_are_rejected(self):
        malformed = [{**PAGE, "records": [{"line": "x" * 2001}]}, {**PAGE, "records": [{}]},
                     {**PAGE, "omitted": {}}, {**PAGE, "skippedBytes": -1},
                     {**PAGE, "state": []}, {**PAGE, "state": {}}]
        for payload in malformed:
            self.client.reads[a.CONTENT] = success({"result": payload})
            self.assertEqual(self.read()["state"], "invalid_response")
        self.client.reads[a.INVENTORY] = success({"result": {**INVENTORY, "files": [FILE, FILE]}})
        self.assertEqual(self.gateway.message_archives({})["state"], "invalid_response")


class ArchiveHTTPTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.client.reads[a.INVENTORY] = success({"result": INVENTORY})
        self.server = b.LocalServer(b.Gateway(self.client), port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)

    def request(self, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request("GET", path, headers=headers or {})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_read_route_and_no_cross_origin_access(self):
        code, payload = self.request("/api/message-archives")
        self.assertEqual(code, 200)
        self.assertEqual(payload["data"]["files"], [FILE])
        self.assertEqual(self.request("/api/message-archives", {"Origin": "https://other.example"})[0], 403)

    def test_duplicate_unknown_and_malformed_queries_never_reach_iris(self):
        for suffix in ("?offset=0&offset=0", "?offset=-1", "?offset=01", "?offset=9007199254740992", "?name=../secret", "?offset=", "?offset=0&path=/etc/passwd"):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.request("/api/message-archives" + suffix)[0], 400)
        self.assertEqual(self.client.requests, [])


if __name__ == "__main__":
    unittest.main()
