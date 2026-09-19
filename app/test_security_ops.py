"""Security module fixtures; no credentials, real network or IRIS writes."""
import copy
import json
import re
import unittest

import security_ops as s

INFO = {"state": "ok", "data": {"privileges": {key: {"use": True} for key in ("Wallet", "Secure", "OAuth2_Client", "OAuth2_Registration")}}}
RESOURCES = {"EditResource": "%Admin_Wallet:USE", "UseResource": "%Admin_Wallet:USE"}
CONFIG = {"AllowedHosts": ["service.example.test"], "RequireTLS": True, "Usage": ["HTTP"], "Secret": {"user": "fixture_user", "password": "fixture_private_value"}}


def okay(result):
    return {"state": "ok", "http_status": 200, "error": None, "payload": {"status": {"errors": []}, "result": result}}


class Client:
    def __init__(self):
        self.collections = {"Demo": copy.deepcopy(RESOURCES)}
        self.secrets = {"Demo": {"Existing": s.KEY_VALUE}}
        self.mutations = []
        self.reads = []
        self.missing_resources = False
        self.fail_write = None
        self.fail_readback = False
        self.details = {}
        self.full_names = False

    def clean_log(self, value):
        if re.search(r"(?i)\b(?:password|authorization|access_token|client_secret)\s*[:=]", value):
            return "[sensitive record withheld]"
        return value.replace("fixture_admin_password", "[redacted]")

    def fetch(self, method, path, query=None, body=None):
        assert s.validate_request(method, path, query, body), "Fixture received an unallowlisted request"
        if method != "GET":
            self.mutations.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
            if self.fail_write:
                response = s.failed(self.fail_write)
                response["error"]["message"] = "fixture_private_value should never escape"
                response["payload"] = {"password": "fixture_private_value"}
                return response
            if path == "/v2/wallet/collection":
                self.collections[query["name"]] = copy.deepcopy(body)
                self.secrets.setdefault(query["name"], {})
            else:
                collection, leaf = query["name"].split(".")
                if method == "DELETE":
                    self.secrets[collection].pop(leaf, None)
                else:
                    self.secrets[collection][leaf] = body["Type"]
            return okay({"Secret": "fixture_private_value", "echoedConfig": body})
        self.reads.append((path, copy.deepcopy(query)))
        if self.fail_readback and self.mutations:
            return s.failed("unavailable")
        if path == "/v2/wallet/collection":
            result = self.collections.get(query["name"])
            return okay(copy.deepcopy(result)) if result else s.failed("not_found", 404)
        if path == "/v2/wallet/secrets":
            rows = [{"Name": query["collection"] + "." + name if self.full_names else name, "Type": kind, "Secret": "fixture_private_value"} for name, kind in self.secrets.get(query["collection"], {}).items()]
            return okay(rows[:query["maxRows"]])
        if path == "/v2/security/resource":
            return s.failed("not_found", 404) if self.missing_resources else okay({"Name": query["name"]})
        return okay(copy.deepcopy(self.details.get(path, {})))


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.info = copy.deepcopy(INFO)
        self.ops = s.SecurityOps(self.client, lambda: self.info)

    def target(self, create=False, **changes):
        return {"collection": "Demo", "name": "NewSecret" if create else "Existing", "type": s.KEY_VALUE,
                "edit_resource": RESOURCES["EditResource"], "use_resource": RESOURCES["UseResource"],
                "expected_type": None if create else s.KEY_VALUE, "config": copy.deepcopy(CONFIG), **changes}

    def deletion_target(self):
        return {key: value for key, value in self.target().items() if key not in ("type", "config")}

    def assert_private(self, result):
        text = json.dumps(result)
        for value in ("fixture_private_value", "fixture_user", "echoedConfig", "WalletSecretConfig", '"config"'):
            self.assertNotIn(value, text)

    def test_transport_rejects_unknown_or_unsafe_requests(self):
        cases = [("GET", "/v2/wallet/secret", {"name": "Demo.Existing"}, None),
                 ("GET", "/v2/wallet/secrets", {"collection": "Demo", "maxRows": 101}, None),
                 ("GET", "/v2/wallet/secrets", {"collection": "Demo", "maxRows": True}, None),
                 ("GET", "/v2/wallet/secrets", {"collection": "Demo", "maxRows": 1, "filter": "*"}, None),
                 ("PUT", "/v2/security/ssl-configuration", {"name": "Demo"}, {"Enabled": True}),
                 ("DELETE", "/v2/wallet/collection", {"name": "Demo"}, None),
                 ("DELETE", "/v2/wallet/secret", {"name": "Demo.Existing"}, {}),
                 ("DELETE", "/v2/wallet/secret", {"name": "Demo.Existing.More"}, None)]
        for args in cases:
            with self.subTest(args=args):
                self.assertFalse(s.validate_request(*args))
        self.assertTrue(s.validate_request("DELETE", "/v2/wallet/secret", {"name": "Demo.Existing"}))

    def test_config_requires_explicit_hosts_tls_http_and_flat_values(self):
        self.assertTrue(s.config_valid(CONFIG))
        for change in ({"RequireTLS": False}, {"AllowedHosts": []}, {"AllowedHosts": ["*"]}, {"AllowedHosts": ["https://example.test"]}, {"AllowedHosts": ["localhost:1234"]}, {"Usage": ["SQL"]}, {"Secret": {}}, {"Secret": {"password": {"nested": "value"}}}, {"Secret": {"password": "has\nnewline"}}):
            with self.subTest(change=change):
                self.assertFalse(s.config_valid({**CONFIG, **change}))
        self.assertFalse(s.config_valid({**CONFIG, "PrivateKey": "material"}))
        self.assertFalse(s.config_valid({**CONFIG, "Secret": {"password": "x" * 4097}}))
        self.assertTrue(s.allowed_host("127.0.0.1"))
        self.assertTrue(s.allowed_host("::1"))

    def test_collection_inspect_resource_context(self):
        result = self.ops.inspect("wallet_collection", "Demo")
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["data"], {"Name": "Demo", **RESOURCES})
        self.assertEqual(result["context"]["edit_resource"], RESOURCES["EditResource"])

    def test_secret_metadata_normalizes_full_and_leaf_names_without_values(self):
        for full in (False, True):
            self.client.full_names = full
            result = self.ops.inspect("wallet_secrets", "Demo")
            self.assertEqual(result["data"], [{"Name": "Existing", "FullName": "Demo.Existing", "Type": s.KEY_VALUE}])
            self.assertEqual(result["targets"][0]["actions"], ["wallet.secret.update", "wallet.secret.delete"])
            self.assert_private(result)

    def test_inspect_names_context_and_privilege_are_guarded(self):
        for kind, name, context in (("unknown", "Demo", None), ("wallet_secrets", "Demo.Other", None), ("tls", "Name\r\n", None), ("tls", "Demo", {"url": "https://example.test"})):
            self.assertEqual(self.ops.inspect(kind, name, context)["state"], "invalid_input")
        self.info["data"]["privileges"]["Secure"]["use"] = False
        self.assertEqual(self.ops.inspect("tls", "Demo")["state"], "forbidden")
        self.assertEqual(self.client.reads, [])

    def test_tls_x509_and_oauth_metadata_are_meaningful_but_whitelisted(self):
        self.client.details["/v2/security/ssl-configuration"] = {"Enabled": True, "TLSMinVersion": 8, "VerifyPeer": 2, "CipherList": ["HIGH"], "PrivateKeyFile": "/private/key", "PrivateKeyPassword": "fixture_private_value", "CertificateFile": "/public/cert"}
        tls = self.ops.inspect("tls", "Demo")
        self.assertEqual(tls["data"]["TLSMinVersion"], 8)
        self.assertTrue(tls["data"]["HasPrivateKeyFile"])
        self.assertNotIn("/private/key", json.dumps(tls))
        self.assert_private(tls)
        self.client.details["/v2/security/x509-credential"] = {"OwnerList": ["Operator"], "PeerNames": ["service.example.test"], "PrivateKey": "fixture_private_value"}
        self.assertEqual(self.ops.inspect("x509", "Demo")["data"]["PeerNames"], ["service.example.test"])
        self.client.details["/v2/security/oauth2/client/client-configuration"] = {"Enabled": True, "ClientType": "confidential", "ClientCredentials": "fixture_private_value", "RedirectionEndpoint": "https://user:other_private@example.test/callback?session_token=other_private#fragment", "Metadata": {"grant_types": ["authorization_code"], "token_endpoint_auth_method": "private_key_jwt", "client_secret": "fixture_private_value"}}
        oauth = self.ops.inspect("oauth_client", "Demo")
        self.assertEqual(oauth["data"]["RedirectionEndpoint"], "https://example.test/callback")
        self.assertEqual(oauth["data"]["Metadata"]["grant_types"], ["authorization_code"])
        self.assertNotIn("other_private", json.dumps(oauth))
        self.assert_private(oauth)

    def test_collection_creation_checks_absence_existing_resources_and_readback(self):
        target = {"name": "NewCollection", "edit_resource": RESOURCES["EditResource"], "use_resource": RESOURCES["UseResource"], "expected_absent": True}
        code, result = self.ops.action("wallet.collection.create", target)
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(self.client.mutations[0], ("PUT", "/v2/wallet/collection", {"name": "NewCollection"}, RESOURCES))
        self.assertIn(("/v2/security/resource", {"name": "%Admin_Wallet"}), self.client.reads)
        self.assert_private(result)

    def test_collection_creation_refuses_existing_or_missing_resource(self):
        target = {"name": "Demo", "edit_resource": RESOURCES["EditResource"], "use_resource": RESOURCES["UseResource"], "expected_absent": True}
        self.assertEqual(self.ops.action("wallet.collection.create", target)[0], 409)
        self.client.missing_resources = True
        self.assertEqual(self.ops.action("wallet.collection.create", {**target, "name": "NewCollection"})[1]["state"], "resource_unverified")
        self.assertEqual(self.client.mutations, [])

    def test_create_update_delete_are_write_only_and_metadata_verified(self):
        code, result = self.ops.action("wallet.secret.create", self.target(create=True))
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "accepted_metadata_verified")
        self.assertFalse(result["value_verified"])
        self.assert_private(result)
        code, result = self.ops.action("wallet.secret.update", self.target())
        self.assertEqual(result["state"], "accepted_metadata_verified")
        self.assert_private(result)
        self.assertEqual(self.client.mutations[1][3], {"Type": s.KEY_VALUE, "WalletSecretConfig": CONFIG})
        code, result = self.ops.action("wallet.secret.delete", self.deletion_target())
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["verification"]["data"], [])
        self.assertEqual(self.client.mutations[2][0], "DELETE")
        self.assertIsNone(self.client.mutations[2][3])
        self.assert_private(result)

    def test_metadata_and_collection_resource_changes_prevent_secret_writes(self):
        self.assertEqual(self.ops.action("wallet.secret.update", self.target(edit_resource="Other:USE"))[1]["state"], "target_changed")
        self.client.secrets["Demo"]["Existing"] = "%Wallet.RSA"
        self.assertEqual(self.ops.action("wallet.secret.update", self.target())[1]["state"], "target_changed")
        self.assertEqual(self.ops.action("wallet.secret.create", self.target(create=True, name="Existing"))[0], 409)
        self.assertEqual(self.client.mutations, [])

    def test_full_secret_sample_does_not_prove_create_absence(self):
        self.client.secrets["Demo"] = {"Secret" + str(index): s.KEY_VALUE for index in range(s.ROW_LIMIT)}
        self.assertEqual(self.ops.action("wallet.secret.create", self.target(create=True))[1]["state"], "target_unverified")
        self.assertEqual(self.client.mutations, [])

    def test_fresh_privilege_check_and_tls_disabled(self):
        self.info["data"]["privileges"]["Wallet"]["use"] = False
        self.assertEqual(self.ops.action("wallet.secret.update", self.target())[0], 403)
        self.assertEqual(self.ops.action("security.tls.set_enabled", {"name": "Demo", "enabled": True})[0], 400)
        self.assertEqual(self.client.mutations, [])
        self.info["data"]["privileges"]["Wallet"]["use"] = True
        self.info["data"]["privileges"]["Secure"]["use"] = False
        actions = {item["id"]: item for item in self.ops.action_definitions(self.info)}
        self.assertFalse(actions["wallet.collection.create"]["enabled"])
        self.assertTrue(actions["wallet.secret.update"]["enabled"])
        self.assertNotIn("security.tls.set_enabled", actions)

    def test_unknown_extra_config_crypto_and_missing_expected_metadata_rejected(self):
        for target in (self.target(unexpected="value"), self.target(type="%Wallet.RSA"), self.target(expected_type=None), self.target(config={}), self.target(collection="Demo.Other")):
            self.assertEqual(self.ops.action("wallet.secret.update", target)[0], 400)
        self.assertEqual(self.ops.action("wallet.secret.delete", self.target())[0], 400)
        self.assertEqual(self.client.mutations, [])

    def test_uncertain_write_with_secret_echo_is_not_retried_or_exposed(self):
        self.client.fail_write = "unavailable"
        code, result = self.ops.action("wallet.secret.update", self.target())
        self.assertEqual(code, 502)
        self.assertEqual(result["state"], "outcome_unknown")
        self.assertEqual(len(self.client.mutations), 1)
        self.assert_private(result)

    def test_successful_write_failed_readback_stays_unverified(self):
        self.client.fail_readback = True
        code, result = self.ops.action("wallet.secret.update", self.target())
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "accepted_unverified")
        self.assertEqual(result["verification"]["state"], "unavailable")
        self.assert_private(result)

    def test_read_transport_exceptions_do_not_disclose_messages(self):
        def failure(*args):
            raise RuntimeError("fixture_private_value")
        self.client.fetch = failure
        result = self.ops.inspect("wallet_collection", "Demo")
        self.assertEqual(result["state"], "unavailable")
        self.assert_private(result)


if __name__ == "__main__":
    unittest.main()
