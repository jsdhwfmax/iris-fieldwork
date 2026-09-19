"""Isolated log-query contract tests. No IRIS, real journal files or credentials."""
import copy
import json
import unittest
from unittest.mock import patch

import log_ops as l


INFO = {"state": "ok", "data": {"privileges": {"Operate": {"use": True}, "Secure": {"use": True}}}}
JOURNAL_FILE = "/usr/irissys/mgr/journal/20260919.001"


def ok(result, status=200):
    return {"state": "ok", "http_status": status, "payload": {"status": {"errors": []}, "result": copy.deepcopy(result)}, "error": None}


def failed(state="unavailable", status=None):
    return {"state": state, "http_status": status, "payload": None,
            "error": {"message": "fixture_secret_diagnostic"}}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.inventory = [{"Name": JOURNAL_FILE}]
        self.inventory_failure = None
        self.post_override = None
        self.poll_override = None
        self.rows = []
        self.states = ["Finished"]
        self.task_name = None
        self.guid = None
        self.jobs = {}

    def clean(self, value):
        if isinstance(value, str):
            return value.replace("fixture_secret", "[redacted]")[:512]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return None

    def clean_log(self, value):
        return self.clean(value)

    def fetch(self, method, path, query=None, body=None):
        self.calls.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
        if path == "/v2/journal/files":
            return copy.deepcopy(self.inventory_failure) if self.inventory_failure else ok(self.inventory)
        if method == "POST":
            if self.post_override is not None:
                return copy.deepcopy(self.post_override)
            identifier = str(900001 + len(self.jobs))
            self.jobs[identifier] = path
            return {"state": "ok", "http_status": 202, "async_id": identifier, "payload": None, "error": None}
        if path == "/v2/async-result":
            if self.poll_override is not None:
                return copy.deepcopy(self.poll_override)
            identifier = query["id"]
            state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return ok({"GUID": self.guid if self.guid is not None else identifier,
                       "TaskName": self.task_name if self.task_name is not None else "POST " + self.jobs[identifier],
                       "State": state, "Result": self.rows,
                       "Console": ["fixture_secret_console"], "FailureReason": "fixture_secret_failure"})
        raise AssertionError("Unexpected request in isolated log fixture")

    @property
    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]

    @property
    def polls(self):
        return [call for call in self.calls if call[1] == "/v2/async-result"]


class LogOpsTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.info = copy.deepcopy(INFO)
        self.ops = l.LogOps(self.client, lambda: self.info)
        self.clock = 1000.0
        timer = patch.object(l.time, "monotonic", lambda: self.clock)
        timer.start()
        self.addCleanup(timer.stop)

    def audit(self, **changes):
        filters = {"begin": "", "end": "", "username": "", "event": "", "limit": 25, **changes}
        return self.ops.query({"kind": "audit", "filters": filters})

    def journal(self, **changes):
        return self.ops.query({"kind": "journal", "filters": {"file": JOURNAL_FILE, "limit": 25, **changes}})

    def poll(self, identifier):
        return self.ops.query({"kind": "result", "filters": {"id": identifier}})

    def test_exact_audit_query_uses_filters_without_request_body(self):
        code, result = self.audit(begin="2026-09-01 00:00:00", end="2026-09-19 23:59:59", username="_SYSTEM", event="LoginFailure", limit=10)
        self.assertEqual(code, 200)
        self.assertEqual(result["query_state"], "complete")
        self.assertEqual(self.client.posts, [("POST", l.PATHS["audit"], {"maxRows": 10, "ascending": 0,
                                            "beginDateTime": "2026-09-01 00:00:00", "endDateTime": "2026-09-19 23:59:59",
                                            "usernames": "_SYSTEM", "events": "LoginFailure"}, None)])

    def test_strict_outer_input_and_unknown_kinds_are_rejected_without_requests(self):
        bad = [None, [], {}, {"kind": "audit", "filters": {}, "extra": 1},
               {"kind": "audit", "filters": []}, {"kind": "unknown", "filters": {}},
               {"kind": [], "filters": {}}, {"kind": {}, "filters": {}}]
        for body in bad:
            with self.subTest(body=body):
                self.assertEqual(self.ops.query(body)[0], 400)
        self.assertEqual(self.client.calls, [])

    def test_audit_filters_dates_names_limits_and_extras_are_strict(self):
        bad = [{"begin": "2026-02-30 00:00:00"}, {"begin": "2026-09-01T00:00:00"},
               {"begin": "2026-09-20 00:00:00", "end": "2026-09-19 00:00:00"},
               {"username": "one,two"}, {"username": "name*"}, {"event": "event\n"},
               {"limit": True}, {"limit": 0}, {"limit": 101}, {"limit": "25"}, {"extra": 1}]
        for changes in bad:
            with self.subTest(changes=changes):
                self.assertEqual(self.audit(**changes)[0], 400)
        self.assertEqual(self.client.posts, [])

    def test_journal_search_matches_current_exact_file_before_dispatch(self):
        code, result = self.journal(limit=7)
        self.assertEqual(code, 200)
        self.assertEqual(result["sample_limit"], 7)
        self.assertEqual(self.client.calls[0], ("GET", "/v2/journal/files", {"maxRows": 100}, None))
        self.assertEqual(self.client.posts, [("POST", l.PATHS["journal"], {"file": JOURNAL_FILE, "reverse": 1, "maxRows": 7}, None)])

    def test_unlisted_duplicate_or_unavailable_journal_inventory_never_dispatches(self):
        for inventory in ([], [{"Name": JOURNAL_FILE}, {"Name": JOURNAL_FILE}], [{"Name": JOURNAL_FILE + ".old"}], {}):
            with self.subTest(inventory=inventory):
                self.client.inventory = inventory
                self.assertEqual(self.journal()[0], 409)
        self.client.inventory_failure = failed("forbidden", 403)
        self.assertEqual(self.journal()[0], 409)
        self.assertEqual(self.client.posts, [])

    def test_journal_target_outside_bounded_inventory_is_rejected(self):
        self.client.inventory = [{"Name": f"/journal/old-{index}"} for index in range(100)] + [{"Name": JOURNAL_FILE}]
        self.assertEqual(self.journal()[0], 409)
        self.assertEqual(self.client.posts, [])

    def test_journal_paths_and_filter_extras_are_strict(self):
        for changes in ({"file": "../journal"}, {"file": "x\\..\\journal"}, {"file": "file\n"},
                        {"file": ""}, {"file": "x" * 513}, {"limit": False}, {"reverse": 0}):
            with self.subTest(changes=changes):
                self.assertEqual(self.journal(**changes)[0], 400)
        self.assertEqual(self.client.posts, [])

    def test_live_start_privileges_are_required_before_any_search_post(self):
        for privilege in ("Operate", "Secure"):
            self.info = copy.deepcopy(INFO)
            self.info["data"]["privileges"][privilege]["use"] = False
            self.assertEqual(self.audit()[0], 403)
        self.info = copy.deepcopy(INFO)
        self.info["data"]["privileges"]["Operate"]["use"] = False
        self.assertEqual(self.journal()[0], 403)
        self.info = {"state": "unavailable", "data": None}
        self.assertEqual(self.audit()[0], 403)
        self.assertEqual(self.client.posts, [])

    def test_journal_search_does_not_require_audit_secure_privilege(self):
        self.info["data"]["privileges"]["Secure"]["use"] = False
        self.assertEqual(self.journal()[0], 200)
        self.assertEqual(len(self.client.posts), 1)

    def test_start_requires_202_and_valid_upstream_id_without_retry(self):
        for response in (failed(), {"state": "ok", "http_status": 200, "async_id": "123"},
                         {"state": "ok", "http_status": 202, "async_id": "not-numeric"},
                         {"state": "ok", "http_status": 202, "async_id": 123},
                         {"state": "ok", "http_status": 202}):
            with self.subTest(response=response):
                self.client.post_override = response
                before = len(self.client.posts)
                code, result = self.audit()
                self.assertEqual(code, 502)
                self.assertEqual(result["state"], "search_not_verified")
                self.assertEqual(len(self.client.posts), before + 1)
                self.assertEqual(self.ops.queries, {})
        self.assertEqual(self.client.polls, [])

    def test_pending_poll_finishes_without_starting_a_second_search(self):
        self.client.states = ["Running", "Finished"]
        code, pending = self.audit()
        self.assertEqual(code, 200)
        self.assertEqual(pending["query_state"], "pending")
        self.assertEqual(pending["query_status"], "Running")
        token = pending["query_id"]
        self.assertNotEqual(token, next(iter(self.client.jobs)))
        complete = self.poll(token)[1]
        self.assertEqual(complete["query_state"], "complete")
        self.assertEqual(len(self.client.posts), 1)
        self.assertEqual(len(self.client.polls), 2)
        self.assertNotIn(next(iter(self.client.jobs)), json.dumps(complete))

    def test_queued_running_and_paused_results_remain_pending(self):
        for state in ("Queued", "Running", "Paused"):
            self.client.states = [state]
            result = self.audit()[1]
            self.assertEqual(result["query_state"], "pending")
            self.assertEqual(result["query_status"], state)
            self.assertEqual(result["data"], [])

    def test_wrong_async_task_kind_is_rejected_without_metadata_leak(self):
        self.client.task_name = "POST " + l.PATHS["journal"]
        code, result = self.audit()
        self.assertEqual(code, 502)
        self.assertEqual(result["state"], "result_unverified")
        self.assertNotIn("fixture_secret", json.dumps(result))

    def test_wrong_async_guid_is_rejected_even_when_task_kind_matches(self):
        self.client.guid = "999999999"
        code, result = self.audit()
        self.assertEqual(code, 502)
        self.assertEqual(result["state"], "result_unverified")

    def test_async_result_without_guid_uses_bound_request_and_task_kind(self):
        # Live IRIS 2026.2 omits GUID here despite the specification's field.
        self.client.poll_override = ok({"TaskName": "POST " + l.PATHS["audit"], "State": "Finished", "Result": []})
        code, result = self.audit()
        self.assertEqual(code, 200)
        self.assertEqual(result["query_state"], "complete")
        self.assertEqual(self.client.polls[0][2], {"id": next(iter(self.client.jobs))})

    def test_failed_canceled_unknown_and_failed_transport_never_return_console(self):
        for state in ("Failed", "Canceled", "Unexpected"):
            self.client.states = [state]
            code, result = self.audit()
            self.assertEqual(code, 502)
            self.assertEqual(result["state"], "search_failed")
            text = json.dumps(result)
            for hidden in ("fixture_secret", '"Console":', '"FailureReason":'):
                self.assertNotIn(hidden, text)
        self.client.poll_override = failed("forbidden", 403)
        self.assertEqual(self.audit()[1]["state"], "result_unverified")

    def test_completed_rows_require_an_array_of_objects(self):
        for rows in ({"unexpected": 1}, ["not a record"], [None], [1], None):
            self.client.rows = rows
            code, result = self.audit()
            self.assertEqual(code, 502)
            self.assertEqual(result["state"], "invalid_response")

    def test_audit_record_projection_omits_payload_sessions_and_console(self):
        self.client.rows = [{"AuditIndex": 3, "TimeStamp": "2026-09-19 12:00:00", "Event": "LoginFailure",
                             "Username": "fixture_secret_user", "Namespace": "USER", "Pid": 42,
                             "EventData": "private event payload", "SessionID": "private session",
                             "Console": "private console", "UnknownProperty": "private unknown"}]
        result = self.audit()[1]
        self.assertEqual(result["data"][0]["Username"], "[redacted]_user")
        self.assertEqual(result["data"][0]["AuditIndex"], 3)
        text = json.dumps(result)
        for hidden in ("EventData", "SessionID", "Console", "UnknownProperty", "private event payload", "fixture_secret"):
            self.assertNotIn(hidden, text)

    def test_journal_projection_omits_global_nodes_and_values(self):
        self.client.rows = [{"Address": 42, "TypeName": "SET", "DatabaseName": "USER", "ProcessID": 99,
                             "GlobalNode": "^Private(1)", "Value": "private node value", "SessionID": "private session", "Console": "private console"}]
        result = self.journal()[1]
        self.assertEqual(result["data"][0], {"Address": 42, "TypeName": "SET", "ProcessID": 99, "DatabaseName": "USER"})
        text = json.dumps(result)
        for hidden in ("GlobalNode", "Value", "SessionID", "Console", "private node value"):
            self.assertNotIn(hidden, text)

    def test_result_limit_is_applied_even_if_upstream_returns_more(self):
        self.client.rows = [{"AuditIndex": index, "EventData": "private"} for index in range(150)]
        result = self.audit(limit=7)[1]
        self.assertEqual(result["count"], 7)
        self.assertEqual(len(result["data"]), 7)
        self.assertEqual(result["sample_limit"], 7)
        self.assertTrue(result["at_limit"])
        self.client.rows = [{"AuditIndex": 1}]
        self.assertFalse(self.audit(limit=7)[1]["at_limit"])

    def test_unknown_other_session_and_upstream_ids_cannot_be_polled(self):
        for token in ("unknown-token", "900001"):
            self.assertEqual(self.poll(token)[0], 404)
        started = self.audit()[1]
        other = l.LogOps(self.client, lambda: self.info)
        calls_before = len(self.client.calls)
        self.assertEqual(other.query({"kind": "result", "filters": {"id": started["query_id"]}})[0], 404)
        self.assertEqual(self.poll(next(iter(self.client.jobs)))[0], 404)
        self.assertEqual(len(self.client.calls), calls_before)

    def test_poll_input_schema_is_exact(self):
        for filters in ({}, {"id": 123}, {"id": "x", "kind": "audit"}):
            self.assertEqual(self.ops.query({"kind": "result", "filters": filters})[0], 400)
        self.assertEqual(self.client.calls, [])

    def test_own_token_expires_at_ten_minutes_without_restart(self):
        token = self.audit()[1]["query_id"]
        self.clock += 599
        self.assertEqual(self.poll(token)[0], 200)
        calls_before = len(self.client.calls)
        self.clock += 1
        self.assertEqual(self.poll(token)[0], 404)
        self.assertEqual(len(self.client.calls), calls_before)
        self.assertEqual(len(self.client.posts), 1)

    def test_session_cap_reserves_slots_and_expiration_releases_them(self):
        for _ in range(32):
            self.assertEqual(self.audit()[0], 200)
        code, result = self.audit()
        self.assertEqual(code, 429)
        self.assertEqual(result["state"], "query_limit")
        self.assertEqual(len(self.client.posts), 32)
        self.clock += 600
        self.assertEqual(self.audit()[0], 200)
        self.assertEqual(len(self.client.posts), 33)
        self.assertEqual(len(self.ops.queries), 1)

    def test_dispatch_reservation_without_upstream_id_does_not_resubmit(self):
        self.ops.queries["fixture-pending"] = {"kind": "audit", "limit": 25, "created": self.clock, "upstream_id": None}
        code, result = self.poll("fixture-pending")
        self.assertEqual(code, 409)
        self.assertEqual(result["state"], "query_pending")
        self.assertEqual(self.client.calls, [])

    def test_transport_validator_only_accepts_bounded_read_only_search_routes(self):
        good = [("GET", "/v2/async-result", {"id": "123456"}, None),
                ("POST", l.PATHS["audit"], {"maxRows": 100, "ascending": 0}, None),
                ("POST", l.PATHS["journal"], {"file": JOURNAL_FILE, "reverse": 1, "maxRows": 25}, None)]
        bad = [("GET", "/v2/async-result", {"id": "123", "extra": "x"}, None),
               ("GET", "/v2/async-result", {"id": "../123"}, None),
               ("GET", "/v2/async-result", {"id": 123}, None),
               ("POST", l.PATHS["audit"], {"maxRows": True, "ascending": 0}, None),
               ("POST", l.PATHS["audit"], {"maxRows": 101, "ascending": 0}, None),
               ("POST", l.PATHS["audit"], {"maxRows": 25, "ascending": 1}, None),
               ("POST", l.PATHS["audit"], {"maxRows": 25, "ascending": 0, "events": "*"}, None),
               ("POST", l.PATHS["audit"], {"maxRows": 25, "ascending": 0, "extra": "x"}, None),
               ("POST", l.PATHS["audit"], {"maxRows": 25, "ascending": 0}, {}),
               ("POST", l.PATHS["journal"], {"file": JOURNAL_FILE, "reverse": True, "maxRows": 25}, None),
               ("POST", l.PATHS["journal"], {"file": "../file", "reverse": 1, "maxRows": 25}, None),
               ("DELETE", "/v2/async-result", {"id": "123"}, None)]
        for request in good:
            with self.subTest(request=request):
                self.assertTrue(l.validate_request(*request))
        for request in bad:
            with self.subTest(request=request):
                self.assertFalse(l.validate_request(*request))


if __name__ == "__main__":
    unittest.main()
