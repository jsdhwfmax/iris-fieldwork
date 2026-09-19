"""Isolated gateway tests. These never connect to a real IRIS instance."""
import copy
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import backend as b


ENV = {"IRIS_USERNAME": "fixture_operator", "IRIS_PASSWORD": "fixture_password_98"}
INFO = {"apiVersion": 2, "serverVersion": "fixture-version", "product": "IRIS",
        "username": "fixture_operator", "systemMode": "TEST",
        "privileges": {"Task": {"use": True}, "Operate": {"use": True}, "Secure": {"use": True}, "fixture_unlisted_privilege_6e0f9b": {"use": True}}}
SENSITIVE_PASSWORD = "fixture_password_value_f94ce2"
SENSITIVE_PERSON = "fixture_person_value_712adb"
ASYNC_ID = "12345678901234567890123456789012345678"


def success(payload):
    return {"state": "ok", "http_status": 200, "payload": payload, "error": None}


class FakeClient(b.IRISClient):
    def __init__(self):
        super().__init__(ENV)
        self.info_data = copy.deepcopy(INFO)
        self.tasks = [{"Id": 1000, "Name": "Test task", "Type": "User", "Namespace": "USER", "Suspended": False},
                      {"Id": 1, "Name": "System task", "Type": "System", "Namespace": "%SYS", "Suspended": False}]
        self.state_override = None
        self.reads = {}
        self.posts = []
        self.post_responses = {}
        self.requests = []
        self.post_failure = None
        self.web = [{"Name": "/fieldwork/demo", "Namespace": "USER", "Type": "CSP", "DispatchClass": "Fieldwork.Demo", "IsSystemApp": False, "Enabled": False},
                    {"Name": "/api/admin", "Namespace": "%SYS", "IsSystemApp": True, "Enabled": True}]
        self.web_detail = {"Type": 2, "NameSpace": "USER", "Enabled": False, "DispatchClass": "Fieldwork.Demo"}
        self.puts = []
        self.alter_other_field = False

    def fetch(self, method, path, query=None, body=None):
        self.requests.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
        if method == "PUT":
            self.puts.append((path, copy.deepcopy(query), copy.deepcopy(body)))
            if self.post_failure:
                return b.failure(self.post_failure)
            self.web_detail["Enabled"] = body["Enabled"]
            self.web[0]["Enabled"] = body["Enabled"]
            if self.alter_other_field:
                self.web_detail["DispatchClass"] = "ChangedElsewhere"
            return success({"result": copy.deepcopy(self.web_detail)})
        if method == "POST":
            self.posts.append((path, copy.deepcopy(query), copy.deepcopy(body)))
            if path in self.post_responses:
                return copy.deepcopy(self.post_responses[path])
            if self.post_failure:
                return b.failure(self.post_failure)
            if path.endswith("/suspend"):
                self.tasks[0]["Suspended"] = True
            elif path.endswith("/resume"):
                self.tasks[0]["Suspended"] = False
            return success({"status": {"errors": []}, "result": {}})
        if path == "/info":
            return success(copy.deepcopy(self.info_data))
        if path == "/v2/tasks":
            return success({"result": copy.deepcopy(self.tasks)})
        if path == "/fieldwork/runtime/task-states":
            return copy.deepcopy(self.state_override) if self.state_override else success({"result": copy.deepcopy(self.tasks)})
        if path == "/v2/web-apps":
            return success({"result": copy.deepcopy(self.web)})
        if path == "/v2/web-app":
            return success({"result": copy.deepcopy(self.web_detail)})
        return copy.deepcopy(self.reads.get(path, success({"result": []})))


