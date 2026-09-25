"""Allowlisted, read-only access to the optional rotated-message-log adapter."""
import re


INVENTORY = "/fieldwork/runtime/message-archives"
CONTENT = "/fieldwork/runtime/message-archive"
MAX_OFFSET = 9007199254740991
NAME = re.compile(r"messages\.old_[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
REVISION = re.compile(r"[0-9a-f]{64}\Z")
MESSAGES = {
    "invalid": "The archive request is invalid. Refresh the archive list.",
    "not_found": "This archive is no longer present. Refresh the archive list.",
    "changed": "This archive changed. Refresh the list before reading it again.",
    "unavailable": "The archive could not be read with the current runtime permissions.",
    "unsupported": "This archive or runtime does not support safe text-log reading.",
}


def valid_name(value):
    return isinstance(value, str) and NAME.fullmatch(value) is not None and ".." not in value


def valid_revision(value):
    return isinstance(value, str) and REVISION.fullmatch(value) is not None


def offset_number(value):
    if not isinstance(value, str) or re.fullmatch(r"0|[1-9][0-9]{0,15}", value) is None:
        raise ValueError("Invalid archive offset")
    number = int(value)
    if number > MAX_OFFSET:
        raise ValueError("Invalid archive offset")
    return number


def validate_request(method, path, query, body):
    if method != "GET" or body is not None or path not in (INVENTORY, CONTENT):
        return False
    expected = {"offset"} if path == INVENTORY else {"name", "revision", "offset"}
    if set(query) != expected:
        return False
    try:
        offset_number(query["offset"])
    except ValueError:
        return False
    return path == INVENTORY or (valid_name(query["name"]) and valid_revision(query["revision"]))


def integer(value):
    return type(value) is int and 0 <= value <= MAX_OFFSET


def project(raw, path, query, client):
    """Reject malformed paging/identity data and expose no unrecognized fields."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid archive response")
    state = raw.get("state")
    if not isinstance(state, str):
        raise ValueError("Invalid archive state")
    if state in MESSAGES:
        return {"state": state, "message": MESSAGES[state]}
    if state != "ok":
        raise ValueError("Invalid archive state")
    offset = offset_number(query["offset"])
    next_offset = raw.get("nextOffset")
    if raw.get("offset") != offset or type(raw.get("offset")) is not int:
        raise ValueError("Archive page does not match request")
    if next_offset is not None and (not integer(next_offset) or next_offset <= offset):
        raise ValueError("Invalid archive continuation")
    result = {"state": "ok", "offset": offset, "nextOffset": next_offset,
              "scope": client.clean(raw.get("scope", "Bounded archive page"))}
    if path == INVENTORY:
        rows, total = raw.get("files"), raw.get("total")
        if not isinstance(rows, list) or len(rows) > 50 or not integer(total):
            raise ValueError("Invalid archive inventory")
        if next_offset is not None and (next_offset > total or next_offset != offset + len(rows)):
            raise ValueError("Invalid archive inventory continuation")
        files = []
        names = set()
        for row in rows:
            if not isinstance(row, dict) or not valid_name(row.get("name")) or not valid_revision(row.get("revision")) or not integer(row.get("sizeBytes")) or not isinstance(row.get("modifiedAt"), str):
                raise ValueError("Invalid archive metadata")
            if row["name"] in names:
                raise ValueError("Duplicate archive")
            names.add(row["name"])
            files.append({"name": row["name"], "revision": row["revision"],
                          "sizeBytes": row["sizeBytes"], "modifiedAt": client.clean(row["modifiedAt"])})
        result.update(files=files, total=total)
    else:
        records, omitted = raw.get("records"), raw.get("omitted")
        if raw.get("name") != query["name"] or raw.get("revision") != query["revision"] or not integer(raw.get("sizeBytes")):
            raise ValueError("Archive identity does not match request")
        if offset > raw["sizeBytes"] or (next_offset is not None and next_offset > raw["sizeBytes"]):
            raise ValueError("Archive continuation exceeds file")
        if not isinstance(records, list) or len(records) > 80 or not isinstance(omitted, dict) or not integer(raw.get("skippedBytes")):
            raise ValueError("Invalid archive records")
        counts = {}
        for key in ("oversizeSegments", "partialSegments", "binaryRecords"):
            if not integer(omitted.get(key)):
                raise ValueError("Invalid archive omission metadata")
            counts[key] = omitted[key]
        lines = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("line"), str) or len(record["line"]) > 2000:
                raise ValueError("Invalid archive line")
            lines.append({"line": client.clean_log(record["line"], limit=2000)})
        result.update(name=query["name"], revision=query["revision"], sizeBytes=raw["sizeBytes"],
                      records=lines, omitted=counts, skippedBytes=raw["skippedBytes"])
    return result
