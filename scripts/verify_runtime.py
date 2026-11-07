"""Real CPU and local-AI acceptance check; writes a report and keeps sample audio in the library."""
import hashlib
import io
import json
import sys
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8767/api'


def api(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=600))


def wait(bid, jid, limit=1200):
    start = time.perf_counter()
    last = ''
    while time.perf_counter() - start < limit:
        book = api('/books/' + bid)
        job = next(j for j in book['jobs'] if j['id'] == jid)
        mark = job['state'] + ': ' + job['message']
        if mark != last:
            print(mark, flush=True)
            last = mark
        if job['state'] in ('complete', 'failed', 'needs_review', 'paused'):
            return book, job, time.perf_counter() - start
        time.sleep(5)
    raise TimeoutError('Acceptance job exceeded 20 minutes. Inspect the resumable job in the app.')


report = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'hardware': api('/status')}
sample = {'title': 'The Bridge at Dawn', 'text': (ROOT / 'samples/bridge.txt').read_text(encoding='utf-8')}
bid = api('/books', sample)['id']
report['book_id'] = bid
jid = api('/books/' + bid + '/jobs', {'type': 'map'})['id']
book, job, elapsed = wait(bid, jid)
report['mapping_seconds'] = elapsed
report['map_job'] = job
report['cast'] = book['cast']
(ROOT / 'docs/runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert job['state'] == 'complete', job
names = {c['name']: c for c in book['cast']}
assert 'Sam' in names and 'Mira' in names, 'AI failed to identify the named cast'
chapters = [api('/chapters/' + c['id']) for c in book['chapters']]
labels = []
for c in chapters:
    for s in c['segments']:
        if s['kind'] != 'narration':
            labels.append({'chapter': c['title'], 'text': s['text'], 'speaker': next((x['name'] for x in book['cast'] if x['id'] == s['speaker']), None), 'review': s['review'], 'kind': s['kind']})
report['labels'] = labels
return_line = next(s for s in chapters[-1]['segments'] if 'I told you I would come back' in s['text'])
report['sam_return_correct'] = return_line['speaker'] == names['Sam']['id']
unknown = next(s for s in chapters[0]['segments'] if 'Did you hear that?' in s['text'])
report['ambiguity_flagged'] = bool(unknown['review'])
(ROOT / 'docs/runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert report['sam_return_correct'], 'Returning speaker was misidentified'
assert report['ambiguity_flagged'], 'Ambiguous speaker should be flagged'
print('Cast:', ', '.join(names), 'Sam return:', report['sam_return_correct'], 'Ambiguous flagged:', report['ambiguity_flagged'], flush=True)
# This is an explicit acceptance-test fallback for the deliberately unknowable line.
jid = api('/books/' + bid + '/jobs', {'type': 'render', 'thoughts': True, 'allow_unresolved': True})['id']
book, job, elapsed = wait(bid, jid)
report['render_seconds'] = elapsed
report['render_job'] = job
report['audio'] = []
for a in book['artifacts']:
    if a['job_id'] != jid:
        continue
    audio = urllib.request.urlopen(BASE + '/artifacts/' + a['id']).read()
    import soundfile as sf
    import numpy as np
    pcm, sr = sf.read(io.BytesIO(audio), dtype='int16')
    assert len(pcm) > 0 and sr == 24000
    assert np.max(np.abs(pcm.astype(np.int32))) > 100, 'Audio is silent'
    report['audio'].append({'title': a['chapter_title'], 'seconds': a['seconds'], 'bytes': len(audio), 'sha256': hashlib.sha256(audio).hexdigest()})
(ROOT / 'docs/runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert job['state'] == 'complete', job
assert len(report['audio']) == 4, 'Expected 3 chapters and combined FLAC'
line = 'Welcome back, Sam. The bridge is still standing.'
preview = api('/preview', {'text': line, 'voice': names['Sam']['voice']})
again = api('/preview', {'text': line, 'voice': names['Sam']['voice']})
other = api('/preview', {'text': line, 'voice': names['Mira']['voice']})
assert preview['url'] == again['url'] and again['generation_seconds'] == 0
assert preview['url'] != other['url']
report['cache_reuse_verified'] = True
report['voice_preview'] = preview
report['other_voice_preview'] = other
report['completed'] = time.strftime('%Y-%m-%d %H:%M:%S')
(ROOT / 'docs/runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'book_id': bid, 'mapping_seconds': report['mapping_seconds'], 'render_seconds': elapsed, 'audio': report['audio'], 'sam_return_correct': report['sam_return_correct'], 'ambiguity_flagged': report['ambiguity_flagged'], 'cache_reuse': True}), flush=True)
