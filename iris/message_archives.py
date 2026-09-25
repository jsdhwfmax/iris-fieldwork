"""Read-only, bounded access to rotated IRIS message logs on supported POSIX hosts.

The production directory is fixed. Directory-relative, no-follow opens prevent
request-controlled traversal and final-component symlink races. Unsupported
hosts fail closed; tests can substitute a directory containing synthetic data.
"""
from datetime import datetime, timezone
import errno
import hashlib
import os
import re
import stat

from fieldwork_runtime import envelope, redact_line


_ROOT = "/usr/irissys/mgr"
PAGE_FILES = 50
PAGE_BYTES = 65536
PAGE_ROWS = 80
MAX_LINE_BYTES = 8000
MAX_LINE_CHARACTERS = 2000
MAX_OFFSET = 9007199254740991
NAME = re.compile(r"messages\.old_[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z", re.ASCII)
REVISION = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
OFFSET = re.compile(r"(?:0|[1-9][0-9]{0,15})\Z", re.ASCII)
COMPRESSED = (".gz", ".bz2", ".xz", ".zip", ".zst", ".lz4", ".7z", ".tgz", ".lz")
SCOPE = ("Uncompressed text archives matching IRIS messages.old_* only; at most 64 KiB read and 80 complete "
         "UTF-8 records per page. Sensitive lines and incomplete/oversize records are withheld.")
MESSAGES = {
    "invalid": "Invalid archive request.",
    "not_found": "The selected archive is no longer present.",
    "changed": "The archive changed. Refresh the inventory before reading again.",
    "unavailable": "The archive could not be read safely.",
    "unsupported": "This archive format or safe file access is unsupported.",
}


class UnsupportedAccess(Exception):
    pass


class ArchiveDirectory:
    """Pin the trusted directory and never follow an archive symlink."""

    def __enter__(self):
        required = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
        if (os.name != "posix" or any(not hasattr(os, flag) for flag in required)
                or os.open not in os.supports_dir_fd
                or os.stat not in os.supports_dir_fd
                or os.stat not in os.supports_follow_symlinks
                or os.listdir not in os.supports_fd):
            raise UnsupportedAccess()
        self.fd = os.open(_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    def names(self):
        return os.listdir(self.fd)

    def metadata(self, name):
        return os.stat(name, dir_fd=self.fd, follow_symlinks=False)

    def open(self, name):
        # NONBLOCK also prevents a swapped-in FIFO from blocking before fstat.
        return os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                       dir_fd=self.fd)


def _offset(value):
    if not isinstance(value, str) or not OFFSET.fullmatch(value):
        raise ValueError()
    parsed = int(value)
    if parsed > MAX_OFFSET:
        raise ValueError()
    return parsed


def _valid_name(name):
    return isinstance(name, str) and bool(NAME.fullmatch(name)) and ".." not in name


def _revision(metadata):
    # Opaque identity/version token. ctime catches replacements and changes even
    # when a writer restores mtime; this is not a filesystem transaction lock.
    values = (metadata.st_dev, metadata.st_ino, metadata.st_size,
              metadata.st_mtime_ns, metadata.st_ctime_ns)
    return hashlib.sha256(":".join(map(str, values)).encode("ascii")).hexdigest()


def _inventory_result(offset=0):
    return {"state": "ok", "files": [], "offset": offset, "nextOffset": None,
            "total": 0, "scope": SCOPE}


def _read_result(name="", revision="", offset=0):
    return {"state": "ok", "name": name, "revision": revision, "sizeBytes": 0,
            "offset": offset, "nextOffset": None, "records": [],
            "omitted": {"oversizeSegments": 0, "partialSegments": 0, "binaryRecords": 0},
            "skippedBytes": 0, "scope": SCOPE}


def _error(result, state):
    result.update(state=state, message=MESSAGES[state], nextOffset=None)
    if "records" in result:
        result["records"] = []
    if "files" in result:
        result["files"] = []
    return result


def inventory(offset="0"):
    """Return fifty filename-sorted entries; this is a fresh, non-atomic listing."""
    try:
        start = _offset(offset)
    except ValueError:
        return _error(_inventory_result(), "invalid")
    result = _inventory_result(start)
    try:
        with ArchiveDirectory() as directory:
            files = []
            for name in directory.names():
                if not _valid_name(name) or name.lower().endswith(COMPRESSED):
                    continue
                try:
                    metadata = directory.metadata(name)
                except FileNotFoundError:
                    continue  # Rotation while listing; a later read verifies identity again.
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_OFFSET:
                    continue
                files.append({"name": name, "sizeBytes": metadata.st_size,
                              "modifiedAt": datetime.fromtimestamp(
                                  metadata.st_mtime, timezone.utc).isoformat(),
                              "revision": _revision(metadata)})
            files.sort(key=lambda entry: entry["name"])
            result["total"] = len(files)
            if start > len(files):
                return _error(result, "invalid")
            result["files"] = files[start:start + PAGE_FILES]
            if start + PAGE_FILES < len(files):
                result["nextOffset"] = start + PAGE_FILES
    except UnsupportedAccess:
        return _error(result, "unsupported")
    except (OSError, ValueError, OverflowError):
        return _error(result, "unavailable")
    return result


