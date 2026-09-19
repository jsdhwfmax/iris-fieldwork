"""Bounded audit and journal metadata searches through the IRIS async API."""
from datetime import datetime
import re
import secrets
import threading
import time

ROW_LIMIT = 100
READ_PATHS = {'/v2/async-result'}
WRITE_ROUTES = {('POST', '/v2/security/audit/records'), ('POST', '/v2/journal/file/records')}
PATHS = {'audit': '/v2/security/audit/records', 'journal': '/v2/journal/file/records'}
FIELDS = {
    'audit': 'AuditIndex TimeStamp UTCTimeStamp EventSource EventType Event Username Namespace Pid JobNumber Authentication SystemID',
    'journal': 'Address TypeName ExtTypeName TimeStamp InTransaction ProcessID DatabaseName',
}


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9]{1,64}', value) is not None


def valid_text(value):
    return isinstance(value, str) and (not value or re.fullmatch(r'[A-Za-z0-9_%][A-Za-z0-9_.% -]{0,127}', value) is not None)


def valid_date(value):
    if value == '':
        return True
    if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', value) is None:
        return False
    try:
        datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return True
    except ValueError:
        return False


def valid_file(value):
    return isinstance(value, str) and 1 <= len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value) and '..' not in value.replace('\\', '/').split('/')


def validate_request(method, path, query=None, body=None):
    q = query or {}
    if not isinstance(q, dict) or body is not None:
        return False
    if method == 'GET' and path == '/v2/async-result':
        return set(q) == {'id'} and valid_id(q['id'])
    if method != 'POST' or path not in PATHS.values() or type(q.get('maxRows')) is not int or not 1 <= q['maxRows'] <= ROW_LIMIT:
        return False
    if path == PATHS['audit']:
        return (set(q) <= {'maxRows', 'ascending', 'beginDateTime', 'endDateTime', 'usernames', 'events'}
                and type(q.get('ascending')) is int and q['ascending'] == 0
                and all(valid_date(q.get(k, '')) for k in ('beginDateTime', 'endDateTime'))
                and all(valid_text(q.get(k, '')) for k in ('usernames', 'events')))
    return set(q) == {'file', 'reverse', 'maxRows'} and valid_file(q['file']) and type(q['reverse']) is int and q['reverse'] == 1


