"""Curated security operations for the loopback Fieldwork gateway.

The caller MUST enforce its same-origin/CSRF/review checks and hold its action
lock before calling action(). Secret configuration is write-only and excluded
from every response. No dependency on backend.py or the vendored specification.
"""
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit, urlunsplit

ROW_LIMIT = 100
KEY_VALUE = "%Wallet.KeyValue"
SECRET_TYPES = (KEY_VALUE, "%Wallet.SymmetricKey", "%Wallet.RSA")
SOURCE = {"repository": "https://github.com/intersystems-community/sysadmin-api-specification",
          "commit": "f764aea427e5c0b1dd08a4c18a0457e0ff7b3b34"}
INSPECT = {
    "wallet_collection": ("/v2/wallet/collection", "name", "Wallet", "Wallet collection"),
    "wallet_secrets": ("/v2/wallet/secrets", "collection", "Wallet", "Wallet secret metadata"),
    "x509": ("/v2/security/x509-credential", "alias", "Secure", "X.509 credential configuration"),
    "tls": ("/v2/security/ssl-configuration", "name", "Secure", "TLS configuration"),
    "oauth_server": ("/v2/security/oauth2/client/server-definition", "serverId", "OAuth2_Client", "OAuth server definition"),
    "oauth_client": ("/v2/security/oauth2/client/client-configuration", "applicationName", "OAuth2_Client", "OAuth client configuration"),
    "oauth_registration": ("/v2/security/oauth2/server/client", "clientId", "OAuth2_Registration", "OAuth registered client"),
}
READ_PATHS = {item[0] for item in INSPECT.values()} | {"/v2/security/resource"}
WRITE_ROUTES = {("PUT", "/v2/wallet/collection"), ("PUT", "/v2/wallet/secret"), ("DELETE", "/v2/wallet/secret")}
FIELDS = {
    "wallet_collection": "EditResource UseResource",
    "x509": "OwnerList PeerNames CAFile",
    "tls": "Enabled Type TLSMinVersion TLSMaxVersion VerifyPeer VerifyDepth AuthorizeCN CipherList Ciphersuites DiffieHellmanBits OCSP OCSPTimeout Description",
    "oauth_server": "IssuerEndpoint SSLConfiguration",
    "oauth_client": "OAuth2ServerDefinition Enabled Description ClientType SSLConfiguration RedirectionEndpoint DefaultScope JWTAudience",
    "oauth_registration": "Name RedirectURL LaunchURL DefaultScope Description ClientType",
}
CLIENT_METADATA = "redirect_uris response_types grant_types application_type client_name id_token_signed_response_alg id_token_encrypted_response_alg id_token_encrypted_response_enc userinfo_signed_response_alg access_token_signed_response_alg request_object_signing_alg token_endpoint_auth_method token_endpoint_auth_signing_alg default_max_age frontchannel_logout_uri frontchannel_logout_session_required".split()
SERVER_METADATA = "issuer authorization_endpoint token_endpoint userinfo_endpoint revocation_endpoint introspection_endpoint jwks_uri registration_endpoint end_session_endpoint scopes_supported response_types_supported response_modes_supported code_challenge_methods_supported grant_types_supported subject_types_supported id_token_signing_alg_values_supported id_token_encryption_alg_values_supported token_endpoint_auth_methods_supported token_endpoint_auth_signing_alg_values_supported claims_supported claims_parameter_supported request_parameter_supported request_uri_parameter_supported require_request_uri_registration frontchannel_logout_supported frontchannel_logout_session_supported".split()
URL_FIELDS = {"IssuerEndpoint", "RedirectionEndpoint", "RedirectURL", "LaunchURL", "redirect_uris", "frontchannel_logout_uri", "issuer", "authorization_endpoint", "token_endpoint", "userinfo_endpoint", "revocation_endpoint", "introspection_endpoint", "jwks_uri", "registration_endpoint", "end_session_endpoint"}
ERRORS = {
    "unauthorized": "IRIS rejected authentication.", "forbidden": "The required IRIS privilege or resource permission was denied.",
    "not_found": "The requested configuration was not found.", "unavailable": "The security API could not be reached.",
    "invalid_response": "The security API returned an unexpected response.", "application_error": "IRIS reported an application error; sensitive detail was withheld.",
    "invalid_input": "Input does not match this operation's bounded schema.", "unsupported": "This security operation is not enabled.",
}


