#!/usr/bin/env python3
"""Probe documented IRIS admin GET endpoints; emit metadata, never payload values.

Credentials: IRIS_USERNAME + IRIS_PASSWORD, or IRIS_BEARER_TOKEN (not both).
Usage: python probe.py http://127.0.0.1:52773
No redirects, proxies, login requests, response files, or non-loopback hosts.
"""

import argparse
import base64
import http.client
import ipaddress
import json
import math
import os
import socket
import ssl
import sys
from urllib.parse import urlsplit


API_PREFIX = "/api/admin"
MAX_ROWS = 5
MAX_BODY_BYTES = 262144
# Boolean: the pinned specification supports a maxRows query parameter.
ENDPOINTS = (
    ("/info", False),
    ("/v2/web-apps", True),
    ("/v2/security/roles", True),
    ("/v2/security/resources", True),
    ("/v2/security/users", True),
    ("/v2/wallet/collections", True),
    ("/v2/security/x509-credentials", True),
    ("/v2/security/ssl-configurations", True),
    ("/v2/security/oauth2/client/server-definitions", True),
    ("/v2/security/oauth2/server/clients", True),
    ("/v2/tasks", True),
    ("/v2/task/manager", False),
    ("/v2/task/history", True),
    ("/v2/processes", True),
    ("/v2/devices", True),
    ("/v2/database-dirs", True),
    ("/v2/monitor/dashboard/main", False),
    ("/v2/monitor/dashboard/system-resources", False),
    ("/v2/monitor/system-usage", False),
    ("/v2/monitor/system-usage/shared-memory", False),
    ("/v2/security/audit/events", True),
    ("/v2/journal/files", True),
)
INFO_KEYS = frozenset((
    "apiVersion", "username", "serverVersion", "systemMode", "product",
    "namespaces", "privileges",
))
RESPONSE_KEYS = frozenset(("status", "console", "result"))


def parse_target(base_url):
    """Return a literal loopback connection target. Never echo invalid input."""
    if not isinstance(base_url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in base_url):
        raise ValueError("base URL must not contain whitespace or control characters")
    try:
        parsed = urlsplit(base_url)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise ValueError("invalid base URL") from None
    if parsed.scheme not in ("http", "https") or not host:
        raise ValueError("an http or https loopback base URL is required")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are forbidden; use the documented environment variables")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/", API_PREFIX, API_PREFIX + "/"):
        raise ValueError("base URL may contain only the origin and optional /api/admin path")
    if "%" in host:
        raise ValueError("encoded hosts and IPv6 zone identifiers are forbidden")
    # Pin localhost to a numeric address: no DNS resolution/rebinding or proxy use.
    if host.lower() == "localhost":
        host = "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("only localhost or literal loopback IP addresses are allowed") from None
    if not address.is_loopback:
        raise ValueError("non-loopback addresses are forbidden")
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    return parsed.scheme, str(address), port


def auth_header(environ):
    """Build one header in memory; never include credential values in errors."""
    username = environ.get("IRIS_USERNAME")
    password = environ.get("IRIS_PASSWORD")
    token = environ.get("IRIS_BEARER_TOKEN")
    if token is not None:
        if username is not None or password is not None:
            raise ValueError("set bearer credentials or username/password, not both")
        if not token or not token.isascii() or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in token):
            raise ValueError("invalid bearer-token format")
        return "Bearer " + token
    if not username or not password:
        raise ValueError("set IRIS_USERNAME and IRIS_PASSWORD, or IRIS_BEARER_TOKEN")
    if ":" in username or any(ord(c) < 32 or ord(c) == 127 for c in username + password):
        raise ValueError("invalid basic-credential format")
    encoded = base64.b64encode((username + ":" + password).encode("utf-8")).decode("ascii")
    return "Basic " + encoded