class LogOps:
    """Track only this gateway's searches; never expose other users' async jobs."""
    def __init__(self, client, info_callback):
        self.client, self.info_callback = client, info_callback
        self.queries = {}
        self.lock = threading.Lock()

    def _result(self, kind, state='ok', **extra):
        return {'key': kind + '_records', 'label': ('Audit' if kind == 'audit' else 'Journal') + ' record metadata',
                'method': 'POST', 'path': '/api/admin' + PATHS.get(kind, ''), 'state': state,
                'http_status': None, 'error': None, 'data': [], 'count': 0, 'sample_limit': ROW_LIMIT,
                'limitations': ['Results are bounded metadata, not a complete export. Audit event data, session identifiers and journal global nodes/values are withheld. Dates use the IRIS server clock.'], **extra}

    def _error(self, kind, code, message, http=400):
        return http, self._result(kind, code, query_state='failed', error={'code': code, 'message': message})

    def query(self, body):
        if not isinstance(body, dict) or set(body) != {'kind', 'filters'} or not isinstance(body['filters'], dict):
            return self._error('audit', 'invalid_input', 'Use an exact kind and filters object.')
        kind, filters = body['kind'], body['filters']
        if kind == 'result':
            if set(filters) != {'id'} or not isinstance(filters['id'], str):
                return self._error('audit', 'invalid_input', 'A query identifier is required.')
            with self.lock:
                self._expire()
                item = self.queries.get(filters['id'])
            if item is None:
                return self._error('audit', 'query_expired', 'The query is unknown or expired. No search was restarted.', 404)
            return self._poll(filters['id'], item)
        if not isinstance(kind, str) or kind not in PATHS:
            return self._error('audit', 'invalid_input', 'Unknown log search kind.')
        limit = filters.get('limit')
        if type(limit) is not int or not 1 <= limit <= ROW_LIMIT:
            return self._error(kind, 'invalid_input', 'The row limit must be between 1 and 100.')
        if kind == 'audit':
            if set(filters) != {'begin', 'end', 'username', 'event', 'limit'} or not all(valid_date(filters[k]) for k in ('begin', 'end')) or not all(valid_text(filters[k]) for k in ('username', 'event')):
                return self._error(kind, 'invalid_input', 'Use server-clock dates in YYYY-MM-DD HH:MM:SS format and single user/event names.')
            if filters['begin'] and filters['end'] and filters['begin'] > filters['end']:
                return self._error(kind, 'invalid_input', 'The start date must precede the end date.')
            query = {'maxRows': limit, 'ascending': 0}
            for source, destination in [('begin','beginDateTime'),('end','endDateTime'),('username','usernames'),('event','events')]:
                if filters[source]:
                    query[destination] = filters[source]
        else:
            if set(filters) != {'file', 'limit'} or not valid_file(filters['file']):
                return self._error(kind, 'invalid_input', 'Select an exact journal file from the current inventory.')
            inventory = self.client.fetch('GET', '/v2/journal/files', {'maxRows': ROW_LIMIT})
            rows = (inventory.get('payload') or {}).get('result')
            if inventory.get('state') != 'ok' or not isinstance(rows, list) or len([r for r in rows[:ROW_LIMIT] if isinstance(r, dict) and r.get('Name') == filters['file']]) != 1:
                return self._error(kind, 'target_unverified', 'The journal file could not be matched to the current bounded inventory.', 409)
            query = {'file': filters['file'], 'reverse': 1, 'maxRows': limit}
        info = self.info_callback()
        privileges = (info.get('data') or {}).get('privileges', {})
        required = ['Operate', 'Secure'] if kind == 'audit' else ['Operate']
        if info.get('state') != 'ok' or not all(privileges.get(p, {}).get('use') is True for p in required):
            return self._error(kind, 'forbidden', 'Required IRIS privileges for this search and its result are unavailable.', 403)
        # Reserve a bounded slot before dispatch. Never automatically resubmit a POST.
        with self.lock:
            self._expire()
            if len(self.queries) >= 32:
                return self._error(kind, 'query_limit', 'The session search limit was reached. Existing queries expire after ten minutes.', 429)
            token = secrets.token_urlsafe(24)
            item = {'kind': kind, 'limit': limit, 'created': time.monotonic(), 'upstream_id': None}
            self.queries[token] = item
        response = self.client.fetch('POST', PATHS[kind], query)
        if response.get('state') != 'ok' or response.get('http_status') != 202 or not valid_id(response.get('async_id')):
            with self.lock:
                self.queries.pop(token, None)
            return self._error(kind, 'search_not_verified', 'The search was not confirmed. No automatic retry occurred.', 502)
        item['upstream_id'] = response['async_id']
        return self._poll(token, item)

    def _expire(self):
        cutoff = time.monotonic() - 600
        self.queries = {key: value for key, value in self.queries.items() if value['created'] > cutoff}

    def _poll(self, token, item):
        kind = item['kind']
        if not valid_id(item.get('upstream_id')):
            return self._error(kind, 'query_pending', 'The search is still being dispatched. It was not restarted.', 409)
        response = self.client.fetch('GET', '/v2/async-result', {'id': item['upstream_id']})
        raw = (response.get('payload') or {}).get('result')
        if response.get('state') != 'ok' or not isinstance(raw, dict) or raw.get('TaskName') != 'POST ' + PATHS[kind] or ('GUID' in raw and raw['GUID'] != item['upstream_id']):
            return self._error(kind, 'result_unverified', 'The search result could not be verified. The search was not restarted.', 502)
        state = raw.get('State')
        result = self._result(kind, query_id=token, query_state='pending', sample_limit=item['limit'], http_status=response.get('http_status'),
                              query_status=state if state in ('Queued', 'Running', 'Finished', 'Failed', 'Canceled', 'Paused') else 'Unknown')
        if state in ('Queued', 'Running', 'Paused'):
            result['message'] = 'Search ' + state.lower() + '. Refresh this result to check again; refreshing does not start another search.'
            return 200, result
        if state != 'Finished':
            return self._error(kind, 'search_failed', 'IRIS did not finish the search successfully. Console and failure details were withheld.', 502)
        rows = raw.get('Result')
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return self._error(kind, 'invalid_response', 'The completed search returned an unexpected record format.', 502)
        result.update(query_state='complete', data=[{key: self.client.clean_log(row[key]) if isinstance(row[key], str) else self.client.clean(row[key])
                      for key in FIELDS[kind].split() if key in row} for row in rows[:item['limit']]])
        result['count'] = len(result['data'])
        result['at_limit'] = len(rows) >= item['limit']
        result['message'] = 'Search finished. The sample limit was reached; more records may exist.' if result['at_limit'] else 'Search finished; bounded record metadata returned.'
        return 200, result
