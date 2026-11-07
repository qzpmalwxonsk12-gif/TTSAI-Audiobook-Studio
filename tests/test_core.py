import json
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import store
from app import voices
from app.analysis import Mapping, Label, Person, save_mapping
from app.main import app
from app.jobs import queue, Queue, ReviewNeeded, Paused
from app.text import spans, chapter_parts


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.setattr(voices, 'DATA', tmp_path)
    monkeypatch.setattr(queue, 'start', lambda: None)
    monkeypatch.setattr(queue, 'close', lambda: None)
    with TestClient(app) as c:
        yield c


def make_book(c, text='Chapter 1\n"Hello," Sam said.\nChapter 72\n"Back again," Sam said.'):
    bid = c.post('/api/books', json={'title': 'Test', 'text': text}).json()['id']
    return c.get('/api/books/' + bid).json()


def person(c, b, name='Sam'):
    data = {'name': name, 'aliases': [], 'description': '', 'voice': voices.recipe(name)}
    return c.post('/api/books/' + b['id'] + '/characters', json=data).json()['id']


def test_source_spans_preserve_unicode_and_order():
    source = '  “Don’t move,” Sam said.\nShe waited. "Why?"\n' + 'Long sentence ' * 100
    parts = spans(source)
    assert all(source[s['start']:s['end']] == s['text'] for s in parts)
    assert all(a['end'] <= b['start'] for a, b in zip(parts, parts[1:]))
    assert ''.join(''.join(s['text'].split()) for s in parts) == ''.join(source.split())
    assert max(len(s['text']) for s in parts) <= 650


def test_chapter_split_preserves_preface():
    parts = chapter_parts('Preface\nChapter 1 — Start\nHello\nChapter 72 — End\nGoodbye')
    assert [p[0] for p in parts] == ['Prologue', 'Chapter 1 — Start', 'Chapter 72 — End']


def test_cross_book_speaker_rejected(client):
    a, b = make_book(client), make_book(client)
    cid = person(client, b)
    chapter = client.get('/api/chapters/' + a['chapters'][0]['id']).json()
    sid = chapter['segments'][0]['id']
    assert client.put('/api/segments/' + sid, json={'kind': 'dialogue', 'speaker': cid}).status_code == 400


def test_cast_merge_keeps_target_voice_and_references(client):
    b = make_book(client)
    sam = person(client, b)
    stranger = person(client, b, 'The swordsman')
    s = client.get('/api/chapters/' + b['chapters'][0]['id']).json()['segments'][0]
    client.put('/api/segments/' + s['id'], json={'kind': 'dialogue', 'speaker': stranger})
    before = next(c for c in client.get('/api/books/' + b['id']).json()['cast'] if c['id'] == sam)['voice']
    assert client.post('/api/characters/' + stranger + '/merge', json={'target_id': sam}).status_code == 200
    after = client.get('/api/books/' + b['id']).json()['cast']
    assert next(c for c in after if c['id'] == sam)['voice'] == before
    assert all(c['id'] != stranger for c in after)
    assert client.get('/api/chapters/' + b['chapters'][0]['id']).json()['segments'][0]['speaker'] == sam


def test_locked_correction_survives_analysis_and_restart(client):
    b = make_book(client)
    sam = person(client, b)
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    s = ch['segments'][0]
    client.put('/api/segments/' + s['id'], json={'kind': 'dialogue', 'speaker': sam})
    mapping = Mapping(characters=[], labels=[Label(id=s['id'], kind='narration', speaker=None, confidence=.9, reason='Wrong model answer')])
    with store.connect() as db:
        save_mapping(db, b['id'], ch['id'], [s], mapping, 'test')
        before = store.cast(db, b['id'])
    store.init()
    with store.connect() as db:
        assert store.cast(db, b['id']) == before
        row = db.execute('SELECT * FROM segments WHERE id=?', (s['id'],)).fetchone()
        assert row['speaker'] == sam and row['locked'] == 1 and row['kind'] == 'dialogue'


def test_ambiguous_alias_never_picks_random_person(client):
    b = make_book(client)
    person(client, b, 'Sam')
    person(client, b, 'Rao')
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    s = ch['segments'][0]
    mapping = Mapping(characters=[Person(name='Sam', aliases=['captain'], profile='neutral'), Person(name='Rao', aliases=['captain'], profile='neutral')],
                      labels=[Label(id=s['id'], kind='dialogue', speaker='captain', confidence=.99, reason='Alias')])
    with store.connect() as db:
        save_mapping(db, b['id'], ch['id'], [s], mapping, 'test')
        row = db.execute('SELECT * FROM segments WHERE id=?', (s['id'],)).fetchone()
        assert row['speaker'] is None and row['review'] == 1


