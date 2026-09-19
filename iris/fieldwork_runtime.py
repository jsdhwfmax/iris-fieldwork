"""Bounded Linux telemetry used inside IRIS Embedded Python.

Read scope is the IRIS process's Linux kernel and fixed local log files.
This module accepts no client-supplied paths, commands or code.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time


def envelope(result):
    return json.dumps({'status': {'errors': [], 'summary': 'OK'},
                       'console': [], 'result': result}, ensure_ascii=True)


def metrics():
    def cpu_snapshot():
        values = [int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
        return sum(values), values[3] + values[4]
    result = {'sampledAt': datetime.now(timezone.utc).isoformat(),
              'scope': 'Linux kernel visible to IRIS; kernel memory/CPU may exceed container limits.'}
    try:
        total1, idle1 = cpu_snapshot()
        time.sleep(0.15)
        total2, idle2 = cpu_snapshot()
        delta = total2 - total1
        result['cpuBusyPercent'] = round(100 * (1 - (idle2-idle1)/delta), 1) if delta > 0 else None
        result['cpuSampleMilliseconds'] = 150
        mem = {line.split(':')[0]: int(line.split()[1]) * 1024
               for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split()) >= 2}
        result.update(memoryTotalBytes=mem.get('MemTotal'), memoryAvailableBytes=mem.get('MemAvailable'))
        disk = os.statvfs('/usr/irissys/mgr')
        result.update(irisDiskTotalBytes=disk.f_blocks*disk.f_frsize,
                      irisDiskAvailableBytes=disk.f_bavail*disk.f_frsize)
        for filename, key in [('memory.max', 'containerMemoryLimitBytes'),
                              ('memory.current', 'containerMemoryUsedBytes')]:
            path = Path('/sys/fs/cgroup') / filename
            if path.is_file():
                value = path.read_text().strip()
                result[key] = int(value) if value.isdecimal() else value
        quota = Path('/sys/fs/cgroup/cpu.max')
        if quota.is_file():
            limit, period = quota.read_text().split()
            result['containerCpuLimitCores'] = round(int(limit)/int(period), 2) if limit != 'max' else None
    except (OSError, ValueError, IndexError):
        result['availability'] = 'partial: Linux telemetry could not be fully read'
    return envelope(result)


SOURCES = [('IRIS messages', '/usr/irissys/mgr/messages.log'),
           ('Web Gateway', '/usr/irissys/csp/bin/CSP.log'),
           ('HTTP server errors', '/usr/irissys/csp/httpd/logs/error_log')]
SECRET = re.compile(r'''(?i)(?:password|passwd|pwd|authorization|(?:set-)?cookie|(?:access|refresh)[_ -]?token|client[_ -]?secret|api[_ -]?key)\s*["']?\s*[:=]''')


def redact_line(line):
    # Withhold the whole line: replacing just one word can leave the token after
    # an auth scheme, or the remainder of a quoted password, visible downstream.
    return '[sensitive log line withheld]' if SECRET.search(line) else line[:2000]


def logs():
    output = []
    for label, path in SOURCES:
        entry = {'source': label, 'scope': 'last 80 lines, up to 64 KiB', 'records': []}
        try:
            with open(path, 'rb') as stream:
                size = os.fstat(stream.fileno()).st_size
                start = max(0, size-65536)
                stream.seek(start)
                raw = stream.read(65536)
            lines = raw.decode('utf-8', 'replace').splitlines()
            if start and lines:
                lines = lines[1:]
            entry['truncated'] = bool(start or len(lines) > 80)
            entry['records'] = [{'line': redact_line(line)}
                                for line in lines[-80:]]
            entry['state'] = 'ok'
        except FileNotFoundError:
            entry['state'] = 'not_present'
        except OSError:
            entry['state'] = 'unavailable'
        output.append(entry)
    return envelope(output)