def _skip(result, kind, amount):
    result["omitted"][kind] += 1
    result["skippedBytes"] += amount


def _page(fd, result):
    """Read at most PAGE_BYTES including the preceding boundary-check byte."""
    start, size = result["offset"], result["sizeBytes"]
    if start == size:
        return result
    budget = PAGE_BYTES
    boundary = True
    if start:
        os.lseek(fd, start - 1, os.SEEK_SET)
        boundary = os.read(fd, 1) == b"\n"
        budget -= 1
    else:
        os.lseek(fd, 0, os.SEEK_SET)
    data = os.read(fd, min(budget, size - start))
    if not data:
        # With a nonempty stat size this means a concurrent truncation or I/O race.
        return _error(result, "changed")
    if any(byte < 32 and byte not in (9, 10, 13) or byte == 127 for byte in data):
        # Catch binary/compressed content even if it has no newline. Never show a
        # binary prefix as a text record, and discard earlier rows on this page.
        _skip(result, "binaryRecords", len(data))
        return _error(result, "unsupported")
    position = 0
    if not boundary:
        end = data.find(b"\n")
        position = len(data) if end < 0 else end + 1
        _skip(result, "partialSegments", position)
    while position < len(data) and len(result["records"]) < PAGE_ROWS:
        end = data.find(b"\n", position)
        if end < 0:
            length = len(data) - position
            at_eof = start + len(data) == size
            if length > MAX_LINE_BYTES:
                _skip(result, "oversizeSegments", length)
                position = len(data)
            elif at_eof:
                _skip(result, "partialSegments", length)
                position = len(data)
            # A short line crossing the byte boundary is deferred intact. If it
            # fills an entire later page, the oversize branch advances the cursor.
            break
        raw = data[position:end]
        consumed = end + 1 - position
        position = end + 1
        if len(raw) > MAX_LINE_BYTES:
            _skip(result, "oversizeSegments", consumed)
            continue
        try:
            line = raw.decode("utf-8", "strict")
        except UnicodeDecodeError:
            _skip(result, "binaryRecords", consumed)
            return _error(result, "unsupported")
        if line.endswith("\r"):
            line = line[:-1]
        if any(ord(character) < 32 and character != "\t" or ord(character) == 127
               for character in line):
            _skip(result, "binaryRecords", consumed)
            return _error(result, "unsupported")
        if len(line) > MAX_LINE_CHARACTERS:
            _skip(result, "oversizeSegments", consumed)
            continue
        result["records"].append({"line": redact_line(line)})
    cursor = start + position
    if cursor < size:
        if cursor <= start:
            # Only reachable for an unexpectedly short non-EOF read. Withhold the
            # fragment rather than return a cursor that can loop forever.
            _skip(result, "partialSegments", len(data))
            cursor = start + len(data)
        result["nextOffset"] = cursor
    return result


def read_archive(name, revision, offset="0"):
    try:
        start = _offset(offset)
        if not _valid_name(name) or not isinstance(revision, str) or not REVISION.fullmatch(revision):
            raise ValueError()
    except ValueError:
        return _error(_read_result(), "invalid")
    result = _read_result(name, revision, start)
    if name.lower().endswith(COMPRESSED):
        return _error(result, "unsupported")
    fd = None
    try:
        with ArchiveDirectory() as directory:
            try:
                fd = directory.open(name)
            except FileNotFoundError:
                return _error(result, "not_found")
            except OSError as error:
                return _error(result, "unsupported" if error.errno == errno.ELOOP else "unavailable")
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode):
                    return _error(result, "unsupported")
                result["sizeBytes"] = before.st_size
                if before.st_size > MAX_OFFSET:
                    return _error(result, "unsupported")
                if _revision(before) != revision:
                    return _error(result, "changed")
                if start > before.st_size:
                    return _error(result, "invalid")
                _page(fd, result)
                after = os.fstat(fd)
                try:
                    current = directory.metadata(name)
                except FileNotFoundError:
                    return _error(result, "changed")
                if (not stat.S_ISREG(current.st_mode) or _revision(after) != revision
                        or _revision(current) != revision):
                    return _error(result, "changed")
            finally:
                os.close(fd)
                fd = None
    except UnsupportedAccess:
        return _error(result, "unsupported")
    except OSError:
        return _error(result, "unavailable")
    return result


def collect(kind, name="", revision="", offset="0", valid=True):
    """Embedded-Python entry point; no client text is reflected by invalid results."""
    if not valid:
        result = _inventory_result() if kind == "inventory" else _read_result()
        return envelope(_error(result, "invalid"))
    if kind == "inventory":
        return envelope(inventory(offset))
    if kind == "read":
        return envelope(read_archive(name, revision, offset))
    return envelope(_error(_read_result(), "invalid"))