def test_interrupted_jobs_resume_as_paused(client):
    b = make_book(client)
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'map'}).json()['id']
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (jid,))
    store.init()
    with store.connect() as db:
        assert db.execute('SELECT state FROM jobs WHERE id=?', (jid,)).fetchone()[0] == 'paused'
    assert client.post('/api/jobs/' + jid + '/resume', json={}).status_code == 200


def test_active_job_blocks_mutation(client):
    b = make_book(client)
    client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'map'})
    r = client.post('/api/books/' + b['id'] + '/characters',
                    json={'name': 'Sam', 'voice': voices.recipe('sam')})
    assert r.status_code == 400
    assert client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'map'}).status_code == 400


def test_render_review_gate_and_dialogue_filter(client, monkeypatch, tmp_path):
    b = make_book(client, 'Chapter 1\n"Hello," Sam said.')
    sam = person(client, b)
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    with store.connect() as db:
        db.execute('UPDATE segments SET mapped=1 WHERE chapter_id=?', (ch['id'],))
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'render'}).json()['id']
    with store.connect() as db:
        job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone())
    worker = Queue()
    with pytest.raises(ReviewNeeded):
        worker.render_chapter(job, ch, {})
    with store.connect() as db:
        db.execute('UPDATE segments SET review=0,speaker=? WHERE chapter_id=? AND kind=?', (sam, ch['id'], 'dialogue'))
    spoken = []
    def fake_render(text, voice):
        spoken.append(text)
        path = tmp_path / 'fake.wav'
        with wave.open(str(path), 'wb') as w:
            w.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            w.writeframes(b'\0\0' * 240)
        return path, .01, .01
    monkeypatch.setattr(voices.speech, 'render', fake_render)
    path = worker.render_chapter(job, ch, {'mode': 'dialogue'})
    assert spoken == ['"Hello,"']
    assert path.exists()


def test_pause_checkpoint_stops_before_next_passage(client):
    b = make_book(client)
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'map'}).json()['id']
    with store.connect() as db:
        db.execute('UPDATE jobs SET pause=1 WHERE id=?', (jid,))
    with pytest.raises(Paused):
        Queue().checkpoint(jid)