class Response:
    def __init__(self, payload, status=200, mime="application/json", headers=None):
        self.body = json.dumps(payload).encode()
        self.status, self.mime = status, mime
        self.headers = headers or {}

    def getheader(self, name):
        return self.mime if name == "Content-Type" else self.headers.get(name)

    def read(self, count):
        return self.body[:count]


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = b.IRISClient(ENV)

    def request_fixture(self, payload, path="/info", status=200):
        with patch.object(b.http.client, "HTTPConnection") as connection:
            connection.return_value.getresponse.return_value = Response(payload, status)
            result = self.client.fetch("GET", path)
            self.assertEqual(connection.call_args.args[:2], ("127.0.0.1", 52773))
            self.assertEqual(connection.return_value.request.call_args.args[:2], ("GET", b.upstream_path(path)))
            return result

    def test_bare_and_live_enveloped_info(self):
        for data in (INFO, {"status": {"errors": []}, "console": [], "result": INFO}):
            with self.subTest(data=data):
                result = self.request_fixture(data)
                self.assertEqual(result["state"], "ok")
                self.assertEqual(result["payload"]["serverVersion"], "fixture-version")

    def test_upper_and_lower_application_errors_do_not_leak(self):
        for key in ("Errors", "errors"):
            result = self.request_fixture({"status": {key: ["fixture_password_98"]}, "result": INFO})
            self.assertEqual(result["state"], "application_error")
            self.assertNotIn("fixture_password_98", json.dumps(result))

    def test_distinct_http_failures_and_redirect_refusal(self):
        for status, state in ((401, "unauthorized"), (403, "forbidden"), (404, "not_found"), (302, "redirect_refused"), (500, "http_error")):
            with self.subTest(status=status):
                self.assertEqual(self.request_fixture({}, status=status)["state"], state)

    def test_unavailable_and_bad_response(self):
        with patch.object(b.http.client, "HTTPConnection", side_effect=OSError("fixture_password_98")):
            result = self.client.fetch("GET", "/info")
        self.assertEqual(result["state"], "unavailable")
        self.assertNotIn("fixture_password_98", json.dumps(result))
        self.assertEqual(self.request_fixture({"result": {}})["state"], "invalid_response")

    def test_allowlist_rejects_arbitrary_reads_or_mutations(self):
        bad = [("GET", "/v2/wallet/credential", {}, None),
               ("GET", "/info", {"url": "http://example.com"}, None),
               ("GET", "/v2/tasks", {"maxRows": True}, None),
               ("GET", "/v2/tasks", {"maxRows": 101}, None),
               ("DELETE", "/v2/tasks", {}, None),
               ("POST", "/v2/task/run", {"id": True}, {"RunNow": True}),
               ("POST", "/v2/task/run", {"id": 1000}, {"RunNow": False}),
               ("POST", "/v2/task/suspend", {"id": 1000}, {"LeaveInQueue": False})]
        bad += [("PUT", "/v2/web-app", {"name": "/api/admin"}, {"Enabled": False}),
                ("PUT", "/v2/web-app", {"name": "/fieldwork/demo"}, {"Enabled": False, "Resource": ""}),
                ("PUT", "/v2/web-app", {"name": "/fieldwork/demo"}, {"Enabled": 1}),
                ("GET", "/v2/web-app", {"name": "/fieldwork/runtime"}, None)]
        with patch.object(b.http.client, "HTTPConnection") as connection:
            for args in bad:
                with self.subTest(args=args), self.assertRaises(ValueError):
                    self.client.fetch(*args)
            connection.assert_not_called()

    def test_loopback_and_credentials(self):
        for url in ("http://example.com", "http://127.0.0.1.evil.test", "http://10.0.0.1", "http://user:pass@localhost", "http://localhost/path", "http://localhost?next=x", "file:///x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                b.loopback_target(url)
        self.assertEqual(b.loopback_target("http://localhost:52773/api/admin"), ("http", "127.0.0.1", 52773))
        self.assertEqual(b.loopback_target("http://[::1]:52773"), ("http", "::1", 52773))
        self.assertEqual(b.IRISClient({}).fetch("GET", "/info")["state"], "configuration_error")
        self.assertEqual(b.IRISClient({**ENV, "IRIS_BEARER_TOKEN": "token"}).fetch("GET", "/info")["state"], "configuration_error")

    def test_adapter_uses_own_root(self):
        self.assertEqual(self.request_fixture({"status": {"errors": []}, "result": {}}, "/fieldwork/runtime/metrics")["state"], "ok")

    def test_mutations_require_recognized_success_envelope(self):
        for payload in ({}, {"error": "fixture rejection"}, {"status": {"summary": "ERROR"}}, {"status": {"errors": ""}}, {"status": {"errors": {}}}):
            with self.subTest(payload=payload), patch.object(b.http.client, "HTTPConnection") as connection:
                connection.return_value.getresponse.return_value = Response(payload)
                result = self.client.fetch("POST", "/v2/task/run", {"id": 1000}, {"RunNow": True})
                self.assertEqual(result["state"], "invalid_response")
        for key in ("errors", "Errors"):
            with patch.object(b.http.client, "HTTPConnection") as connection:
                connection.return_value.getresponse.return_value = Response({"status": {key: []}, "result": {}})
                self.assertEqual(self.client.fetch("POST", "/v2/task/run", {"id": 1000}, {"RunNow": True})["state"], "ok")

    def async_response(self, location):
        headers = {} if location is None else {"Location": location}
        with patch.object(b.http.client, "HTTPConnection") as connection:
            connection.return_value.getresponse.return_value = Response({"status": {"errors": []}, "console": []}, 202, headers=headers)
            result = self.client.fetch("POST", "/v2/security/audit/records", {"maxRows": 10, "ascending": 0})
            connection.return_value.request.assert_called_once()
            return result

    def test_async_location_accepts_only_fixed_relative_result_paths(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                result = self.async_response("/api/admin/" + version + "/async-result?id=" + ASYNC_ID)
                self.assertEqual(result["state"], "ok")
                self.assertEqual(result["async_id"], ASYNC_ID)
                self.assertNotIn("Location", result)
                self.assertNotIn("GUID", result["payload"])

    def test_async_location_rejects_origin_path_duplicate_or_ambiguous_id(self):
        base = "/api/admin/v2/async-result"
        locations = [None, "", "https://foreign.example.test" + base + "?id=" + ASYNC_ID,
                     "http://127.0.0.1:52773" + base + "?id=" + ASYNC_ID,
                     "//foreign.example.test" + base + "?id=" + ASYNC_ID,
                     "/api/admin/v2/wallet/secret?id=" + ASYNC_ID,
                     base + "?id=" + ASYNC_ID + "&id=" + ASYNC_ID,
                     base + "?id=" + ASYNC_ID + "&id=",
                     base + "?id=" + ASYNC_ID + "&unexpected=",
                     base + "?id=" + ASYNC_ID + "#fragment",
                     base + "?id=", base + "?id=not-a-numeric-identifier",
                     base + "?id=" + "1" * 65]
        for location in locations:
            with self.subTest(location=location):
                result = self.async_response(location)
                self.assertEqual(result["state"], "invalid_response")
                self.assertNotIn("async_id", result)

    def test_curated_transport_routes_dispatch_exact_queries(self):
        examples = [
            ("GET", "/v2/security/ssl-configuration", {"name": "TLS Fixture"}, None, "/api/admin/v2/security/ssl-configuration?name=TLS+Fixture"),
            ("GET", "/v2/wallet/secrets", {"collection": "FixtureWallet", "maxRows": 5}, None, "/api/admin/v2/wallet/secrets?collection=FixtureWallet&maxRows=5"),
            ("GET", "/v2/async-result", {"id": ASYNC_ID}, None, "/api/admin/v2/async-result?id=" + ASYNC_ID),
            ("PUT", "/v2/security/role", {"name": "FixtureRole"}, {"Resources": [{"Name": "FixtureResource", "Permissions": "U"}]}, "/api/admin/v2/security/role?name=FixtureRole"),
        ]
        for method, path, query, body, expected_path in examples:
            with self.subTest(path=path), patch.object(b.http.client, "HTTPConnection") as connection:
                connection.return_value.getresponse.return_value = Response({"status": {"errors": []}, "result": {}})
                result = self.client.fetch(method, path, query, body)
                self.assertEqual(result["state"], "ok")
                args = connection.return_value.request.call_args
                self.assertEqual(args.args, (method, expected_path))
                self.assertEqual(json.loads(args.kwargs["body"]) if args.kwargs["body"] is not None else None, body)

    def test_curated_transport_rejects_extra_filters_bodies_and_secret_reads(self):
        examples = [
            ("GET", "/v2/security/x509-credential", {"name": "Fixture"}, None),
            ("GET", "/v2/security/ssl-configuration", {"name": "Fixture", "url": "https://foreign.example.test"}, None),
            ("GET", "/v2/wallet/secret", {"name": "FixtureWallet.Token"}, None),
            ("GET", "/v2/wallet/secrets", {"collection": "FixtureWallet", "maxRows": 101}, None),
            ("GET", "/v2/async-result", {"id": ASYNC_ID, "maxRows": 10}, None),
            ("GET", "/v2/async-result", {"id": "../foreign"}, None),
            ("DELETE", "/v2/async-result", {"id": ASYNC_ID}, None),
            ("PUT", "/v2/security/role", {"name": "FixtureRole"}, {"Resources": [], "SuperRoles": ["%All"]}),
            ("POST", "/v2/security/audit/records", {"maxRows": 10, "ascending": 0}, {}),
            ("POST", "/v2/security/audit/records", {"maxRows": 10, "ascending": 0, "purge": True}, None),
            ("POST", "/v2/journal/file/records", {"file": "../journal", "maxRows": 10, "reverse": 1}, None),
            ("POST", "/v2/journal/file/records", {"file": "/journal/example", "maxRows": True, "reverse": 1}, None),
        ]
        with patch.object(b.http.client, "HTTPConnection") as connection:
            for args in examples:
                with self.subTest(args=args), self.assertRaises(ValueError):
                    self.client.fetch(*args)
            connection.assert_not_called()


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.gateway = b.Gateway(self.client)

    def act(self, action="task.suspend", target=1000):
        return self.gateway.action({"action": action, "target": {"id": target}, "reviewed": True})

    def test_status_omits_credentials_and_unlisted_privileges(self):
        status = self.gateway.status()
        text = json.dumps(status)
        self.assertTrue(status["connected"])
        self.assertNotIn("username", text)
        self.assertNotIn("fixture_operator", text)
        self.assertNotIn("fixture_unlisted_privilege_6e0f9b", text)
        actions = {a["id"]: a for a in status["capabilities"]["actions"]}
        self.assertFalse(actions["task.run"]["reversible"])
        self.assertTrue(actions["web.set_enabled"]["enabled"])

    def test_sections_show_errors_and_only_allowlisted_metadata(self):
        self.client.reads["/v2/security/users"] = success({"result": [{"Name": "fixture_operator", "Password": SENSITIVE_PASSWORD, "FullName": SENSITIVE_PERSON, "Enabled": True}]})
        self.client.reads["/v2/security/roles"] = b.failure("forbidden", 403)
        result = self.gateway.section("permissions")
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["resources"][0]["state"], "forbidden")
        self.assertEqual(result["resources"][1]["data"], [{"Name": "[redacted]", "Enabled": True}])
        self.assertNotIn("Password", json.dumps(result))
        self.assertNotIn(SENSITIVE_PASSWORD, json.dumps(result))
        self.assertNotIn(SENSITIVE_PERSON, json.dumps(result))

    def test_runtime_logs_bounded_and_redacted(self):
        lines = ["ordinary startup", "password=hidden-value", 'password="some hidden-value"', "Authorization: Bearer hidden-value", "Authorization: [redacted] hidden-value", "-----BEGIN PRIVATE KEY-----", "http://user:hidden-value@example.test", "fixture_password_98"]
        self.client.reads["/fieldwork/runtime/logs"] = success({"result": [{"source": "messages", "scope": "IRIS", "state": "ok", "truncated": True, "private": "hidden-value", "records": [{"line": line} for line in lines] + [{"line": "more"}] * 200}]})
        logs = self.gateway.section("logs")["resources"][0]
        rendered = json.dumps(logs)
        self.assertEqual(logs["state"], "ok")
        self.assertEqual(len(logs["data"][0]["records"]), 100)
        for secret in ("hidden-value", "fixture_password_98", "BEGIN PRIVATE KEY"):
            self.assertNotIn(secret, rendered)
        self.assertIn("ordinary startup", rendered)

    def test_task_history_retains_status_and_scrubs_result(self):
        self.client.reads["/v2/task/history"] = success({"result": [
            {"TaskId": 1000, "Status": "1", "Result": "Success", "Completed": True},
            {"TaskId": 1000, "Status": "0", "Result": 'password="hidden result secret"', "Completed": True},
            {"TaskId": 1000, "Status": "1", "Result": "Resumed task", "Completed": True}]})
        history = self.gateway.read_resource(b.HISTORY)
        self.assertEqual(history["data"][0]["Status"], "1")
        self.assertEqual(history["data"][0]["Result"], "Success")
        self.assertEqual(history["data"][1]["Result"], "[sensitive record withheld]")
        self.assertEqual(history["data"][2]["Result"], "Resumed task")
        self.assertNotIn("Outcome", history["data"][1])
        self.assertNotIn("Outcome", history["data"][2])
        self.assertNotIn("hidden result secret", json.dumps(history))

    def test_missing_adapter_is_explicit(self):
        self.client.reads["/fieldwork/runtime/metrics"] = b.failure("not_found", 404)
        result = self.gateway.section("system")
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["resources"][0]["state"], "not_found")
        self.assertEqual(result["resources"][0]["http_status"], 404)

    def test_partial_metrics_retain_available_values_and_limitations(self):
        self.client.reads["/fieldwork/runtime/metrics"] = success({"result": {"cpuBusyPercent": 12.5, "availability": "partial: Linux telemetry could not be fully read"}})
        result = self.gateway.section("system")
        metrics = result["resources"][0]
        self.assertEqual(result["state"], "partial")
        self.assertEqual(metrics["state"], "partial")
        self.assertEqual(metrics["data"]["cpuBusyPercent"], 12.5)
        self.assertIn("partial:", metrics["data"]["availability"])
        self.assertIn("Some runtime metrics could not be read on this host.", result["limitations"])

    def test_targets_only_user_tasks_and_available_commands(self):
        result = self.gateway.section("tasks")
        self.assertEqual(result["targets"], [{"type": "task", "id": 1000, "name": "Test task", "actions": ["task.suspend", "task.run"]}])
        self.client.info_data["privileges"]["Task"]["use"] = False
        self.assertEqual(self.gateway.section("tasks")["targets"][0]["actions"], [])

    def test_review_schema_target_and_state_rejected_without_post(self):
        bad = [{"action": "task.run", "target": {"id": 1000}, "reviewed": False},
               {"action": "task.run", "target": {"id": True}, "reviewed": True},
               {"action": "task.run", "target": {"id": 1000, "url": "x"}, "reviewed": True},
               {"action": "task.run", "target": {"id": 1000}, "reviewed": True, "payload": {}},
               {"action": "web.set_enabled", "target": {"id": 1000}, "reviewed": True}]
        for value in bad:
            self.assertEqual(self.gateway.action(value)[0], 400)
        self.assertEqual(self.act(target=1)[0], 403)
        self.assertEqual(self.act(target=999)[0], 409)
        self.assertEqual(self.act("task.resume")[0], 409)
        self.assertEqual(self.client.posts, [])

    def test_live_capability_checked_before_each_action(self):
        self.client.info_data["privileges"]["Task"]["use"] = False
        self.assertEqual(self.act()[0], 403)
        self.assertEqual(self.client.posts, [])

    def test_task_actions_use_exact_bodies_and_verify_state(self):
        result = self.act()[1]
        self.assertEqual(result["state"], "verified")
        self.assertFalse(result["before"]["Suspended"])
        self.assertEqual(len(result["verification"]["data"]), 1)
        self.assertTrue(result["verification"]["data"][0]["Suspended"])
        self.assertEqual(self.client.posts[-1], ("/v2/task/suspend", {"id": 1000}, {"LeaveInQueue": True}))
        self.assertEqual(self.act("task.resume")[1]["state"], "verified")
        self.assertEqual(self.client.posts[-1], ("/v2/task/resume", {"id": 1000}, None))
        self.assertEqual(self.act("task.run")[1]["state"], "accepted")
        self.assertEqual(self.client.posts[-1], ("/v2/task/run", {"id": 1000}, {"RunNow": True}))

    def test_uncertain_run_never_retries(self):
        self.client.post_failure = "unavailable"
        code, result = self.act("task.run")
        self.assertEqual(code, 502)
        self.assertEqual(result["state"], "outcome_unknown")
        self.assertEqual(len(self.client.posts), 1)
        self.assertIsNone(result["verification"])

    def test_task_state_adapter_overrides_stale_api_with_visible_mismatch(self):
        self.client.state_override = success({"result": [{**self.client.tasks[0], "Suspended": True}]})
        section = self.gateway.section("tasks")
        row = section["resources"][0]["data"][0]
        self.assertTrue(row["Suspended"])
        self.assertTrue(row["StateVerified"])
        self.assertTrue(row["StateMismatch"])
        self.assertFalse(row["ApiReportedSuspended"])
        self.assertEqual(section["targets"][0]["actions"], ["task.resume"])
        self.assertEqual(self.act("task.run")[0], 409)
        self.assertEqual(self.client.posts, [])

    def test_task_adapter_unavailable_or_identity_mismatch_disables_commands(self):
        for response in (b.failure("not_found", 404), success({"result": [{**self.client.tasks[0], "Name": "Another task"}]}), success({"result": [{**self.client.tasks[0], "Namespace": "ANOTHER"}]})):
            self.client.state_override = response
            self.assertEqual(self.gateway.section("tasks")["targets"][0]["actions"], [])
            self.assertEqual(self.act("task.run")[0], 403)
        self.assertEqual(self.client.posts, [])

    def test_explorer_is_curated_no_secret_routes(self):
        catalog = self.gateway.explorer()
        self.assertEqual(catalog["source"], b.SOURCE)
        posts = [item for item in catalog["items"] if item["method"] == "POST"]
        self.assertEqual(len(posts), 3)
        self.assertTrue(all(item["enabled"] is False for item in posts))
        self.assertNotIn("/v2/wallet/credential", json.dumps(catalog))

    def web_act(self, **changes):
        target = {"name": "/fieldwork/demo", "enabled": True, "expected_enabled": False, **changes}
        return self.gateway.action({"action": "web.set_enabled", "target": target, "reviewed": True})

    def test_web_targets_protected_paths_and_schema(self):
        targets = self.gateway.section("web")["targets"]
        self.assertEqual(targets, [{"type": "web_app", "name": "/fieldwork/demo", "enabled": False, "actions": ["web.set_enabled"]}])
        for name in ("/", "/api/admin", "/API/admin", "/api/user-app", "/fieldwork/runtime", "/fieldwork", "/csp/sys", "/csp/sys/app", "/fieldwork/../runtime", "/fieldwork/%64emo"):
            with self.subTest(name=name):
                self.assertEqual(self.web_act(name=name)[0], 400)
        self.assertEqual(self.web_act(enabled=1)[0], 400)
        self.assertEqual(self.web_act(enabled=False)[0], 400)
        self.assertEqual(self.client.puts, [])

    def test_web_toggle_minimal_body_and_field_preservation(self):
        code, result = self.web_act()
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["verification"]["data"], {"Name": "/fieldwork/demo", "Enabled": True, "other_fields_unchanged": True})
        self.assertEqual(self.client.puts, [("/v2/web-app", {"name": "/fieldwork/demo"}, {"Enabled": True})])
        self.assertNotIn("DispatchClass", json.dumps(result))
        self.assertEqual(self.web_act(enabled=False, expected_enabled=True)[1]["state"], "verified")

    def test_web_stale_state_system_type_and_privilege_rejected(self):
        self.client.web_detail["Enabled"] = True
        self.assertEqual(self.web_act()[1]["state"], "target_changed")
        self.client.web_detail["Enabled"] = False
        self.client.web_detail["Type"] = 3
        self.assertEqual(self.web_act()[1]["state"], "target_unverified")
        self.client.web_detail["Type"] = 2
        self.client.web[0]["IsSystemApp"] = True
        self.assertEqual(self.web_act()[0], 403)
        self.client.web[0]["IsSystemApp"] = False
        self.client.info_data["privileges"]["Secure"]["use"] = False
        self.assertEqual(self.web_act()[0], 403)
        self.assertEqual(self.client.puts, [])

    def test_observed_web_detail_without_type_name_or_system_flag(self):
        self.client.web[0]["DispatchClass"] = "Fieldwork.Runtime"
        self.client.web_detail = {"NameSpace": "USER", "DispatchClass": "Fieldwork.Runtime", "Enabled": False}
        code, result = self.web_act()
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(self.client.puts, [("/v2/web-app", {"name": "/fieldwork/demo"}, {"Enabled": True})])

    def test_web_detail_identity_mismatch_prevents_put(self):
        for field, mismatch in (("NameSpace", "OTHER"), ("DispatchClass", "Other.Application")):
            with self.subTest(field=field):
                original = self.client.web_detail[field]
                self.client.web_detail[field] = mismatch
                self.assertEqual(self.web_act()[1]["state"], "target_unverified")
                self.client.web_detail[field] = original
        self.client.web[0]["Type"] = "Unknown"
        self.assertEqual(self.gateway.section("web")["targets"], [])
        self.assertEqual(self.web_act()[1]["state"], "target_not_permitted")
        self.assertEqual(self.client.puts, [])

    def test_web_other_field_change_does_not_claim_verified_or_rollback(self):
        self.client.alter_other_field = True
        self.assertEqual(self.web_act()[1]["state"], "accepted_unverified")
        self.assertEqual(len(self.client.puts), 1)
        self.client.web[0]["DispatchClass"] = self.client.web_detail["DispatchClass"]
        self.client.post_failure = "unavailable"
        result = self.web_act(enabled=False, expected_enabled=True)[1]
        self.assertEqual(result["state"], "outcome_unknown")
        self.assertEqual(len(self.client.puts), 2)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fieldwork-gateway-test-")
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        (self.root / "index.html").write_text("<title>Fixture</title>", encoding="utf-8")
        (self.root / "app.js").write_text("'use strict';", encoding="utf-8")
        (self.root / ".secret.js").write_text(SENSITIVE_PASSWORD, encoding="utf-8")
        self.client = FakeClient()
        self.gateway = b.Gateway(self.client)
        self.server = b.LocalServer(self.gateway, port=0, static_root=self.root)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)
        self.temporary.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def action_headers(self):
        return {"Origin": self.origin, "X-CSRF-Token": self.gateway.csrf_token, "Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"}

    def test_loopback_binding_static_and_no_arbitrary_files(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path in ("/", "/static/app.js"):
            self.assertEqual(self.request("GET", path)[0], 200)
        for path in ("/static/.secret.js", "/static/../backend.py", "/static/%2e%2e/backend.py", "/api/arbitrary", "/spec/mainspec_v2.json"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("GET", "/api/status?url=x")[0], 400)

    def test_foreign_origin_host_and_csrf_are_denied(self):
        payload = json.dumps({"action": "task.run", "target": {"id": 1000}, "reviewed": True})
        cases = [{}, {**self.action_headers(), "Origin": "https://evil.test"},
                 {**self.action_headers(), "Host": "evil.test"},
                 {**self.action_headers(), "Sec-Fetch-Site": "cross-site"},
                 {**self.action_headers(), "X-CSRF-Token": "wrong"},
                 {**self.action_headers(), "X-CSRF-Token": "\u00e9"}]
        for headers in cases:
            self.assertEqual(self.request("POST", "/api/action", payload, headers)[0], 403)
        self.assertEqual(self.request("GET", "/api/status", headers={"Origin": "https://evil.test"})[0], 403)
        self.assertEqual(self.client.posts, [])

    def test_strict_json_and_content_type(self):
        duplicate = '{"action":"task.run","action":"task.run","target":{"id":1000},"reviewed":true}'
        self.assertEqual(self.request("POST", "/api/action", duplicate, self.action_headers())[0], 400)
        nonfinite = '{"action":"task.run","target":{"id":NaN},"reviewed":true}'
        self.assertEqual(self.request("POST", "/api/action", nonfinite, self.action_headers())[0], 400)
        headers = {**self.action_headers(), "Content-Type": "text/plain"}
        self.assertEqual(self.request("POST", "/api/action", "{}", headers)[0], 415)
        self.assertEqual(self.client.posts, [])

    def test_status_token_and_reviewed_http_action(self):
        code, headers, data = self.request("GET", "/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["csrf_token"], self.gateway.csrf_token)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        payload = json.dumps({"action": "task.suspend", "target": {"id": 1000}, "reviewed": True})
        code, _, data = self.request("POST", "/api/action", payload, self.action_headers())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["state"], "verified")
        self.assertEqual(len(self.client.posts), 1)

    def test_inspect_decodes_exact_parameters_and_uses_curated_detail(self):
        self.client.reads["/v2/security/ssl-configuration"] = success({"result": {"Enabled": True, "TLSMinVersion": 8, "PrivateKeyPassword": SENSITIVE_PASSWORD}})
        code, _, raw = self.request("GET", "/api/inspect?kind=tls&name=TLS%20Fixture")
        result = json.loads(raw)
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["data"]["TLSMinVersion"], 8)
        self.assertIn(("GET", "/v2/security/ssl-configuration", {"name": "TLS Fixture"}, None), self.client.requests)
        self.assertNotIn(SENSITIVE_PASSWORD, raw.decode())

    def test_inspect_rejects_duplicate_unknown_or_missing_parameters_before_upstream(self):
        queries = ["kind=tls", "name=Fixture", "kind=tls&name=Fixture&context=x", "kind=tls&kind=x509&name=Fixture",
                   "kind=tls&name=Fixture&name=Other", "kind=tls&name=Fixture&name=", "kind=tls&name=Fixture&%6eame=Other",
                   "kind=tls&name=Fixture&unknown=", "kind=tls&name=Fixture&flag", "kind=unknown&name=Fixture"]
        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(self.request("GET", "/api/inspect?" + query)[0], 400)
        self.assertEqual(self.client.requests, [])
        self.assertEqual(self.request("GET", "/api/inspect?kind=tls&name=Fixture", headers={"Origin": "https://foreign.example.test"})[0], 403)
        self.assertEqual(self.client.requests, [])

    def test_log_query_requires_csrf_same_origin_and_exact_route(self):
        payload = json.dumps({"kind": "audit", "filters": {"begin": "", "end": "", "username": "", "event": "", "limit": 10}})
        for headers in ({}, {**self.action_headers(), "X-CSRF-Token": "wrong"}, {**self.action_headers(), "Origin": "https://foreign.example.test"}):
            self.assertEqual(self.request("POST", "/api/log-query", payload, headers)[0], 403)
        for path in ("/api/log-query/", "/api/log-query?kind=audit", "/api/arbitrary-query"):
            self.assertEqual(self.request("POST", path, None, self.action_headers())[0], 404)
        self.assertEqual(self.request("GET", "/api/log-query")[0], 404)
        self.assertEqual(self.client.requests, [])

    def test_log_query_rejects_duplicate_json_and_unknown_schema(self):
        duplicate = '{"kind":"audit","kind":"journal","filters":{}}'
        self.assertEqual(self.request("POST", "/api/log-query", duplicate, self.action_headers())[0], 400)
        extra = {"kind": "audit", "filters": {"begin": "", "end": "", "username": "", "event": "", "limit": 10}, "reviewed": True}
        self.assertEqual(self.request("POST", "/api/log-query", json.dumps(extra), self.action_headers())[0], 400)
        self.assertEqual(self.client.requests, [])

    def test_log_query_completes_without_guid_and_poll_does_not_resubmit(self):
        route = "/v2/security/audit/records"
        self.client.post_responses[route] = {"state": "ok", "http_status": 202, "payload": {"status": {"errors": []}}, "error": None, "async_id": ASYNC_ID}
        self.client.reads["/v2/async-result"] = success({"result": {"TaskName": "POST " + route, "State": "Finished", "Result": [
            {"AuditIndex": 1, "Event": "Login", "SessionID": SENSITIVE_PASSWORD, "EventData": SENSITIVE_PERSON}]}})
        body = {"kind": "audit", "filters": {"begin": "", "end": "", "username": "", "event": "", "limit": 10}}
        code, _, raw = self.request("POST", "/api/log-query", json.dumps(body), self.action_headers())
        result = json.loads(raw)
        self.assertEqual(code, 200)
        self.assertEqual(result["query_state"], "complete")
        self.assertEqual(result["data"], [{"AuditIndex": 1, "Event": "Login"}])
        self.assertNotIn(ASYNC_ID, raw.decode())
        self.assertNotIn(SENSITIVE_PASSWORD, raw.decode())
        self.assertNotIn(SENSITIVE_PERSON, raw.decode())
        self.assertEqual(self.client.posts, [(route, {"maxRows": 10, "ascending": 0}, None)])
        self.assertIn(("GET", "/v2/async-result", {"id": ASYNC_ID}, None), self.client.requests)
        poll = {"kind": "result", "filters": {"id": result["query_id"]}}
        self.assertEqual(self.request("POST", "/api/log-query", json.dumps(poll), self.action_headers())[0], 200)
        self.assertEqual(len(self.client.posts), 1)
        unknown = {"kind": "result", "filters": {"id": ASYNC_ID}}
        self.assertEqual(self.request("POST", "/api/log-query", json.dumps(unknown), self.action_headers())[0], 404)
        self.assertEqual(len(self.client.posts), 1)


class ProbeRegressionTests(unittest.TestCase):
    def test_info_envelopes_and_lowercase_errors(self):
        path = Path(__file__).resolve().parents[1] / "runtime" / "probe.py"
        spec = importlib.util.spec_from_file_location("fieldwork_probe", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for value in (INFO, {"status": {"errors": []}, "result": INFO, "console": []}):
            result = module.summarize_payload(value, "/info")
            self.assertEqual(result["state"], "ok")
            self.assertNotIn("fixture_operator", json.dumps(result))
        result = module.summarize_payload({"status": {"errors": ["fixture_password_98"]}, "result": INFO}, "/info")
        self.assertEqual(result["state"], "application_error")
        self.assertNotIn("fixture_password_98", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