def summarize_payload(payload, path):
    """Only emit schema-known top-level key names and computed lengths.

    Unknown field names are withheld because arbitrary JSON keys can themselves
    contain usernames, secret material, or raw log messages.
    """
    if not isinstance(payload, dict):
        return {"state": "unexpected_json_shape", "counts": {
            "top_level_items": len(payload) if isinstance(payload, list) else 0,
        }}
    info = payload.get("result") if path == "/info" and isinstance(payload.get("result"), dict) else payload
    allowed = INFO_KEYS if path == "/info" and info is payload else RESPONSE_KEYS
    keys = sorted(set(payload).intersection(allowed))
    counts = {
        "top_level_fields": len(payload),
        "unreported_top_level_fields": len(set(payload).difference(allowed)),
    }
    for name in ("result", "console", "namespaces", "privileges"):
        value = payload.get(name)
        if isinstance(value, list):
            counts[name + "_items"] = len(value)
        elif isinstance(value, dict):
            counts[name + "_fields"] = len(value)
    status = payload.get("status")
    errors = (status.get("Errors") or status.get("errors")) if isinstance(status, dict) else None
    if isinstance(errors, list):
        counts["status_error_items"] = len(errors)
    expected = {"apiVersion", "serverVersion"} if path == "/info" else {"result"}
    state = "ok" if expected.issubset(info if path == "/info" else payload) else "unexpected_json_shape"
    if isinstance(errors, list) and errors:
        state = "application_error"
    return {"state": state, "top_level_keys": keys, "counts": counts}


def probe_endpoint(target, authorization, path, timeout=5.0):
    allowlist = dict(ENDPOINTS)
    if path not in allowlist:
        raise ValueError("endpoint is not in the GET allowlist")
    scheme, host, port = target
    # Validate again for callers importing this function instead of using the CLI.
    if scheme not in ("http", "https") or not ipaddress.ip_address(host).is_loopback or not 1 <= port <= 65535:
        raise ValueError("invalid loopback connection target")
    request_path = API_PREFIX + path
    if allowlist[path]:
        request_path += "?maxRows=" + str(MAX_ROWS)
    result = {"path": request_path, "http_status": None}
    connection = None
    try:
        if scheme == "https":
            connection = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            connection = http.client.HTTPConnection(host, port, timeout=timeout)
        connection.request("GET", request_path, headers={
            "Authorization": authorization,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "ClearRow-IRIS-Capability-Probe/1.0",
            "Connection": "close",
        })
        response = connection.getresponse()
        result["http_status"] = response.status
        specific = {401: "unauthorized", 403: "forbidden", 404: "not_found"}
        if response.status in specific:
            result["state"] = specific[response.status]
        elif 300 <= response.status < 400:
            result["state"] = "redirect_refused"
        elif not 200 <= response.status < 300:
            result["state"] = "http_error"
        else:
            content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json" and not content_type.endswith("+json"):
                result["state"] = "non_json_response"
            elif (response.getheader("Content-Encoding") or "identity").strip().lower() not in ("", "identity"):
                result["state"] = "unsupported_content_encoding"
            else:
                body = response.read(MAX_BODY_BYTES + 1)
                if len(body) > MAX_BODY_BYTES:
                    result["state"] = "response_too_large"
                else:
                    try:
                        payload = json.loads(body)
                    except (ValueError, UnicodeError, RecursionError):
                        result["state"] = "invalid_json"
                    else:
                        result.update(summarize_payload(payload, path))
    except ssl.SSLCertVerificationError:
        result.update(state="unavailable", reason="tls_verification_failed")
    except ssl.SSLError:
        result.update(state="unavailable", reason="tls_error")
    except (TimeoutError, socket.timeout):
        result.update(state="unavailable", reason="timeout")
    except ConnectionRefusedError:
        result.update(state="unavailable", reason="connection_refused")
    except (OSError, http.client.HTTPException):
        result.update(state="unavailable", reason="connection_or_protocol_error")
    finally:
        if connection is not None:
            connection.close()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="loopback origin, optionally ending in /api/admin")
    parser.add_argument("--timeout", type=float, default=5.0, help="per-request socket timeout, 0.1 to 30 seconds")
    parser.add_argument("--path", action="append", help="probe only this allowlisted relative path; repeat as needed")
    args = parser.parse_args(argv)
    try:
        target = parse_target(args.base_url)
        if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= 30:
            raise ValueError("timeout must be between 0.1 and 30 seconds")
        selected = list(dict.fromkeys(args.path or [path for path, _ in ENDPOINTS]))
        if any(path not in dict(ENDPOINTS) for path in selected):
            raise ValueError("requested path is not in the GET allowlist")
        authorization = auth_header(os.environ)
    except ValueError as error:
        print(json.dumps({"state": "configuration_error", "reason": str(error)}), file=sys.stderr)
        return 2
    succeeded = True
    for path in selected:
        result = probe_endpoint(target, authorization, path, args.timeout)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
        succeeded = succeeded and result["state"] == "ok"
    return 0 if succeeded else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(json.dumps({"state": "interrupted"}), file=sys.stderr)
        sys.exit(130)
