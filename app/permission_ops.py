"""Reviewed, bounded IRIS permission operations; no credentials or user writes.

The gateway owns HTTP/CSRF protection and upstream transport. IRIS 2026.2 live
checks confirmed Resources-only role updates preserve the other role fields.
Resource creation remains disabled: that build rejected empty public grants.
"""
import re
import threading


READ_PATHS = {"/v2/security/role", "/v2/security/user", "/v2/security/resource",
              "/v2/security/resources"}
WRITE_ROUTES = {("PUT", "/v2/security/role"), ("PUT", "/v2/security/resource")}
ROLE_RESOURCE_UPDATES_VERIFIED = True
RESOURCE_CREATION_VERIFIED = False
MAX_RESOURCES = 40
INVENTORY_LIMIT = 100
KINDS = ("role", "user", "resource")
PERMISSION_ORDER = "RWU"


def valid_inspect_name(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z_%][A-Za-z0-9_.% -]{0,127}", value)) and value == value.strip()


def safe_mutation_name(value):
    return (isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", value))
            and not value.lower().startswith(("admin", "system", "root", "superuser"))
            and value.lower() not in {"all", "default", "public", "operator", "manager", "developer"})


def normalize_resources(value):
    """Strict user resource rows, deterministic ordering, no duplicate grants."""
    if not isinstance(value, list) or len(value) > MAX_RESOURCES:
        raise ValueError("At most 40 resource grants are permitted.")
    result, names = [], set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"Name", "Permissions"} or not safe_mutation_name(item["Name"]):
            raise ValueError("Only named user-defined resources can be changed.")
        permissions = item["Permissions"]
        if not isinstance(permissions, str) or not permissions or len(permissions) > 3 or set(permissions) - set(PERMISSION_ORDER) or len(set(permissions)) != len(permissions):
            raise ValueError("Permissions must contain distinct R, W or U letters.")
        key = item["Name"].casefold()
        if key in names:
            raise ValueError("Duplicate resource name.")
        names.add(key)
        result.append({"Name": item["Name"], "Permissions": "".join(p for p in PERMISSION_ORDER if p in permissions)})
    return sorted(result, key=lambda row: row["Name"].casefold())