def test_origin_and_host_protection(client):
    assert client.post('/api/books', json={'title':'x','text':'x'}, headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/books', headers={'Host':'evil.example'}).status_code == 400


def test_voice_parameters_reject_invalid_values():
    v = voices.recipe('Sam')
    with pytest.raises(ValueError):
        voices.validate({**v, 'mix': float('nan')})
    with pytest.raises(ValueError):
        voices.validate({**v, 'a': 'missing_voice'})
    assert voices.recipe('Sam') == v


def test_original_import_is_exact_and_mapping_fields_are_required(client):
    source = '  Preface\r\nChapter 1\r\n“Do not rewrite me,” Sam said.  '
    b = make_book(client, source)
    with (store.DATA / 'sources' / (b['id'] + '.txt')).open(encoding='utf-8', newline='') as f:
        assert f.read() == source
    schema = Mapping.model_json_schema()
    assert 'characters' in schema['required']
    assert 'speaker' in schema['$defs']['Label']['required']


def test_combined_flac_is_lossless_and_streamable(tmp_path):
    import numpy as np
    import soundfile as sf
    from app.voices import join_flac
    pcm = np.arange(-1200, 1200, dtype=np.int16)
    src = tmp_path / 'chapter.wav'
    sf.write(src, pcm, 24000, subtype='PCM_16')
    out = tmp_path / 'book.flac'
    seconds = join_flac([src, src], out, pause_seconds=.1)
    actual, sr = sf.read(out, dtype='int16')
    assert sr == 24000 and seconds == pytest.approx(.3)
    assert np.array_equal(actual, np.concatenate([pcm, np.zeros(2400, dtype=np.int16), pcm]))


def test_direct_source_tags_override_model_guesses(client):
    from app.analysis import apply_source_evidence
    source = 'Roe, the captain who guarded the gate, returned.\n"Stay alert," the captain thought.'
    b = make_book(client, source)
    roe = person(client, b, 'Roe')
    wrong = person(client, b, 'Arden')
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    quote = next(s for s in ch['segments'] if s['kind'] == 'dialogue')
    with store.connect() as db:
        db.execute('UPDATE segments SET speaker=? WHERE id=?', (wrong, quote['id']))
        apply_source_evidence(db, b['id'], ch['id'], ch['segments'], ch['source'])
        s = db.execute('SELECT * FROM segments WHERE id=?', (quote['id'],)).fetchone()
        assert s['speaker'] == roe and s['kind'] == 'thought' and s['review'] == 0

def test_full_job_publishes_combined_artifact(client, monkeypatch, tmp_path):
    b = make_book(client, 'Chapter 1\nHello.')
    with store.connect() as db:
        db.execute('UPDATE segments SET mapped=1,review=0')
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type':'render'}).json()['id']
    with store.connect() as db:
        job = dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
    def fake_render(text, voice):
        path = tmp_path / 'voice.wav'
        with wave.open(str(path), 'wb') as w:
            w.setparams((1,2,24000,0,'NONE','not compressed'))
            w.writeframes(b'\0\0' * 240)
        return path,.01,.01
    monkeypatch.setattr(voices.speech, 'render', fake_render)
    Queue().process(job)
    artifacts = client.get('/api/books/' + b['id']).json()['artifacts']
    assert len(artifacts) == 2
    combined = next(a for a in artifacts if a['chapter_id'] is None)
    assert combined['format'] == 'FLAC'
    assert client.get('/api/artifacts/' + combined['id']).headers['content-type'] == 'audio/flac'


@pytest.mark.parametrize('returned', [['0','0'], ['0'], ['0','2']])
def test_analysis_rejects_missing_duplicate_or_foreign_ids(monkeypatch, returned):
    from app.analysis import OllamaAnalyzer
    import app.analysis as analysis
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'message': {'content': json.dumps({'characters': [], 'labels': [
                {'id': x, 'kind': 'narration', 'speaker': None, 'confidence': 1, 'reason': 'test'} for x in returned]})}}
    class LocalClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(analysis.httpx, 'AsyncClient', LocalClient)
    with pytest.raises(ValueError, match='omitted or duplicated'):
        OllamaAnalyzer().analyze([{'id':'long-a','text':'One.'},{'id':'long-b','text':'Two.'}],[],'')


def test_mapping_pipeline_applies_source_evidence(client, monkeypatch):
    import app.jobs as jobs
    from app.analysis import OllamaAnalyzer
    b = make_book(client, 'Chapter 1\n"Stay alert," Roe thought.')
    roe = person(client, b, 'Roe')
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type':'map'}).json()['id']
    with store.connect() as db:
        job = dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
    def predict(self, segments, cast, context, checkpoint=None):
        return Mapping(characters=[], labels=[Label(id=s['id'],kind=s['kind'],speaker=None,confidence=.9,reason='Model omitted identity') for s in segments])
    monkeypatch.setattr(OllamaAnalyzer, 'analyze', predict)
    Queue().map_chapter(job, ch, {}, [ch])
    updated=client.get('/api/chapters/' + ch['id']).json()
    quote=next(s for s in updated['segments'] if 'Stay alert' in s['text'])
    assert quote['speaker']==roe and quote['kind']=='thought' and quote['review']==0


def test_mapping_pause_cancels_inflight_request_without_saving(client, monkeypatch):
    import asyncio
    import time
    import app.analysis as analysis
    started, cancelled = [], []
    b = make_book(client, 'Chapter 1\n"Wait," Roe said.')
    ch = client.get('/api/chapters/' + b['chapters'][0]['id']).json()
    jid = client.post('/api/books/' + b['id'] + '/jobs', json={'type': 'map'}).json()['id']
    with store.connect() as db:
        job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone())
    class LocalClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            started.append(True)
            with store.connect() as db:
                db.execute('UPDATE jobs SET pause=1 WHERE id=?', (jid,))
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)
    monkeypatch.setattr(analysis.httpx, 'AsyncClient', LocalClient)
    before = time.monotonic()
    from app.jobs import Paused
    with pytest.raises(Paused):
        Queue().map_chapter(job, ch, {}, [ch])
    assert time.monotonic() - before < 2
    assert started and cancelled
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM analysis_log').fetchone()[0] == 0
        assert db.execute('SELECT SUM(mapped) FROM segments WHERE chapter_id=?', (ch['id'],)).fetchone()[0] == 0
    assert client.post('/api/jobs/' + jid + '/pause', json={}).status_code == 200
    assert client.post('/api/jobs/' + jid + '/resume', json={}).status_code == 200