def component(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value) is not None


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_%][A-Za-z0-9_.% -]{0,127}", value) is not None


def resource_permission(value):
    if not isinstance(value, str):
        return False
    return re.fullmatch(r"%?[A-Za-z][A-Za-z0-9_.-]{0,95}:(?:USE|READ|WRITE|U|R|W)", value) is not None


def allowed_host(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253 or value != value.strip():
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in value.split("."))


def config_valid(value):
    if not isinstance(value, dict) or set(value) != {"AllowedHosts", "RequireTLS", "Usage", "Secret"}:
        return False
    hosts, secret = value["AllowedHosts"], value["Secret"]
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= 16 or not all(allowed_host(host) for host in hosts) or len(set(hosts)) != len(hosts):
        return False
    if value["RequireTLS"] is not True or value["Usage"] != ["HTTP"] or not isinstance(secret, dict) or not 1 <= len(secret) <= 16:
        return False
    if not all(component(key) and isinstance(text, str) and 1 <= len(text) <= 4096 and not any(ord(c) < 32 or ord(c) == 127 for c in text) for key, text in secret.items()):
        return False
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8")) <= 12288


def validate_request(method, path, query=None, body=None):
    """Transport-side validator; returns False for all unlisted query/body shapes."""
    query = {} if query is None else query
    if not isinstance(query, dict):
        return False
    if method == "GET":
        if body is not None or path not in READ_PATHS:
            return False
        if path == "/v2/security/resource":
            return set(query) == {"name"} and identifier(query["name"])
        kind = next((kind for kind, spec in INSPECT.items() if spec[0] == path), None)
        parameter = INSPECT[kind][1]
        if kind == "wallet_secrets":
            return set(query) == {"collection", "maxRows"} and component(query["collection"]) and type(query["maxRows"]) is int and 1 <= query["maxRows"] <= ROW_LIMIT
        check = component if kind == "wallet_collection" else identifier
        return set(query) == {parameter} and check(query[parameter])
    if (method, path) not in WRITE_ROUTES or set(query) != {"name"}:
        return False
    if path == "/v2/wallet/collection":
        return component(query["name"]) and isinstance(body, dict) and set(body) == {"EditResource", "UseResource"} and all(resource_permission(v) for v in body.values())
    name = query["name"]
    if not isinstance(name, str) or len(name.split(".")) != 2 or not all(component(part) for part in name.split(".")):
        return False
    if method == "DELETE":
        return body is None
    return isinstance(body, dict) and set(body) == {"Type", "WalletSecretConfig"} and body["Type"] == KEY_VALUE and config_valid(body["WalletSecretConfig"])


def public(response):
    state = response.get("state", "invalid_response") if isinstance(response, dict) else "invalid_response"
    status = response.get("http_status") if isinstance(response, dict) else None
    return {"state": state, "http_status": status if type(status) is int else None,
            "error": None if state == "ok" else {"code": state, "message": ERRORS.get(state, "The security operation did not complete; upstream detail was withheld.")}}


def failed(state, status=None):
    return {**public({"state": state, "http_status": status}), "payload": None}


def permitted(info, privilege):
    return isinstance(info, dict) and info.get("state") == "ok" and (info.get("data") or {}).get("privileges", {}).get(privilege, {}).get("use") is True


