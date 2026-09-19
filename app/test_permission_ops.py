"""Permission workflow checks with an isolated in-memory IRIS transport."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import permission_ops as p


def ok(detail, status=200):
    return {"state": "ok", "http_status": status, "error": None,
            "payload": {"status": {"errors": []}, "result": copy.deepcopy(detail)}}


def failed(state, status=None):
    return {"state": state, "http_status": status,
            "error": {"message": "fixture_sensitive_diagnostic"}, "payload": None}


INFO = {"state": "ok", "data": {"privileges": {"Secure": {"use": True}}}}


class FakeClient:
    def __init__(self):
        self.roles = {"FieldworkReaders": {"Description": "Fixture role", "GrantedRoles": [], "EscalationOnly": False,
                                           "Resources": [{"Name": "FieldworkData", "Permissions": "R"}],
                                           "ExtraServerField": "must survive"}}
        self.resources = {"FieldworkData": {"Description": "Fixture data", "PublicPermission": ""},
                          "FieldworkJobs": {"Description": "Fixture jobs", "PublicPermission": ""}}
        self.users = {"_SYSTEM": {"Enabled": True, "NameSpace": "%SYS", "Roles": ["%All"],
                                  "EscalationRoles": [], "FullName": "private identity",
                                  "EmailAddress": "private@example.test", "Password": "fixture_secret"}}
        self.inventory = [{"Name": name, "ResourceType": "Application", "AllowDelete": True} for name in self.resources]
        self.calls = []
        self.put_failure = None
        self.get_failure = None
        self.alter_other_field = False
        self.bad_readback = False
        self.create_status = 201

    def clean(self, value):
        if isinstance(value, str):
            return value.replace("fixture_secret", "[redacted]")
        return copy.deepcopy(value)

    def clean_log(self, value):
        return self.clean(value)

    def fetch(self, method, path, query=None, body=None):
        self.calls.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
        name = (query or {}).get("name")
        if method == "GET":
            if self.get_failure:
                return copy.deepcopy(self.get_failure)
            if path == "/v2/security/resources":
                names = query.get("names", "").split(",")
                return ok([row for row in self.inventory if row["Name"] in names] if query.get("names") else self.inventory)
            store = {"/v2/security/role": self.roles, "/v2/security/resource": self.resources,
                     "/v2/security/user": self.users}[path]
            if self.bad_readback and any(call[0] == "PUT" for call in self.calls):
                return failed("unavailable")
            return ok(store[name]) if name in store else failed("not_found", 404)
        if method == "PUT":
            if self.put_failure:
                return copy.deepcopy(self.put_failure)
            if path == "/v2/security/role":
                self.roles[name].update(copy.deepcopy(body))
                if self.alter_other_field:
                    self.roles[name]["GrantedRoles"] = ["ChangedElsewhere"]
                return ok(self.roles[name])
            if path == "/v2/security/resource":
                self.resources[name] = copy.deepcopy(body)
                return ok(self.resources[name], self.create_status)
        raise AssertionError("Unexpected fixture request")

    @property
    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


class PermissionOpsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(p, "ROLE_RESOURCE_UPDATES_VERIFIED", True))
        self.stack.enter_context(patch.object(p, "RESOURCE_CREATION_VERIFIED", True))
        self.client = FakeClient()
        self.info = copy.deepcopy(INFO)
        self.ops = p.PermissionOps(self.client, lambda: self.info)

    def role_target(self, **changes):
        return {"name": "FieldworkReaders", "resources": [{"Name": "FieldworkData", "Permissions": "RW"}],
                "expected_resources": [{"Name": "FieldworkData", "Permissions": "R"}], **changes}

    def role_action(self, **changes):
        return self.ops.action("role.set_resources", self.role_target(**changes))

    def resource_action(self, **changes):
        return self.ops.action("resource.create", {"name": "FieldworkNew", "description": "New private resource", **changes})

    def test_inspection_keeps_permissions_and_excludes_identity_and_credentials(self):
        result = self.ops.inspect("user", "_SYSTEM")
        self.assertEqual(result["data"]["Roles"], ["%All"])
        self.assertEqual(result["count"], 1)
        text = json.dumps(result)
        for secret in ("fixture_secret", "private identity", "private@example.test", "Password", "FullName"):
            self.assertNotIn(secret, text)
        self.assertEqual(self.client.writes, [])

    def test_role_details_include_resources_and_editability(self):
        result = self.ops.inspect("role", "FieldworkReaders")
        self.assertTrue(result["data"]["editable"])
        self.assertEqual(result["data"]["Resources"], [{"Name": "FieldworkData", "Permissions": "R"}])
        self.assertNotIn("ExtraServerField", result["data"])
        self.client.roles["FieldworkReaders"]["GrantedRoles"] = ["%All"]
        self.assertFalse(self.ops.inspect("role", "FieldworkReaders")["data"]["editable"])

    def test_invalid_inspections_do_not_send_requests(self):
        for kind, name in (("wallet", "name"), ("role", "../name"), ("user", "bob?x=1"), ("resource", "x\n")):
            with self.subTest(kind=kind, name=name), self.assertRaises(ValueError):
                self.ops.inspect(kind, name)
        self.assertEqual(self.client.calls, [])

    def test_raw_error_detail_is_never_returned(self):
        self.client.get_failure = failed("forbidden", 403)
        result = self.ops.inspect("role", "FieldworkReaders")
        self.assertEqual(result["state"], "forbidden")
        self.assertNotIn("fixture_sensitive_diagnostic", json.dumps(result))

    def test_capability_requires_privilege_and_live_semantics_flags(self):
        with patch.object(p, "ROLE_RESOURCE_UPDATES_VERIFIED", False):
            self.assertFalse(self.ops.action_definitions(self.info)[0]["enabled"])
            self.assertEqual(self.role_action()[0], 403)
        with patch.object(p, "RESOURCE_CREATION_VERIFIED", False):
            self.assertEqual(self.resource_action()[0], 403)
        self.info["data"]["privileges"]["Secure"]["use"] = False
        self.assertEqual(self.role_action()[0], 403)
        self.assertEqual(self.resource_action()[0], 403)
        self.assertEqual(self.client.calls, [])

    def test_minimal_role_update_and_other_field_preservation(self):
        code, result = self.role_action()
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertTrue(result["verification"]["other_fields_unchanged"])
        self.assertEqual(self.client.writes, [("PUT", "/v2/security/role", {"name": "FieldworkReaders"},
                                             {"Resources": [{"Name": "FieldworkData", "Permissions": "RW"}]})])
        self.assertEqual(self.client.roles["FieldworkReaders"]["ExtraServerField"], "must survive")

    def test_all_custom_grants_can_be_revoked(self):
        self.assertEqual(self.role_action(resources=[])[1]["state"], "verified")
        self.assertEqual(self.client.writes[0][3], {"Resources": []})

    def test_grant_order_is_canonical_without_duplicate_permissions(self):
        expected = [{"Name": "FieldworkJobs", "Permissions": "U"}, {"Name": "FieldworkData", "Permissions": "WR"}]
        self.assertEqual(p.normalize_resources(expected), [{"Name": "FieldworkData", "Permissions": "RW"}, {"Name": "FieldworkJobs", "Permissions": "U"}])
        for value in ([{"Name": "FieldworkData", "Permissions": "RR"}], [{"Name": "FieldworkData", "Permissions": "X"}],
                      [{"Name": "FieldworkData", "Permissions": ""}], [{"Name": "FieldworkData", "Permissions": "U", "Extra": 1}],
                      [{"Name": "FieldworkData", "Permissions": "R"}, {"Name": "fieldworkdata", "Permissions": "U"}],
                      [{"Name": f"Data{x}", "Permissions": "U"} for x in range(41)]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.normalize_resources(value)

    def test_strict_targets_and_protected_names_never_write(self):
        for name in ("%All", "%Manager", "_SYSTEM", "AdminRole", "SystemReaders", "root", "../role", "a" * 65):
            self.assertEqual(self.role_action(name=name)[0], 400)
            self.assertEqual(self.resource_action(name=name)[0], 400)
        target = self.role_target()
        target["Description"] = "Unrelated change"
        self.assertEqual(self.ops.action("role.set_resources", target)[0], 400)
        self.assertEqual(self.resource_action(PublicPermission="U")[0], 400)
        self.assertEqual(self.client.writes, [])

    def test_changed_or_missing_role_state_is_rejected_without_write(self):
        self.client.roles["FieldworkReaders"]["Resources"] = []
        self.assertEqual(self.role_action()[1]["state"], "target_changed")
        self.assertEqual(self.role_action(name="MissingRole")[1]["state"], "target_unverified")
        self.assertEqual(self.client.writes, [])

    def test_inherited_system_and_escalation_roles_are_rejected(self):
        for change in ({"GrantedRoles": ["%All"]}, {"GrantedRoles": ["CustomInherited"]},
                       {"EscalationOnly": True}, {"Resources": [{"Name": "%Admin_Secure", "Permissions": "U"}]}):
            client = FakeClient()
            client.roles["FieldworkReaders"].update(change)
            ops = p.PermissionOps(client, lambda: self.info)
            self.assertEqual(ops.action("role.set_resources", self.role_target())[1]["state"], "target_unverified")
            self.assertEqual(client.writes, [])

    def test_unknown_system_or_non_deletable_resources_cannot_be_granted(self):
        for field, value in (("ResourceType", "System"), ("ResourceType", "Unknown"), ("AllowDelete", False)):
            self.client.inventory[0][field] = value
            self.assertEqual(self.role_action()[1]["state"], "resource_not_permitted")
            self.client.inventory = FakeClient().inventory
        self.assertEqual(self.role_action(resources=[{"Name": "MissingResource", "Permissions": "U"}])[1]["state"], "resource_not_permitted")
        self.assertEqual(self.client.writes, [])

    def test_exact_filter_finds_application_resource_after_large_system_inventory(self):
        self.client.inventory = [{"Name": f"%Other{x}", "ResourceType": "System", "AllowDelete": False} for x in range(150)] + self.client.inventory
        self.assertEqual(self.role_action()[1]["state"], "verified")
        reads = [call for call in self.client.calls if call[1] == "/v2/security/resources"]
        self.assertEqual(reads, [("GET", "/v2/security/resources", {"names": "FieldworkData", "maxRows": 100}, None)])

    def test_other_field_change_and_bad_readback_do_not_claim_verified(self):
        self.client.alter_other_field = True
        result = self.role_action()[1]
        self.assertEqual(result["state"], "accepted_unverified")
        self.assertFalse(result["verification"]["other_fields_unchanged"])
        self.assertEqual(len(self.client.writes), 1)
        client = FakeClient()
        client.bad_readback = True
        result = p.PermissionOps(client, lambda: self.info).action("role.set_resources", self.role_target())[1]
        self.assertEqual(result["state"], "accepted_unverified")
        self.assertEqual(len(client.writes), 1)

    def test_uncertain_write_never_retries_or_leaks_diagnostic(self):
        self.client.put_failure = failed("invalid_response", 200)
        code, result = self.role_action()
        self.assertEqual(code, 502)
        self.assertEqual(result["state"], "outcome_unknown")
        self.assertEqual(len(self.client.writes), 1)
        self.assertNotIn("fixture_sensitive_diagnostic", json.dumps(result))

    def test_create_private_resource_requires_absence_and_verifies_creation(self):
        code, result = self.resource_action()
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(self.client.writes, [("PUT", "/v2/security/resource", {"name": "FieldworkNew"},
                                             {"Description": "New private resource", "PublicPermission": ""})])
        self.assertEqual(result["verification"]["data"]["PublicPermission"], "")

    def test_create_never_overwrites_known_resource_or_unknown_state(self):
        self.assertEqual(self.resource_action(name="FieldworkData")[1]["state"], "target_exists_or_unverified")
        for state, status in (("unavailable", None), ("forbidden", 403), ("not_found", None)):
            self.client.get_failure = failed(state, status)
            self.assertEqual(self.resource_action()[1]["state"], "target_exists_or_unverified")
        self.assertEqual(self.client.writes, [])

    def test_create_200_does_not_prove_creation_and_no_retry_occurs(self):
        self.client.create_status = 200
        self.assertEqual(self.resource_action()[1]["state"], "accepted_unverified")
        self.assertEqual(len(self.client.writes), 1)

    def test_create_description_and_privacy_inputs_are_strict(self):
        for value in ("", " spaced ", "x\n", "x" * 241, None, 1):
            self.assertEqual(self.resource_action(description=value)[0], 400)
        self.assertEqual(self.client.writes, [])

    def test_pinned_spec_has_only_the_supported_fields_and_routes(self):
        path = Path(__file__).resolve().parents[1] / "spec" / "mainspec_v2.json"
        if not path.is_file():
            self.skipTest("Pinned API specification is not bundled; fetch via spec/SOURCE.json for this optional reference check.")
        spec = json.loads(path.read_text())
        for method, path in p.WRITE_ROUTES:
            self.assertIn(method.lower(), spec["paths"][path])
        self.assertIn("Resources", spec["components"]["schemas"]["Role"]["properties"])
        resource_fields = spec["components"]["schemas"]["Resource"]["properties"]
        self.assertIn("Description", resource_fields)
        self.assertIn("PublicPermission", resource_fields)
        self.assertNotIn(("PUT", "/v2/security/user"), p.WRITE_ROUTES)

    def test_transport_validator_accepts_only_exact_supported_requests(self):
        good = [("GET", "/v2/security/user", {"name": "_SYSTEM"}, None),
                ("GET", "/v2/security/resources", {"maxRows": 100}, None),
                ("GET", "/v2/security/resources", {"names": "FieldworkData,FieldworkJobs", "maxRows": 100}, None),
                ("PUT", "/v2/security/role", {"name": "FieldworkReaders"}, {"Resources": []}),
                ("PUT", "/v2/security/resource", {"name": "FieldworkNew"}, {"Description": "Fixture", "PublicPermission": ""})]
        bad = [("GET", "/v2/security/user", {"name": "_SYSTEM", "extra": "x"}, None),
               ("GET", "/v2/security/resource", {"name": "good"}, {}),
               ("GET", "/v2/security/resources", {"maxRows": True}, None),
               ("GET", "/v2/security/resources", {"maxRows": 101}, None),
               ("GET", "/v2/security/resources", {"names": "Fieldwork*", "maxRows": 100}, None),
               ("GET", "/v2/security/resources", {"names": "%Admin_Secure", "maxRows": 100}, None),
               ("GET", "/v2/security/resources", {"names": "FieldworkData,,FieldworkJobs", "maxRows": 100}, None),
               ("GET", "/v2/security/resources", {"names": "FieldworkData,fieldworkdata", "maxRows": 100}, None),
               ("PUT", "/v2/security/user", {"name": "normal"}, {"Enabled": True}),
               ("DELETE", "/v2/security/role", {"name": "FieldworkReaders"}, None),
               ("PUT", "/v2/security/role", {"name": "%All"}, {"Resources": []}),
               ("PUT", "/v2/security/role", {"name": "FieldworkReaders"}, {"Resources": [], "GrantedRoles": ["%All"]}),
               ("PUT", "/v2/security/resource", {"name": "FieldworkNew"}, {"Description": "Fixture", "PublicPermission": "U"}),
               ("PUT", "/v2/security/resource", {"name": "FieldworkNew"}, {"Description": "Fixture"})]
        for request in good:
            with self.subTest(request=request):
                self.assertTrue(p.validate_request(*request))
        for request in bad:
            with self.subTest(request=request):
                self.assertFalse(p.validate_request(*request))


if __name__ == "__main__":
    unittest.main()