def valid_description(value):
    return (isinstance(value, str) and 1 <= len(value.strip()) <= 240 and value == value.strip()
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def valid_resource_filter(value):
    if not isinstance(value, str):
        return False
    names = value.split(",")
    return (1 <= len(names) <= 2 * MAX_RESOURCES and all(safe_mutation_name(name) for name in names)
            and len({name.casefold() for name in names}) == len(names))


def validate_request(method, path, query=None, body=None):
    """Transport allowlist; accepting a route does not bypass action guards."""
    if not isinstance(query, dict):
        return False
    if method == "GET":
        if body is not None:
            return False
        if path == "/v2/security/resources":
            return (set(query) in ({"maxRows"}, {"names", "maxRows"}) and type(query["maxRows"]) is int
                    and 1 <= query["maxRows"] <= INVENTORY_LIMIT
                    and ("names" not in query or valid_resource_filter(query["names"])))
        return path in {"/v2/security/" + kind for kind in KINDS} and set(query) == {"name"} and valid_inspect_name(query["name"])
    if method != "PUT" or path not in {"/v2/security/role", "/v2/security/resource"} or set(query) != {"name"} or not safe_mutation_name(query["name"]) or not isinstance(body, dict):
        return False
    if path == "/v2/security/resource":
        return set(body) == {"Description", "PublicPermission"} and valid_description(body["Description"]) and body["PublicPermission"] == ""
    if set(body) != {"Resources"}:
        return False
    try:
        normalize_resources(body["Resources"])
    except ValueError:
        return False
    return True


def public_result(response):
    # Do not trust a transport's error text: an adapter may include an IRIS
    # diagnostic. Only a stable code/status is exposed from failed responses.
    state = response.get("state", "invalid_response")
    return {"state": state, "http_status": response.get("http_status"),
            "error": None if state == "ok" else {"code": state, "message": "IRIS permission operation is unavailable; diagnostic detail withheld."}}


def detail_payload(response):
    if response.get("state") != "ok":
        return None
    payload = response.get("payload")
    detail = payload.get("result") if isinstance(payload, dict) else None
    return detail if isinstance(detail, dict) else None


class PermissionOps:
    def __init__(self, client, info_callback):
        self.client = client
        self.info_callback = info_callback
        self.lock = threading.Lock()

    @staticmethod
    def can_secure(info):
        return (isinstance(info, dict) and info.get("state") == "ok"
                and (info.get("data") or {}).get("privileges", {}).get("Secure", {}).get("use") is True)

    def action_definitions(self, info):
        can_secure = self.can_secure(info)
        return [
            {"id": "role.set_resources", "label": "Update role resource grants", "target_type": "role",
             "enabled": can_secure and ROLE_RESOURCE_UPDATES_VERIFIED, "requires_review": True, "reversible": True,
             "reason": "Existing user roles and user resources only; no inherited roles or system grants. Fresh state and readback checks do not hold an external concurrency lock." if can_secure and ROLE_RESOURCE_UPDATES_VERIFIED else "Requires live %Admin_Secure:U and a verified Resources-only update implementation."},
            {"id": "resource.create", "label": "Create private resource", "target_type": "resource",
             "enabled": can_secure and RESOURCE_CREATION_VERIFIED, "requires_review": True, "reversible": False,
             "reason": "Creates a new user resource without public permissions. No atomic create-if-absent guard is exposed; other administrators must not concurrently create the same name. Deletion is not exposed." if can_secure and RESOURCE_CREATION_VERIFIED else "Disabled: tested IRIS 2026.2 rejects empty public permissions during resource creation; no public-grant workaround is enabled."},
        ]

    def _project(self, kind, name, detail):
        result = {"Name": self.client.clean(name)}
        fields = {"role": ("Description", "GrantedRoles", "EscalationOnly"),
                  "user": ("Enabled", "NameSpace", "Roles", "EscalationRoles", "AccountNeverExpires", "ExpirationDate"),
                  "resource": ("Description", "PublicPermission")}[kind]
        for field in fields:
            if field in detail:
                result[field] = self.client.clean(detail[field])
        if kind == "role":
            rows = detail.get("Resources")
            result["Resources"] = [{"Name": self.client.clean(row.get("Name")), "Permissions": self.client.clean(row.get("Permissions"))}
                                   for row in rows[:INVENTORY_LIMIT] if isinstance(row, dict)] if isinstance(rows, list) else None
            result["editable"] = self._editable_role(name, detail)
            result["resource_limit"] = MAX_RESOURCES
            result["resources_truncated"] = isinstance(rows, list) and len(rows) > INVENTORY_LIMIT
        return result

    def _resource_result(self, kind, name, response):
        result = {"key": kind + "_detail", "label": kind.title() + " details", "method": "GET",
                  "path": "/api/admin/v2/security/" + kind, **public_result(response),
                  "count": 0, "data": None, "sample_limit": None}
        if response.get("state") == "ok":
            detail = detail_payload(response)
            if detail is None:
                result.update(state="invalid_response", error={"code": "invalid_response", "message": "IRIS returned no permission detail object."})
            else:
                result.update(count=1, data=self._project(kind, name, detail))
        return result

    def inspect(self, kind, name):
        if kind not in KINDS or not valid_inspect_name(name):
            raise ValueError("A valid role, user or resource name is required.")
        response = self.client.fetch("GET", "/v2/security/" + kind, {"name": name})
        return self._resource_result(kind, name, response)

    @staticmethod
    def _editable_role(name, detail):
        if not safe_mutation_name(name) or detail.get("EscalationOnly") is not False or detail.get("GrantedRoles") != []:
            return False
        try:
            normalize_resources(detail.get("Resources"))
        except ValueError:
            return False
        return True

    @staticmethod
    def _reject(state, message, code=400):
        return code, {"ok": False, "state": state, "message": message, "verification": None}

    def action(self, action, target):
        if action not in ("role.set_resources", "resource.create"):
            return self._reject("unsupported_action", "This permission action is not exposed.")
        if not isinstance(target, dict):
            return self._reject("invalid_target", "A permission target object is required.")
        with self.lock:
            if not next(item for item in self.action_definitions(self.info_callback()) if item["id"] == action)["enabled"]:
                return self._reject("forbidden", "The live privilege and verified implementation checks did not permit this action.", 403)
            if action == "role.set_resources":
                return self._set_resources(target)
            return self._create_resource(target)

    def _set_resources(self, target):
        if set(target) != {"name", "resources", "expected_resources"} or not safe_mutation_name(target.get("name")):
            return self._reject("invalid_target", "A safe user role name and exact resources/expected_resources arrays are required.")
        name = target["name"]
        try:
            desired = normalize_resources(target["resources"])
            expected = normalize_resources(target["expected_resources"])
        except ValueError as error:
            return self._reject("invalid_target", str(error))
        if desired == expected:
            return self._reject("no_change", "The requested resource grants match the reviewed state.")
        before_response = self.client.fetch("GET", "/v2/security/role", {"name": name})
        before = detail_payload(before_response)
        if before is None or not self._editable_role(name, before):
            return self._reject("target_unverified", "Only an existing non-escalation user role without inherited roles or system resource grants can be changed.", 409)
        if normalize_resources(before["Resources"]) != expected:
            return self._reject("target_changed", "Role resource grants changed. Refresh and review again; no update was sent.", 409)
        names = sorted({row["Name"] for row in desired + expected}, key=str.casefold)
        name_filter = ",".join(names)
        if not valid_resource_filter(name_filter):
            return self._reject("invalid_target", "Use consistent resource name casing across the current and desired grants.")
        resources = self.client.fetch("GET", "/v2/security/resources", {"names": name_filter, "maxRows": INVENTORY_LIMIT})
        payload = resources.get("payload") if resources.get("state") == "ok" else None
        rows = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return self._reject("resources_unverified", "The bounded resource inventory could not be verified; no update was sent.", 409)
        for grant in desired + expected:
            matches = [row for row in rows[:INVENTORY_LIMIT] if isinstance(row, dict) and row.get("Name") == grant["Name"]]
            if len(matches) != 1 or matches[0].get("ResourceType") != "Application" or matches[0].get("AllowDelete") is not True:
                return self._reject("resource_not_permitted", "Every changed grant must name an existing application resource in the exact-name inventory.", 409)
        response = self.client.fetch("PUT", "/v2/security/role", {"name": name}, {"Resources": desired})
        answer = {"ok": response.get("state") == "ok", "action": "role.set_resources", "target": {"name": name, "resources": desired},
                  "before": self._project("role", name, before), "upstream": public_result(response), "verification": None}
        if response.get("state") != "ok":
            return self._failed_update(answer, response)
        after_response = self.client.fetch("GET", "/v2/security/role", {"name": name})
        after = detail_payload(after_response)
        same_fields = isinstance(after, dict) and {k: v for k, v in before.items() if k != "Resources"} == {k: v for k, v in after.items() if k != "Resources"}
        try:
            grants_match = isinstance(after, dict) and normalize_resources(after.get("Resources")) == desired
        except ValueError:
            grants_match = False
        answer["verification"] = self._resource_result("role", name, after_response)
        answer["verification"]["other_fields_unchanged"] = same_fields
        verified = same_fields and grants_match
        answer.update(state="verified" if verified else "accepted_unverified",
                      message="Resource grants were read back and other role fields match the pre-update read. No external concurrency lock was held." if verified else "IRIS accepted the update, but resulting grants or unchanged role fields could not be verified. Inspect before any retry; no rollback occurred.")
        return 200, answer

    def _create_resource(self, target):
        if set(target) != {"name", "description"} or not safe_mutation_name(target.get("name")):
            return self._reject("invalid_target", "A safe new resource name and description are required.")
        name, description = target["name"], target["description"]
        if not valid_description(description):
            return self._reject("invalid_target", "Description must be 1–240 printable characters without surrounding whitespace.")
        before = self.client.fetch("GET", "/v2/security/resource", {"name": name})
        if before.get("state") != "not_found" or before.get("http_status") != 404:
            return self._reject("target_exists_or_unverified", "The resource name must be confirmed absent with HTTP 404; no update was sent.", 409)
        response = self.client.fetch("PUT", "/v2/security/resource", {"name": name}, {"Description": description, "PublicPermission": ""})
        answer = {"ok": response.get("state") == "ok", "action": "resource.create", "target": {"name": name},
                  "before": {"Name": self.client.clean(name), "state": "not_found"}, "upstream": public_result(response), "verification": None}
        if response.get("state") != "ok":
            return self._failed_update(answer, response)
        after_response = self.client.fetch("GET", "/v2/security/resource", {"name": name})
        after = detail_payload(after_response)
        answer["verification"] = self._resource_result("resource", name, after_response)
        verified = response.get("http_status") == 201 and isinstance(after, dict) and after.get("Description") == description and after.get("PublicPermission") == ""
        answer.update(state="verified" if verified else "accepted_unverified",
                      message="IRIS reported creation and the resource was read back without public permissions." if verified else "IRIS accepted the request, but a new resource and its private state could not be verified. Inspect before any retry.")
        return 200, answer

    @staticmethod
    def _failed_update(answer, response):
        rejected = response.get("state") in ("unauthorized", "forbidden", "not_found")
        answer.update(state="rejected" if rejected else "outcome_unknown", message="IRIS rejected the permission request." if rejected else "The permission outcome is unknown. Inspect current state before retrying; no automatic retry occurred.")
        return 502, answer