class SecurityOps:
    def __init__(self, client, info_callback):
        self.client, self.info_callback = client, info_callback

    def _fetch(self, method, path, query=None, body=None):
        if not validate_request(method, path, query, body):
            return failed("invalid_input")
        try:
            response = self.client.fetch(method, path, query, body)
        except Exception:
            return failed("unavailable")
        if not isinstance(response, dict):
            return failed("invalid_response")
        return response

    def _info(self):
        try:
            return self.info_callback()
        except Exception:
            return {"state": "unavailable", "data": None}

    def _clean(self, value, url=False):
        if isinstance(value, str):
            value = self.client.clean_log(value)
            if url:
                try:
                    parts = urlsplit(value)
                    if parts.scheme not in ("http", "https") or not parts.hostname:
                        return "[non-HTTP endpoint withheld]"
                    hostname = parts.hostname
                    authority = ("[" + hostname + "]") if ":" in hostname else hostname
                    if parts.port:
                        authority += ":" + str(parts.port)
                    value = urlunsplit((parts.scheme, authority, parts.path, "", ""))
                except ValueError:
                    return "[invalid endpoint withheld]"
            return value[:512]
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, list):
            return [self._clean(item, url) for item in value[:32] if item is None or isinstance(item, (str, bool, int, float))]
        return None

    def _resource(self, kind, name, response, data=None):
        path, _, _, label = INSPECT.get(kind, ("", "", "", "Security configuration"))
        return {"key": kind, "label": label, "method": "GET", "path": "/api/admin" + path, **public(response),
                "data": data, "count": len(data) if isinstance(data, list) else 1 if isinstance(data, dict) else 0,
                "sample_limit": ROW_LIMIT if kind == "wallet_secrets" else None, "targets": [],
                "limitations": ["Secret values and private keys are not returned. Endpoint URL query strings and user information are withheld."]}

    def _collection(self, name):
        response = self._fetch("GET", "/v2/wallet/collection", {"name": name})
        raw = (response.get("payload") or {}).get("result") if response.get("state") == "ok" else None
        if response.get("state") != "ok":
            return response, None
        if not isinstance(raw, dict) or not all(resource_permission(raw.get(key)) for key in ("EditResource", "UseResource")):
            return failed("invalid_response", response.get("http_status")), None
        return response, {"Name": name, "EditResource": raw["EditResource"], "UseResource": raw["UseResource"]}

    def _secret_list(self, collection):
        response = self._fetch("GET", "/v2/wallet/secrets", {"collection": collection, "maxRows": ROW_LIMIT})
        raw = (response.get("payload") or {}).get("result") if response.get("state") == "ok" else None
        if response.get("state") != "ok":
            return response, None
        if not isinstance(raw, list) or len(raw) > ROW_LIMIT:
            return failed("invalid_response", response.get("http_status")), None
        rows, seen = [], set()
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("Name"), str) or item.get("Type") not in SECRET_TYPES:
                return failed("invalid_response", response.get("http_status")), None
            leaf = item["Name"].removeprefix(collection + ".")
            if not component(leaf) or leaf in seen:
                return failed("invalid_response", response.get("http_status")), None
            seen.add(leaf)
            rows.append({"Name": leaf, "FullName": collection + "." + leaf, "Type": item["Type"]})
        return response, rows

    def inspect(self, kind, name, context=None):
        if kind not in INSPECT or context not in (None, {}):
            return self._resource(kind, name, failed("invalid_input"))
        check = component if kind.startswith("wallet_") else identifier
        if not check(name):
            return self._resource(kind, name, failed("invalid_input"))
        path, parameter, privilege, _ = INSPECT[kind]
        if not permitted(self._info(), privilege):
            return self._resource(kind, name, failed("forbidden", 403))
        if kind in ("wallet_collection", "wallet_secrets"):
            response, collection = self._collection(name)
            if collection is None:
                return self._resource(kind, name, response)
            if kind == "wallet_collection":
                result = self._resource(kind, name, response, collection)
                result["context"] = {"collection": name, "edit_resource": collection["EditResource"], "use_resource": collection["UseResource"]}
                return result
            response, rows = self._secret_list(name)
            result = self._resource(kind, name, response, rows)
            result["context"] = {"collection": name, "edit_resource": collection["EditResource"], "use_resource": collection["UseResource"]}
            if rows is not None:
                result["targets"] = [{"type": "wallet_secret", "collection": name, "name": row["Name"], "expected_type": row["Type"], "edit_resource": collection["EditResource"], "use_resource": collection["UseResource"], "actions": ["wallet.secret.update", "wallet.secret.delete"] if row["Type"] == KEY_VALUE else []} for row in rows]
                result["limitations"].append("Names and types are bounded metadata. A full sample cannot establish that a name is absent.")
            return result
        response = self._fetch("GET", path, {parameter: name})
        raw = (response.get("payload") or {}).get("result") if response.get("state") == "ok" else None
        if response.get("state") != "ok":
            return self._resource(kind, name, response)
        if not isinstance(raw, dict):
            return self._resource(kind, name, failed("invalid_response", response.get("http_status")))
        data = {field: self._clean(raw[field], field in URL_FIELDS) for field in FIELDS[kind].split() if field in raw}
        if kind == "tls":
            data.update({"HasCAFile": bool(raw.get("CAFile")), "HasCertificateFile": bool(raw.get("CertificateFile")), "HasPrivateKeyFile": bool(raw.get("PrivateKeyFile"))})
        if kind.startswith("oauth_") and isinstance(raw.get("Metadata"), dict):
            allowed = SERVER_METADATA if kind == "oauth_server" else CLIENT_METADATA
            data["Metadata"] = {key: self._clean(raw["Metadata"][key], key in URL_FIELDS) for key in allowed if key in raw["Metadata"]}
        result = self._resource(kind, name, response, data)
        result["context"] = {"name": name}
        return result

    def action_definitions(self, info):
        wallet, secure = permitted(info, "Wallet"), permitted(info, "Secure")
        return [{"id": action, "label": label, "target_type": target_type, "enabled": enabled, "requires_review": True,
                 "reversible": False, "reason": reason} for action, label, target_type, enabled, reason in (
                    ("wallet.collection.create", "Create wallet collection", "wallet_collection", wallet and secure, "Requires Wallet and Secure use privileges; both resource names must already exist. Collection creation uses PUT without a server-side create-only lock."),
                    ("wallet.secret.create", "Create write-only secret", "wallet_secret", wallet, "KeyValue HTTP configuration only, explicit hosts and TLS required; existing collection resources must match."),
                    ("wallet.secret.update", "Replace write-only secret", "wallet_secret", wallet, "Existing KeyValue metadata and collection resources must match. Prior values cannot be read back or restored by this app."),
                    ("wallet.secret.delete", "Remove wallet secret", "wallet_secret", wallet, "Existing KeyValue metadata and collection resources must match. Removal cannot be undone by this app."))]

    def _error(self, code, state, message, response=None):
        result = {"ok": False, "state": state, "message": message}
        if response is not None:
            result["upstream"] = public(response)
        return code, result

    def _mutation_result(self, action, safe_target, before, response):
        result = {"ok": response.get("state") == "ok", "action": action, "target": safe_target, "before": before,
                  "upstream": public(response), "verification": None, "value_verified": False}
        if response.get("state") != "ok":
            denied = response.get("state") in ("unauthorized", "forbidden", "not_found")
            result.update(state="rejected" if denied else "outcome_unknown", message="IRIS rejected the command." if denied else "The outcome is unknown. Inspect metadata before retrying; no automatic retry occurred. Secret values are never returned.")
        return result

    def action(self, action, target):
        if not isinstance(action, str) or not isinstance(target, dict):
            return self._error(400, "invalid_input", ERRORS["invalid_input"])
        definitions = {item["id"]: item for item in self.action_definitions(self._info())}
        if action not in definitions or action == "security.tls.set_enabled":
            return self._error(400, "unsupported", ERRORS["unsupported"])
        if not definitions[action]["enabled"]:
            return self._error(403, "forbidden", ERRORS["forbidden"])
        if action == "wallet.collection.create":
            return self._create_collection(target)
        delete = action == "wallet.secret.delete"
        keys = {"collection", "name", "edit_resource", "use_resource", "expected_type"}
        if not delete:
            keys |= {"type", "config"}
        if set(target) != keys or not component(target.get("collection")) or not component(target.get("name")) or not all(resource_permission(target.get(key)) for key in ("edit_resource", "use_resource")):
            return self._error(400, "invalid_input", ERRORS["invalid_input"])
        creating = action == "wallet.secret.create"
        if target["expected_type"] != (None if creating else KEY_VALUE) or (not delete and (target["type"] != KEY_VALUE or not config_valid(target["config"]))):
            return self._error(400, "invalid_input", ERRORS["invalid_input"])
        response, collection = self._collection(target["collection"])
        if collection is None:
            return self._error(409, "target_unverified", "Collection metadata could not be verified; no command was sent.", response)
        if collection["EditResource"] != target["edit_resource"] or collection["UseResource"] != target["use_resource"]:
            return self._error(409, "target_changed", "Collection resources changed. Refresh and review again; no command was sent.")
        response, rows = self._secret_list(target["collection"])
        if rows is None:
            return self._error(409, "target_unverified", "Secret metadata could not be verified; no command was sent.", response)
        found = next((row for row in rows if row["Name"] == target["name"]), None)
        if creating and (found is not None or len(rows) >= ROW_LIMIT):
            return self._error(409, "target_unverified", "The secret name is present or the bounded list cannot establish absence; no command was sent.")
        if not creating and (found is None or found["Type"] != target["expected_type"]):
            return self._error(409, "target_changed", "Secret name/type changed or could not be verified; no command was sent.")
        safe_target = {key: target[key] for key in ("collection", "name", "edit_resource", "use_resource", "expected_type")}
        before = {"exists": found is not None, "type": found["Type"] if found else None}
        route_name = target["collection"] + "." + target["name"]
        payload = None if delete else {"Type": KEY_VALUE, "WalletSecretConfig": target["config"]}
        response = self._fetch("DELETE" if delete else "PUT", "/v2/wallet/secret", {"name": route_name}, payload)
        answer = self._mutation_result(action, safe_target, before, response)
        if not answer["ok"]:
            return 502, answer
        after, rows = self._secret_list(target["collection"])
        current = next((row for row in rows if row["Name"] == target["name"]), None) if rows is not None else None
        verified = rows is not None and ((current is None and len(rows) < ROW_LIMIT) if delete else (current is not None and current["Type"] == KEY_VALUE))
        answer["verification"] = self._resource("wallet_secrets", target["collection"], after, [current] if current else [] if rows is not None else None)
        answer.update(state="verified" if verified and delete else "accepted_metadata_verified" if verified else "accepted_unverified",
                      message="The secret name is absent from the bounded metadata readback." if verified and delete else "IRIS accepted the write and name/type metadata was read back. The secret value is write-only and was not read back." if verified else "IRIS accepted the command, but resulting metadata could not be verified. Refresh before another command.")
        return 200, answer

    def _create_collection(self, target):
        if set(target) != {"name", "edit_resource", "use_resource", "expected_absent"} or not component(target.get("name")) or target.get("expected_absent") is not True or not all(resource_permission(target.get(key)) for key in ("edit_resource", "use_resource")):
            return self._error(400, "invalid_input", ERRORS["invalid_input"])
        before, collection = self._collection(target["name"])
        if before.get("state") != "not_found" or before.get("http_status") != 404:
            return self._error(409, "target_unverified", "Collection absence could not be established; no command was sent.", before)
        for resource_name in sorted({target[key].split(":", 1)[0] for key in ("edit_resource", "use_resource")}):
            existing = self._fetch("GET", "/v2/security/resource", {"name": resource_name})
            raw = (existing.get("payload") or {}).get("result") if existing.get("state") == "ok" else None
            if not isinstance(raw, dict):
                return self._error(409, "resource_unverified", "A referenced security resource could not be verified; no command was sent.", existing)
        payload = {"EditResource": target["edit_resource"], "UseResource": target["use_resource"]}
        response = self._fetch("PUT", "/v2/wallet/collection", {"name": target["name"]}, payload)
        answer = self._mutation_result("wallet.collection.create", dict(target), {"exists": False}, response)
        if not answer["ok"]:
            return 502, answer
        after, collection = self._collection(target["name"])
        verified = collection is not None and all(collection[field] == payload[field] for field in payload)
        answer["verification"] = self._resource("wallet_collection", target["name"], after, collection)
        answer.update(state="verified" if verified else "accepted_unverified", message="Collection resource metadata was read back. A separate administrator can still make concurrent changes." if verified else "IRIS accepted creation, but resource metadata could not be verified. Refresh before another command.")
        return 200, answer
