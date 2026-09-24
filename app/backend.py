#!/usr/bin/env python3
"""Local IRIS Fieldwork gateway. Python standard library; no runtime-spec dependency.

IRIS_BASE_URL defaults to http://127.0.0.1:52773. Credentials stay in
IRIS_USERNAME/IRIS_PASSWORD or IRIS_BEARER_TOKEN. Serve on 127.0.0.1:8766.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import ssl
import threading
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import permission_ops
import security_ops
import log_ops

VERSION = "0.2.0"
SOURCE = {"repository": "https://github.com/intersystems-community/sysadmin-api-specification",
          "commit": "f764aea427e5c0b1dd08a4c18a0457e0ff7b3b34"}
PREFIX = "/api/admin"
ROW_LIMIT = 100
BODY_LIMIT = 1024 * 1024
SECTIONS = ("web", "permissions", "security", "tasks", "system", "logs")
TASK_ACTIONS = ("task.suspend", "task.resume", "task.run")
PROTECTED_WEB_PREFIXES = ("/api", "/csp/sys", "/csp/bin", "/isc", "/fieldwork/runtime")


@dataclass(frozen=True)
class Resource:
    key: str
    label: str
    path: str
    privilege: str
    fields: tuple
    bounded: bool = True


def resource(key, label, path, privilege, fields, bounded=True):
    return Resource(key, label, path, privilege, tuple(fields.split()), bounded)


TASKS = resource("tasks", "Scheduled tasks", "/v2/tasks", "%Admin_Operate:U or %Admin_Task:U",
                 "Id Name Type Namespace TaskClass Suspended LastFinished NextScheduled")
TASK_STATES = resource("task_states", "Task state verification", "/fieldwork/runtime/task-states", "%Admin_Operate:U",
                       "Id Name Namespace TaskClass Suspended TimePeriod", False)
HISTORY = resource("task_history", "Task activity history", "/v2/task/history", "%Admin_Operate:U",
                   "TaskId Name Namespace Pid LastStart Completed LogDatetime ErrDate ErrNumber Status Result")
RESOURCES = {
    "web": (resource("web_apps", "Web applications", "/v2/web-apps", "%Admin_Secure:U",
                     "Name Namespace NamespaceDefault Enabled Type Resource AuthenticationMethods IsSystemApp DispatchClass"),),
    "permissions": (
        resource("roles", "Roles", "/v2/security/roles", "%Admin_Secure:U", "Name EscalationOnly"),
        resource("users", "Users", "/v2/security/users", "%Admin_Secure:U", "Name Enabled Type Namespace"),
        resource("resources", "Security resources", "/v2/security/resources", "%Admin_Secure:U", "Name PublicPermission ResourceType AllowDelete")),
    "security": (
        resource("wallet_collections", "Wallet collections (metadata)", "/v2/wallet/collections", "%Admin_Wallet:U", "Name EditResource UseResource"),
        resource("x509_credentials", "X.509 credentials (metadata)", "/v2/security/x509-credentials", "%Admin_Secure:U", "Alias HasPrivateKey"),
        resource("ssl_configurations", "TLS configurations", "/v2/security/ssl-configurations", "%Admin_Secure:U", "Name Enabled Type"),
        resource("oauth_servers", "OAuth server definitions", "/v2/security/oauth2/client/server-definitions", "%Admin_OAuth2_Client:U", "ID ClientCount ResourceCount"),
        resource("oauth_clients", "OAuth clients (metadata)", "/v2/security/oauth2/server/clients", "%Admin_OAuth2_Registration:U", "Name ClientId ClientType")),
    "tasks": (TASKS, TASK_STATES, resource("task_manager", "Task manager", "/v2/task/manager", "%Admin_Operate:U or %Admin_Task:U", "Status", False),
              resource("upcoming", "Upcoming tasks", "/v2/task/upcoming", "%Admin_Operate:U", "Id Name Namespace Datetime Suspended"), HISTORY),
    "system": (
        resource("runtime_metrics", "Runtime host metrics", "/fieldwork/runtime/metrics", "%Admin_Operate:U", "sampledAt scope availability cpuBusyPercent cpuSampleMilliseconds memoryTotalBytes memoryAvailableBytes irisDiskTotalBytes irisDiskAvailableBytes containerMemoryLimitBytes containerMemoryUsedBytes containerCpuLimitCores", False),
        resource("processes", "IRIS processes", "/v2/processes", "%Admin_Operate:U", "Job Pid Nspace Routine State Commands Globals CPUTime ParentPid ElapsedTime CanBeExamined CanBeSuspended CanBeTerminated"),
        resource("devices", "Devices", "/v2/devices", "%Admin_Manage:U", "Name Type SubType Alias"),
        resource("databases", "Local databases", "/v2/database-dirs", "%Admin_Manage:U or %Admin_Operate:U", "Directory MaxSize Size Status Resource Encrypted Mirrored SFN"),
        resource("system_usage", "IRIS usage counters", "/v2/monitor/system-usage", "%Admin_Operate:U", "AllGlobalReferences GlobalUpdateReferences RoutineCalls RoutineBufferLoadsAndSaves LogicalBlockRequests BlockReads BlockWrites WIJwrites JournalEntries JournalBlockWrites RoutineLines LastUpdate", False),
        resource("shared_memory", "Shared memory", "/v2/monitor/system-usage/shared-memory", "%Admin_Operate:U", "SMHAllocated SMHAvailable SMHUsed SMTUsed GSTUsed AllUsed", False)),
    "logs": (resource("runtime_logs", "Runtime log sources", "/fieldwork/runtime/logs", "%Admin_Operate:U", "source scope truncated state", False), HISTORY,
        resource("journal_files", "Journal file inventory", "/v2/journal/files", "%Admin_Operate:U", "Name Size CreationTime DataSize"),
        resource("audit_events", "Audit event definitions and counters", "/v2/security/audit/events", "%Admin_Secure:U", "EventName Enabled Total Written Lost")),
}
READ_PATHS = {r.path for rs in RESOURCES.values() for r in rs} | {"/info", "/v2/web-app"}
LIMITATIONS = {
    "web": ["Explorer describes the curated admin API; discovery of other applications' OpenAPI documents is not implemented.",
            "The Enabled-only update preserved other fields in a disposable IRIS 2026.2 test. A fresh state check and readback detect changes; no server-side lock prevents another administrator changing the app concurrently.",
            "Core API, gateway and system applications cannot be toggled."],
    "permissions": ["Reviewed resource grants can be changed on existing non-system roles without inherited roles. Only verified application resources are permitted.",
                    "Resource creation is unavailable on the tested IRIS 2026.2 build because its API rejects an empty public-permission value. User account writes are not exposed."],
    "security": ["Wallet collection creation and write-only KeyValue secret management use fresh metadata checks. Secret values and private keys are never returned.",
                 "X.509, TLS and OAuth configuration details are inspected without changing key material or authentication settings."],
    "tasks": ["Commands apply only to listed user-defined tasks. Running a task can cause effects that cannot be undone.",
              "The Fieldwork adapter verifies suspension from %SYS.Task because the tested IRIS 2026.2 task list reported a stale suspension state. Identity-matched values are retained alongside the API report; unverified states disable commands.",
              "A historical PID match does not prove process identity because operating systems reuse PIDs."],
    "system": ["The optional Fieldwork adapter reports the runtime host/container scope declared in each sample. Process controls are not exposed."],
    "logs": ["Use Search audit or a journal file's record search to read bounded record metadata.",
             "The optional Fieldwork adapter provides bounded runtime log sources; this is not complete coverage of every subsystem. Missing adapter routes remain visible.",
             "Audit and journal searches queue a read operation through the upstream async API. Record data and secret-bearing payload fields are withheld."],
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upstream_path(path):
    return path if path.startswith("/fieldwork/runtime/") else PREFIX + path


def permitted_web_name(value):
    if not isinstance(value, str) or not 2 <= len(value) <= 240 or not re.fullmatch(r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", value):
        return False
    if any(part in (".", "..") for part in value.split("/")):
        return False
    name = value.lower()
    return not any(name == protected or name.startswith(protected + "/") or protected.startswith(name + "/") for protected in PROTECTED_WEB_PREFIXES)


def loopback_target(value):
    if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError("Invalid IRIS loopback URL")
    try:
        u = urlsplit(value)
        host, port = u.hostname, u.port
    except ValueError:
        raise ValueError("Invalid IRIS loopback URL") from None
    if u.scheme not in ("http", "https") or not host or u.username is not None or u.password is not None:
        raise ValueError("IRIS URL must be an HTTP(S) loopback origin without credentials")
    if u.path not in ("", "/", PREFIX, PREFIX + "/") or u.query or u.fragment or "%" in host:
        raise ValueError("IRIS URL has an unsupported path or component")
    host = "127.0.0.1" if host.lower() == "localhost" else host
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("IRIS host must be a literal loopback address or localhost") from None
    if not address.is_loopback or (port is not None and not 1 <= port <= 65535):
        raise ValueError("IRIS host must be loopback with a valid port")
    return u.scheme, str(address), port or (443 if u.scheme == "https" else 80)


def credentials(env):
    user, password, token = (env.get(k) for k in ("IRIS_USERNAME", "IRIS_PASSWORD", "IRIS_BEARER_TOKEN"))
    if token is not None:
        if user is not None or password is not None or not token or not token.isascii() or any(ord(c) < 33 or ord(c) == 127 for c in token):
            raise ValueError("Set only a valid IRIS_BEARER_TOKEN or a username/password pair")
        return "Bearer " + token, (token,)
    if not user or not password or ":" in user or any(ord(c) < 32 or ord(c) == 127 for c in user + password):
        raise ValueError("Set valid IRIS_USERNAME and IRIS_PASSWORD environment variables")
    encoded = base64.b64encode((user + ":" + password).encode()).decode("ascii")
    return "Basic " + encoded, (user, password, encoded)


ERROR_MESSAGES = {
    "unauthorized": "IRIS rejected authentication (401).",
    "forbidden": "IRIS denied the required privilege (403).",
    "not_found": "IRIS did not expose this route or target (404).",
    "unavailable": "IRIS could not be reached or the connection timed out.",
    "tls_error": "IRIS TLS verification or negotiation failed.",
    "redirect_refused": "An upstream redirect was refused.",
    "invalid_response": "IRIS returned an unexpected response format.",
    "response_too_large": "IRIS response exceeded the gateway's body limit.",
    "http_error": "IRIS returned an unsuccessful HTTP status.",
    "application_error": "IRIS reported an application error; sensitive detail was withheld.",
    "configuration_error": "IRIS connection credentials are not configured correctly.",
}


def failure(state, status=None):
    return {"state": state, "http_status": status, "payload": None,
            "error": {"code": state, "message": ERROR_MESSAGES.get(state, "Operation unavailable.")}}


class IRISClient:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.authorization = None
        self.sensitive = ()
        self.target = None
        try:
            self.target = loopback_target(env.get("IRIS_BASE_URL", "http://127.0.0.1:52773"))
            self.authorization, self.sensitive = credentials(env)
        except ValueError:
            pass  # UI can start without credentials, with a visible configuration error.

    def clean(self, value):
        if isinstance(value, str):
            value = re.sub(r"[\x00-\x1f\x7f]", " ", value)[:512]
            for sensitive in self.sensitive:
                value = value.replace(sensitive, "[redacted]")
            return value
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        if isinstance(value, list):
            return [self.clean(v) for v in value[:50] if v is None or isinstance(v, (str, bool, int, float))]
        return None

    def clean_log(self, value):
        if not isinstance(value, str):
            return "[non-text record withheld]"
        value = self.clean(value)
        if "PRIVATE KEY" in value.upper():
            return "[key material withheld]"
        if re.search(r'''(?i)\b(?:authorization|proxy-authorization|password|passwd|pwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|api[_-]?key)\s*["']?\s*[:=]''', value):
            return "[sensitive record withheld]"
        value = re.sub(r"(?i)(https?://)[^/\s@]+@", r"\1[redacted]@", value)
        value = re.sub(r"[A-Za-z0-9+/=_-]{48,}", "[long token withheld]", value)
        return value

    def fetch(self, method, path, query=None, body=None):
        query = query or {}
        curated = any(module.validate_request(method, path, query, body) for module in (permission_ops, security_ops, log_ops))
        if curated:
            pass
        elif method == "GET":
            if path not in READ_PATHS or body is not None:
                raise ValueError("Read operation is not allowlisted")
            if path == "/v2/web-app":
                if set(query) != {"name"} or not permitted_web_name(query["name"]):
                    raise ValueError("Web target is not allowlisted")
            elif set(query) - {"maxRows"}:
                raise ValueError("Read query is not allowlisted")
            if "maxRows" in query and (type(query["maxRows"]) is not int or not 1 <= query["maxRows"] <= ROW_LIMIT):
                raise ValueError("Invalid row limit")
        elif method == "POST":
            if path not in {"/v2/task/" + a.split(".")[1] for a in TASK_ACTIONS} or set(query) != {"id"} or type(query["id"]) is not int or not 1 <= query["id"] <= 2147483647:
                raise ValueError("Mutation is not allowlisted")
            expected = {"/v2/task/run": {"RunNow": True}, "/v2/task/suspend": {"LeaveInQueue": True}, "/v2/task/resume": None}[path]
            if body != expected:
                raise ValueError("Mutation body is not allowlisted")
        elif method == "PUT":
            if path != "/v2/web-app" or set(query) != {"name"} or not permitted_web_name(query["name"]) or not isinstance(body, dict) or set(body) != {"Enabled"} or type(body["Enabled"]) is not bool:
                raise ValueError("Web mutation is not allowlisted")
        else:
            raise ValueError("HTTP method is not allowlisted")
        if self.target is None or self.authorization is None:
            return failure("configuration_error")
        scheme, host, port = self.target
        conn = None
        status = None
        try:
            cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
            conn = cls(host, port, timeout=3)
            route = upstream_path(path) + ("?" + urlencode(query) if query else "")
            headers = {"Authorization": self.authorization, "Accept": "application/json", "Accept-Encoding": "identity", "Connection": "close"}
            raw_body = None
            if body is not None:
                raw_body = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
            conn.request(method, route, body=raw_body, headers=headers)
            response = conn.getresponse()
            status = response.status
            if status in (401, 403, 404):
                return failure({401: "unauthorized", 403: "forbidden", 404: "not_found"}[status], status)
            if 300 <= status < 400:
                return failure("redirect_refused", status)
            if not 200 <= status < 300:
                return failure("http_error", status)
            mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if mime != "application/json" and not mime.endswith("+json"):
                return failure("invalid_response", status)
            if (response.getheader("Content-Encoding") or "identity").lower() != "identity":
                return failure("invalid_response", status)
            raw = response.read(BODY_LIMIT + 1)
            if len(raw) > BODY_LIMIT:
                return failure("response_too_large", status)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return failure("invalid_response", status)
            envelope = payload.get("status")
            errors = (envelope.get("Errors") or envelope.get("errors")) if isinstance(envelope, dict) else None
            if errors:
                return failure("application_error", status)
            if method != "GET":
                error_keys = [key for key in ("Errors", "errors") if isinstance(envelope, dict) and key in envelope]
                if not error_keys or any(not isinstance(envelope[key], list) for key in error_keys):
                    return failure("invalid_response", status)
            if path == "/info":
                if isinstance(payload.get("result"), dict):
                    payload = payload["result"]
                if not {"apiVersion", "serverVersion"}.issubset(payload):
                    return failure("invalid_response", status)
            elif method == "GET" and "result" not in payload:
                return failure("invalid_response", status)
            result = {"state": "ok", "http_status": status, "payload": payload, "error": None}
            if status == 202 and (method, path) in log_ops.WRITE_ROUTES:
                location = urlsplit(response.getheader("Location") or "")
                params = parse_qs(location.query, strict_parsing=True, keep_blank_values=True, max_num_fields=2)
                if location.scheme or location.netloc or location.fragment or location.path not in (PREFIX + "/v1/async-result", PREFIX + "/v2/async-result") or set(params) != {"id"} or len(params["id"]) != 1 or not log_ops.valid_id(params["id"][0]):
                    return failure("invalid_response", status)
                # IRIS 2026.2 returns a v1 Location header for its v2 search.
                # Retain only the validated ID; always poll our fixed v2 route.
                result["async_id"] = params["id"][0]
            return result
        except ssl.SSLError:
            return failure("tls_error", status)
        except (OSError, http.client.HTTPException):
            return failure("unavailable", status)
        except (ValueError, UnicodeError, RecursionError):
            return failure("invalid_response", status)
        finally:
            if conn is not None:
                conn.close()


def public_result(result):
    return {key: result[key] for key in ("state", "http_status", "error")}


class Gateway:
    def __init__(self, client=None):
        self.client = client or IRISClient()
        self.csrf_token = secrets.token_urlsafe(32)
        self.action_lock = threading.Lock()
        self.permissions = permission_ops.PermissionOps(self.client, self.info)
        self.security = security_ops.SecurityOps(self.client, self.info)
        self.logs = log_ops.LogOps(self.client, self.info)

    def info(self):
        response = self.client.fetch("GET", "/info")
        result = public_result(response)
        result["data"] = None
        if response["state"] == "ok":
            raw = response["payload"]
            data = {k: self.client.clean(raw[k]) for k in ("apiVersion", "serverVersion", "product", "systemMode") if k in raw}
            privileges = raw.get("privileges", {})
            data["privileges"] = {k: {"use": v.get("use") is True} for k, v in privileges.items()
                                  if k in ("Manage", "Operate", "Secure", "Task", "Wallet", "OAuth2_Client", "OAuth2_Server", "OAuth2_Registration") and isinstance(v, dict)} if isinstance(privileges, dict) else {}
            result["data"] = data
        return result

    def action_definitions(self, info):
        privileges = (info.get("data") or {}).get("privileges", {})
        can_task = info["state"] == "ok" and privileges.get("Task", {}).get("use") is True and privileges.get("Operate", {}).get("use") is True
        can_web = info["state"] == "ok" and (info.get("data") or {}).get("privileges", {}).get("Secure", {}).get("use") is True
        actions = [{"id": a, "label": {"task.suspend": "Suspend task", "task.resume": "Resume task", "task.run": "Run task now"}[a],
                    "target_type": "task", "enabled": can_task, "requires_review": True, "reversible": a != "task.run",
                    "reason": "Only listed user-defined tasks with adapter-verified suspension; running may have irreversible effects." if can_task else "A live connection with %Admin_Task:U and %Admin_Operate:U is required."} for a in TASK_ACTIONS]
        actions.append({"id": "web.set_enabled", "label": "Change web application enabled state", "target_type": "web_app",
                        "enabled": can_web, "requires_review": True, "reversible": True,
                        "reason": "Only verified non-system applications outside protected routes. Changes may interrupt application traffic; no external concurrency lock." if can_web else "A live connection with %Admin_Secure:U is required."})
        return actions + self.permissions.action_definitions(info) + self.security.action_definitions(info)

    def inspect(self, kind, name):
        if kind in permission_ops.KINDS:
            return self.permissions.inspect(kind, name)
        if kind in security_ops.INSPECT:
            return self.security.inspect(kind, name)
        raise ValueError("Unknown inspection kind")

    def status(self):
        info = self.info()
        return {"app": "IRIS Fieldwork", "version": VERSION, "mode": "live", "connected": info["state"] == "ok",
                "csrf_token": self.csrf_token, "upstream": info, "timestamp": now(),
                "capabilities": {"sections": list(SECTIONS), "actions": self.action_definitions(info),
                                 "row_limit": ROW_LIMIT, "logs_adapter": {"enabled": True, "state": "probe_in_logs_section"}}}

    def read_resource(self, item):
        response = self.client.fetch("GET", item.path, {"maxRows": ROW_LIMIT} if item.bounded else None)
        result = {"key": item.key, "label": item.label, "method": "GET", "path": upstream_path(item.path),
                  **public_result(response), "data": None, "count": 0, "sample_limit": ROW_LIMIT if item.bounded else None}
        if response["state"] != "ok":
            return result
        raw = response["payload"].get("result")
        def project(row):
            if not isinstance(row, dict):
                return None
            clean = {k: self.client.clean(row[k]) for k in item.fields if k in row}
            if item.key == "runtime_logs":
                records = row.get("records")
                clean["records"] = [{"line": self.client.clean_log(record.get("line"))} for record in records[:100] if isinstance(record, dict)] if isinstance(records, list) else []
            if item.key == "task_history":
                if "Result" in row:
                    clean["Result"] = self.client.clean_log(row["Result"])
            return clean
        if isinstance(raw, list):
            result["data"] = [project(row) for row in raw[:ROW_LIMIT] if isinstance(row, dict)]
        elif isinstance(raw, dict):
            result["data"] = project(raw)
        else:
            result.update(state="invalid_response", error=failure("invalid_response")["error"])
            return result
        result["count"] = len(result["data"])
        if item.key == "runtime_metrics" and isinstance(raw, dict) and raw.get("availability"):
            result.update(state="partial", error={"code": "partial_telemetry", "message": "The runtime adapter reports incomplete telemetry. Available measurements are retained; inspect availability."},
                          limitations=["Some runtime metrics could not be read on this host."])
        return result

    def section(self, section):
        if section not in RESOURCES:
            raise ValueError("Unknown section")
        with ThreadPoolExecutor(max_workers=4) as pool:
            resources = list(pool.map(self.read_resource, RESOURCES[section]))
        good = sum(r["state"] == "ok" for r in resources)
        targets, actions = [], []
        if section == "tasks":
            self.enrich_task_states(resources[0], resources[1])
            actions = self.action_definitions(self.info())
            permitted = {a["id"] for a in actions if a["enabled"]}
            rows = resources[0]["data"]
            if isinstance(rows, list):
                for row in rows:
                    if row.get("Type") != "User" or type(row.get("Id")) is not int or not 1 <= row["Id"] <= 2147483647:
                        continue
                    choices = ("task.resume",) if row.get("Suspended") is True else ("task.suspend", "task.run") if row.get("Suspended") is False else ()
                    targets.append({"type": "task", "id": row["Id"], "name": row.get("Name", "User task"),
                                    "actions": [a for a in choices if a in permitted]})
        elif section == "web":
            actions = self.action_definitions(self.info())
            permitted = next(a for a in actions if a["id"] == "web.set_enabled")["enabled"]
            rows = resources[0]["data"]
            if isinstance(rows, list):
                for row in rows:
                    if permitted_web_name(row.get("Name")) and row.get("IsSystemApp") is False and row.get("Type") == "CSP" and type(row.get("Enabled")) is bool and isinstance(row.get("Namespace"), str) and row["Namespace"] and row["Namespace"].upper() != "%SYS" and isinstance(row.get("DispatchClass"), str):
                        targets.append({"type": "web_app", "name": row["Name"], "enabled": row["Enabled"], "actions": ["web.set_enabled"] if permitted else []})
        elif section == "permissions":
            actions = self.permissions.action_definitions(self.info())
        elif section == "security":
            actions = self.security.action_definitions(self.info())
        limitations = LIMITATIONS[section] + [note for r in resources for note in r.get("limitations", [])]
        return {"section": section, "state": "ok" if good == len(resources) else "partial" if any(r["state"] in ("ok", "partial") for r in resources) else "unavailable",
                "resources": resources, "targets": targets, "actions": actions, "limitations": limitations, "timestamp": now()}

    def enrich_task_states(self, inventory, states):
        authoritative = states.get("data") if states["state"] == "ok" else None
        rows = inventory.get("data")
        if not isinstance(rows, list):
            return inventory
        for row in rows:
            row["ApiReportedSuspended"] = row.get("Suspended")
            row["Suspended"] = None
            row["StateVerified"] = False
            row["StateVerification"] = "unavailable" if not isinstance(authoritative, list) else "identity_not_matched"
            matches = [state for state in authoritative if type(state.get("Id")) is int and state["Id"] == row.get("Id") and isinstance(state.get("Name"), str) and state["Name"] == row.get("Name") and isinstance(state.get("Namespace"), str) and state["Namespace"] == row.get("Namespace") and ("TaskClass" not in row or row["TaskClass"] == state.get("TaskClass"))] if isinstance(authoritative, list) else []
            if len(matches) == 1 and type(matches[0].get("Suspended")) is bool:
                row["Suspended"] = matches[0]["Suspended"]
                row["StateVerified"] = True
                row["StateMismatch"] = row["ApiReportedSuspended"] is not row["Suspended"]
                row["StateVerification"] = "Fieldwork adapter: %SYS.Task"
        inventory["state_verification"] = public_result(states)
        return inventory

    def task_inventory(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            inventory, states = list(pool.map(self.read_resource, (TASKS, TASK_STATES)))
        return self.enrich_task_states(inventory, states)

    def explorer(self):
        items = []
        for section, resources in RESOURCES.items():
            for item in resources:
                items.append({"id": section + "." + item.key, "section": section, "method": "GET", "path": upstream_path(item.path),
                              "summary": item.label, "privilege": item.privilege, "parameters": [{"name": "maxRows", "required": False, "value": ROW_LIMIT}] if item.bounded else [], "enabled": True})
        for action in TASK_ACTIONS:
            items.append({"id": action, "section": "tasks", "method": "POST", "path": PREFIX + "/v2/task/" + action.split(".")[1],
                          "summary": "Reviewed user-task command through /api/action", "privilege": "%Admin_Task:U",
                          "parameters": [{"name": "id", "required": True, "type": "integer"}], "enabled": False,
                          "reason": "Explorer is read-only. Use the task review controls."})
        items.append({"id": "web.set_enabled", "section": "web", "method": "PUT", "path": PREFIX + "/v2/web-app",
                      "summary": "Reviewed Enabled-only update through /api/action", "privilege": "%Admin_Secure:U",
                      "parameters": [{"name": "name", "required": True, "type": "string"}], "enabled": False,
                      "reason": "Explorer is read-only. Use the web application review controls."})
        return {"source": SOURCE, "items": items, "limitations": ["Curated operation metadata only; no arbitrary request execution or bundled upstream specification is served."]}

    def action(self, body):
        if not isinstance(body, dict) or set(body) != {"action", "target", "reviewed"} or body.get("reviewed") is not True:
            return 400, {"ok": False, "state": "invalid_input", "message": "An exact action, target and reviewed:true body is required."}
        action, target = body["action"], body["target"]
        if action == "web.set_enabled":
            return self.web_action(target)
        if isinstance(action, str) and action in ("role.set_resources", "resource.create"):
            with self.action_lock:
                return self.permissions.action(action, target)
        if isinstance(action, str) and action.startswith("wallet."):
            with self.action_lock:
                return self.security.action(action, target)
        if not isinstance(action, str) or action not in TASK_ACTIONS:
            return 400, {"ok": False, "state": "unsupported_action", "message": "This management action is not enabled."}
        if not isinstance(target, dict) or set(target) != {"id"} or type(target["id"]) is not int or not 1 <= target["id"] <= 2147483647:
            return 400, {"ok": False, "state": "invalid_target", "message": "A positive integer task id is required."}
        with self.action_lock:
            info = self.info()
            if not next(a for a in self.action_definitions(info) if a["id"] == action)["enabled"]:
                return 403, {"ok": False, "action": action, "target": target, "state": "forbidden", "message": "A live %Admin_Task:U capability check is required.", "upstream": public_result(info), "verification": None}
            before = self.task_inventory()
            rows = before.get("data")
            task = next((r for r in rows if r.get("Id") == target["id"]), None) if isinstance(rows, list) else None
            if before["state"] != "ok" or task is None:
                return 409, {"ok": False, "state": "target_unverified", "message": "The task is not in the current bounded task list; no command was sent.", "verification": before}
            if task.get("Type") != "User" or type(task.get("Suspended")) is not bool:
                return 403, {"ok": False, "state": "target_not_permitted", "message": "Only verified user-defined tasks with known suspension state can be changed."}
            if (action == "task.resume" and not task["Suspended"]) or (action != "task.resume" and task["Suspended"]):
                return 409, {"ok": False, "state": "target_changed", "message": "Task state does not match this action. Refresh and review again."}
            request_body = {"task.run": {"RunNow": True}, "task.suspend": {"LeaveInQueue": True}, "task.resume": None}[action]
            response = self.client.fetch("POST", "/v2/task/" + action.split(".")[1], {"id": target["id"]}, request_body)
            answer = {"ok": response["state"] == "ok", "action": action, "target": target,
                      "before": {k: task[k] for k in ("Id", "Name", "Suspended", "StateVerification") if k in task},
                      "upstream": public_result(response), "verification": None}
            if response["state"] != "ok":
                uncertain = response["state"] not in ("unauthorized", "forbidden", "not_found")
                answer.update(state="outcome_unknown" if uncertain else "rejected",
                              message="The outcome is unknown. Inspect task state before retrying; no automatic retry occurred." if uncertain else "IRIS did not accept the command.")
                return 502, answer
            verification = self.task_inventory()
            if isinstance(verification["data"], list):
                verification["data"] = [r for r in verification["data"] if r.get("Id") == target["id"]]
                verification["count"] = len(verification["data"])
            answer["verification"] = verification
            current = next((r for r in verification["data"] if r.get("Id") == target["id"]), None) if isinstance(verification["data"], list) else None
            verified = current is not None and current.get("Suspended") is (action == "task.suspend")
            if action == "task.run":
                answer.update(state="accepted", message="IRIS accepted the run request. Task completion and downstream effects are not verified.")
            else:
                answer.update(state="verified" if verified else "accepted_unverified",
                              message="The requested suspension state was read back from IRIS." if verified else "IRIS accepted the request, but the resulting state could not be verified. Refresh before another command.")
            return 200, answer

    def web_action(self, target):
        if not isinstance(target, dict) or set(target) != {"name", "enabled", "expected_enabled"} or not permitted_web_name(target["name"]) or type(target["enabled"]) is not bool or type(target["expected_enabled"]) is not bool or target["enabled"] == target["expected_enabled"]:
            return 400, {"ok": False, "state": "invalid_target", "message": "A permitted application name and opposite Boolean enabled/expected_enabled states are required."}
        action = "web.set_enabled"
        with self.action_lock:
            info = self.info()
            if not next(a for a in self.action_definitions(info) if a["id"] == action)["enabled"]:
                return 403, {"ok": False, "state": "forbidden", "message": "A live %Admin_Secure:U capability check is required."}
            inventory = self.read_resource(RESOURCES["web"][0])
            rows = inventory.get("data")
            row = next((r for r in rows if r.get("Name") == target["name"]), None) if isinstance(rows, list) else None
            if inventory["state"] != "ok" or row is None:
                return 409, {"ok": False, "state": "target_unverified", "message": "The application is not in the current bounded inventory; no command was sent."}
            if row.get("IsSystemApp") is not False or row.get("Type") != "CSP" or not isinstance(row.get("Namespace"), str) or not row["Namespace"] or row["Namespace"].upper() == "%SYS" or not isinstance(row.get("DispatchClass"), str):
                return 403, {"ok": False, "state": "target_not_permitted", "message": "Only inventory-verified non-system CSP applications can be changed."}
            before = self.client.fetch("GET", "/v2/web-app", {"name": target["name"]})
            detail = before["payload"].get("result") if before["state"] == "ok" else None
            identity_matches = isinstance(detail, dict) and detail.get("NameSpace") == row["Namespace"] and detail.get("DispatchClass") == row["DispatchClass"]
            detail_type_valid = isinstance(detail, dict) and ("Type" not in detail or (type(detail["Type"]) is int and not detail["Type"] & 1 and bool(detail["Type"] & 2)))
            if not identity_matches or not detail_type_valid:
                return 409, {"ok": False, "state": "target_unverified", "message": "Application detail identity does not match the verified inventory, or its reported type is unsupported; no command was sent.", "upstream": public_result(before)}
            if row.get("Enabled") is not target["expected_enabled"] or detail.get("Enabled") is not target["expected_enabled"]:
                return 409, {"ok": False, "state": "target_changed", "message": "Application state changed. Refresh and review again; no command was sent."}
            response = self.client.fetch("PUT", "/v2/web-app", {"name": target["name"]}, {"Enabled": target["enabled"]})
            answer = {"ok": response["state"] == "ok", "action": action, "target": target,
                      "before": {"Name": target["name"], "Enabled": target["expected_enabled"]},
                      "upstream": public_result(response), "verification": None}
            if response["state"] != "ok":
                rejected = response["state"] in ("unauthorized", "forbidden", "not_found")
                answer.update(state="rejected" if rejected else "outcome_unknown", message="IRIS rejected the command." if rejected else "The outcome is unknown. Inspect application state before retrying; no automatic retry occurred.")
                return 502, answer
            after = self.client.fetch("GET", "/v2/web-app", {"name": target["name"]})
            updated = after["payload"].get("result") if after["state"] == "ok" else None
            same_fields = isinstance(updated, dict) and {k: v for k, v in detail.items() if k != "Enabled"} == {k: v for k, v in updated.items() if k != "Enabled"}
            verified = same_fields and updated.get("Enabled") is target["enabled"]
            verification = {"key": "web_app", "label": "Web application state", "method": "GET", "path": PREFIX + "/v2/web-app",
                            **public_result(after), "count": 0, "data": None, "sample_limit": None}
            if isinstance(updated, dict):
                verification.update(count=1, data={"Name": target["name"], "Enabled": self.client.clean(updated.get("Enabled")), "other_fields_unchanged": same_fields})
            answer.update(verification=verification, state="verified" if verified else "accepted_unverified",
                          message="The Enabled state was read back and other configuration fields match the pre-update read. No external concurrency lock is held." if verified else "IRIS accepted the update, but the state or other configuration fields could not be verified. Refresh before another command.")
            return 200, answer


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "IRISFieldwork"
    sys_version = ""

    def log_message(self, *args):
        pass  # No request URLs, headers, credentials or payloads in access logs.

    def browser_allowed(self, mutation=False):
        hosts = self.headers.get_all("Host") or []
        port = self.server.server_port
        if len(hosts) != 1 or hosts[0] not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        origins = self.headers.get_all("Origin") or []
        if len(origins) > 1 or (origins and origins[0] != "http://" + hosts[0]):
            return False
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            return False
        if mutation:
            tokens = self.headers.get_all("X-CSRF-Token") or []
            return len(origins) == 1 and len(tokens) == 1 and tokens[0].isascii() and hmac.compare_digest(tokens[0], self.server.gateway.csrf_token)
        return True

    def respond(self, code, payload, content_type="application/json; charset=utf-8"):
        raw = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode() if not isinstance(payload, bytes) else payload
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.browser_allowed():
            self.respond(403, {"error": "origin_denied"}); return
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            if parsed.scheme or parsed.netloc or parsed.fragment or len(self.path) > 4096 or (parsed.query and path != "/api/inspect"):
                self.respond(400, {"error": "invalid_request_path"}); return
            gateway = self.server.gateway
            if path == "/api/inspect":
                params = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True, max_num_fields=3)
                if set(params) != {"kind", "name"} or any(len(v) != 1 for v in params.values()):
                    raise ValueError("Invalid inspection query")
                self.respond(200, gateway.inspect(params["kind"][0], params["name"][0])); return
            if path == "/api/status":
                self.respond(200, gateway.status()); return
            if path == "/api/explorer":
                self.respond(200, gateway.explorer()); return
            if path.startswith("/api/section/") and path.removeprefix("/api/section/") in SECTIONS:
                self.respond(200, gateway.section(path.removeprefix("/api/section/"))); return
            if path.startswith("/api/"):
                self.respond(404, {"error": "route_not_found"}); return
            relative = unquote(path.removeprefix("/static/") if path.startswith("/static/") else path).lstrip("/") or "index.html"
            root = self.server.static_root.resolve()
            file = (root / relative).resolve()
            if not file.is_relative_to(root) or any(part.startswith(".") for part in Path(relative).parts) or file.suffix.lower() not in (".html", ".css", ".js", ".svg", ".png", ".ico", ".woff2") or not file.is_file():
                self.respond(404, {"error": "file_not_found"}); return
            if file.stat().st_size > 4 * BODY_LIMIT:
                self.respond(413, {"error": "file_too_large"}); return
            self.respond(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        except (ValueError, OSError):
            self.respond(400, {"error": "invalid_request"})
        except Exception:
            self.respond(500, {"error": "gateway_error"})

    def do_POST(self):
        if not self.browser_allowed(mutation=True):
            # Draining a small framed body avoids a TCP reset hiding the denial
            # on Windows. Never parse it, wait indefinitely, or accept chunking.
            lengths = self.headers.get_all("Content-Length") or []
            if not self.headers.get("Transfer-Encoding") and len(lengths) == 1 and lengths[0].isascii() and lengths[0].isdigit() and 0 < int(lengths[0]) <= 16384:
                try:
                    self.connection.settimeout(0.2)
                    self.rfile.read(int(lengths[0]))
                except OSError:
                    pass
            self.respond(403, {"error": "origin_or_csrf_denied"}); return
        if self.path not in ("/api/action", "/api/log-query"):
            self.respond(404, {"error": "route_not_found"}); return
        lengths = self.headers.get_all("Content-Length") or []
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 16384:
            self.respond(400, {"error": "invalid_body_length"}); return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.respond(415, {"error": "json_required"}); return
        try:
            self.connection.settimeout(3)
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                raise ValueError("Incomplete body")
            body = json.loads(raw, object_pairs_hook=reject_duplicate_keys,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))
            code, result = self.server.gateway.action(body) if self.path == "/api/action" else self.server.gateway.logs.query(body)
            self.respond(code, result)
        except (ValueError, UnicodeError, OSError, RecursionError):
            self.respond(400, {"error": "invalid_json_body"})
        except Exception:
            self.respond(500, {"error": "gateway_error"})

    def do_OPTIONS(self):
        self.respond(403, {"error": "cross_origin_not_supported"})


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, gateway=None, port=8766, static_root=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.gateway = gateway or Gateway()
        self.static_root = Path(static_root) if static_root else Path(__file__).with_name("static")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    server = LocalServer(port=args.port)
    print(f"IRIS Fieldwork gateway: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
