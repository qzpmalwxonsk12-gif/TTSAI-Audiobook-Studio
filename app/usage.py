"""Read-only provider balances, clearly separated from local request reservations."""
from datetime import datetime, timezone
import hashlib
import json
import threading
import time

import httpx

from . import cloud, store

_cache = {}
_lock = threading.Lock()


def percentage(used, limit):
    return round(100 * used / limit, 1) if limit > 0 else None


def elevenlabs_balance():
    try:
        api_key = cloud.key('elevenlabs')
    except cloud.ProviderError:
        return {'available': False, 'message': 'Add an ElevenLabs key to read its balance.'}
    fingerprint = hashlib.sha256(api_key.encode()).hexdigest()
    # Cache failures too, so denied requests are not repeated on every UI poll.
    with _lock:
        cached = _cache.get(fingerprint)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        result = {'available': False, 'checked_at': datetime.now(timezone.utc).isoformat()}
        try:
            response = httpx.get('https://api.elevenlabs.io/v1/user/subscription',
                                 headers={'xi-api-key': api_key}, timeout=8, follow_redirects=False)
            if response.status_code in (401, 403):
                result['message'] = 'Balance unavailable. Check the key and enable User: Read to view usage.'
            elif not response.is_success:
                result['message'] = 'ElevenLabs balance is temporarily unavailable. Local counters remain available.'
            else:
                data = response.json()
                used, limit = data.get('character_count'), data.get('character_limit')
                if type(used) is not int or type(limit) is not int or used < 0 or limit < 0:
                    raise ValueError('Invalid usage response')
                result.update(available=True, used=used, limit=limit, remaining=max(0, limit-used),
                              percent_used=percentage(used, limit), tier=str(data.get('tier') or 'Unknown'),
                              resets_at=data.get('next_character_count_reset_unix'))
        except (httpx.HTTPError, ValueError, TypeError):
            result['message'] = 'Could not read the provider balance. No generation request was made.'
        _cache.clear()
        _cache[fingerprint] = (time.monotonic(), result)
        return result


def snapshot(book_id=None):
    now = datetime.now(timezone.utc)
    month = now.strftime('%Y-%m-01 00:00:00')
    today = now.strftime('%Y-%m-%d 00:00:00')
    providers = []
    connected = cloud.connections()
    job_usage = None
    with store.connect() as db:
        for provider in cloud.PROVIDERS:
            row = db.execute('''SELECT COUNT(*) AS requests, COALESCE(SUM(chars),0) AS speech_characters,
                COALESCE(SUM(created>=?),0) AS requests_today FROM cloud_usage
                WHERE provider=? AND created>=?''', (today, provider, month)).fetchone()
            providers.append({'provider': provider, 'connected': connected[provider],
                              'local': dict(row), 'account': None})
        if book_id:
            store.book(db, book_id)
            job = db.execute('SELECT id,type,state,options FROM jobs WHERE book_id=? ORDER BY created DESC,rowid DESC LIMIT 1', (book_id,)).fetchone()
            if job:
                options = json.loads(job['options'])
                if options.get('mapping_provider') == 'gemini' or options.get('tts_provider', 'local') != 'local':
                    row = db.execute('SELECT COUNT(*),COALESCE(SUM(chars),0) FROM cloud_usage WHERE scope=?', (job['id'],)).fetchone()
                    request_limit, char_limit = options.get('max_cloud_requests', 60), options.get('max_cloud_chars', 10000)
                    job_usage = {'id': job['id'], 'type': job['type'], 'state': job['state'],
                                 'requests': row[0], 'request_limit': request_limit,
                                 'request_percent': percentage(row[0], request_limit),
                                 'speech_characters': row[1], 'character_limit': char_limit,
                                 'character_percent': percentage(row[1], char_limit)}
    providers[1]['account'] = elevenlabs_balance()
    return {'month_utc': now.strftime('%Y-%m'), 'providers': providers, 'job': job_usage}
