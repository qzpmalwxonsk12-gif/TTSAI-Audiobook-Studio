import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
import psutil
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from . import store
from .analysis import normalize, identity_index
from .text import chapter_parts, spans
from .voices import recipe, validate, BASES, speech
from .jobs import queue
from . import cloud
from . import usage


@asynccontextmanager
async def lifespan(app):
    store.init()
    queue.start()
    yield
    queue.close()


app = FastAPI(title='TTSAI · Audiobook Studio', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver', *filter(None, os.environ.get('TTSAI_HOSTS', '').split(','))])


@app.middleware('http')
async def local_only(request: Request, call_next):
    password = os.environ.get('TTSAI_PASSWORD', '')
    if password and request.url.path != '/health':
        import base64
        try:
            provided = base64.b64decode(request.headers.get('authorization', '').removeprefix('Basic '), validate=True).decode().split(':', 1)[1]
        except Exception:
            provided = ''
        if not secrets.compare_digest(provided, password):
            return JSONResponse({'detail': 'Sign in to your private studio.'}, status_code=401, headers={'WWW-Authenticate': 'Basic realm="TTSAI"'})
    origin = request.headers.get('origin')
    expected_origin = os.environ.get('TTSAI_PUBLIC_URL', str(request.base_url).rstrip('/'))
    if origin and origin != expected_origin:
        return JSONResponse({'detail': 'This local application does not accept cross-origin requests.'}, status_code=403)
    if request.method in ('POST', 'PUT', 'PATCH') and not request.headers.get('content-type', '').startswith('application/json'):
        return JSONResponse({'detail': 'JSON request required.'}, status_code=415)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; frame-ancestors 'none'"
    return response


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=400)


class ImportBook(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default='', max_length=10_000_000)


class JobRequest(BaseModel):
    type: Literal['map', 'render', 'listen']
    mode: Literal['full', 'dialogue'] = 'full'
    thoughts: bool = False
    allow_unresolved: bool = False
    chapter_id: str | None = None
    model: str = Field(default='qwen3:4b', min_length=1, max_length=100)
    mapping_provider: Literal['ollama', 'gemini'] = 'ollama'
    tts_provider: Literal['local', 'gemini', 'elevenlabs', 'hume', 'deepgram'] = 'local'
    max_cloud_requests: int = Field(default=60, ge=1, le=500)
    max_cloud_chars: int = Field(default=10000, ge=100, le=1000000)


class CharacterEdit(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    description: str = Field(default='', max_length=1500)
    voice: dict
    cloud_voice: dict | None = None


def save_character_cloud_voice(db, cid, body):
    if body is None:
        return
    provider = body.get('provider')
    if provider not in cloud.PROVIDERS:
        raise ValueError('Unknown speech provider')
    value = CloudVoice.model_validate(body)
    if provider == 'gemini' and value.voice_id not in {v[0] for v in cloud.GEMINI_VOICES}:
        raise ValueError('Choose a valid Gemini voice')
    if provider == 'deepgram' and value.voice_id not in {v['id'] for v in cloud.catalog(provider)}:
        raise ValueError('Choose a supported Deepgram voice')
    db.execute('INSERT INTO cloud_cast(character_id,provider,voice_id,direction,reason,pitch_semitones,speed) VALUES(?,?,?,?,?,?,?) ON CONFLICT(character_id,provider) DO UPDATE SET voice_id=excluded.voice_id,direction=excluded.direction,reason=excluded.reason,pitch_semitones=excluded.pitch_semitones,speed=excluded.speed',
               (cid, provider, value.voice_id, value.direction, 'Manually selected', value.pitch_semitones, value.speed))


class SegmentEdit(BaseModel):
    kind: Literal['dialogue', 'narration', 'thought']
    speaker: str | None = None
    needs_review: bool = False


class Preview(BaseModel):
    voice: dict
    text: str = Field(default='I told you the bridge would hold. Next time, try a little faith.', min_length=1, max_length=650)


class ChapterAdd(BaseModel):
    number: int = Field(ge=1, le=1000000)
    title: str = Field(default='', max_length=200)
    text: str = Field(min_length=1, max_length=1000000)


class Connection(BaseModel):
    key: str = Field(default='', max_length=500)


class CloudVoice(BaseModel):
    voice_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    direction: str = Field(default='', max_length=600)
    pitch_semitones: float = Field(default=0, ge=-3, le=3)
    speed: float = Field(default=1, ge=.7, le=1.5)


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/api/connections')
def connections():
    return {'connected': cloud.connections(), 'models': cloud.MODELS}


@app.put('/api/connections/{provider}')
def connection(provider: str, body: Connection):
    cloud.set_key(provider, body.key)
    return {'connected': cloud.connections()}


@app.get('/api/usage')
def api_usage(book_id: str | None = None):
    return usage.snapshot(book_id)


@app.get('/api/cloud-voices/{provider}')
def cloud_voices(provider: str):
    return cloud.catalog(provider)


@app.put('/api/characters/{cid}/cloud-voice/{provider}')
def edit_cloud_voice(cid: str, provider: str, body: CloudVoice):
    if provider not in cloud.PROVIDERS:
        raise ValueError('Unknown speech provider')
    if provider == 'gemini' and body.voice_id not in {v[0] for v in cloud.GEMINI_VOICES}:
        raise ValueError('Choose a valid Gemini voice')
    with store.connect() as db:
        row = db.execute('SELECT * FROM characters WHERE id=? AND merged_into IS NULL', (cid,)).fetchone()
        if not row:
            raise ValueError('Character not found')
        store.assert_idle(db, row['book_id'])
        save_character_cloud_voice(db, cid, {'provider': provider, **body.model_dump()})
        store.bump(db, row['book_id'])
    return {'ok': True}


class Merge(BaseModel):
    target_id: str


@app.get('/api/status')
def status():
    installed, error = [], None
    try:
        r = httpx.get('http://127.0.0.1:11435/api/tags', timeout=2)
        r.raise_for_status()
        installed = [m['name'] for m in r.json().get('models', [])]
    except Exception:
        error = 'Local speaker service is unavailable. Start the app using Start.cmd.'
    return {'speech_ready': speech.ready(), 'models': installed, 'analysis_error': error,
            'memory_available_gb': round(psutil.virtual_memory().available / 1024**3, 1),
            'voices': BASES, 'root': str(store.ROOT)}


@app.get('/api/books')
def books():
    with store.connect() as db:
        return store.rows(db, 'SELECT b.*, (SELECT COUNT(*) FROM chapters c WHERE c.book_id=b.id) AS chapters FROM books b ORDER BY created DESC')


@app.post('/api/books')
def import_book(body: ImportBook):
    if not body.title.strip():
        raise ValueError('Enter a book title.')
    bid = store.uid()
    source_dir = store.DATA / 'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / (bid + '.txt')).write_text(body.text, encoding='utf-8', newline='')
    with store.connect() as db:
        db.execute('INSERT INTO books(id,title) VALUES(?,?)', (bid, body.title.strip()))
        narrator_voice = recipe(bid + ':narrator', 'feminine')
        narrator_voice.update(a='af_heart', b='af_bella', mix=.15, speed=1.0)
        db.execute('INSERT INTO characters(id,book_id,name,voice) VALUES(?,?,?,?)',
                   (store.uid(), bid, 'Narrator', json.dumps(narrator_voice)))
        for i, (title, source) in enumerate(chapter_parts(body.text) if body.text.strip() else []):
            cid = store.uid()
            db.execute('INSERT INTO chapters(id,book_id,ordinal,title,source) VALUES(?,?,?,?,?)', (cid, bid, i + 1, title, source))
            for j, s in enumerate(spans(source)):
                db.execute('INSERT INTO segments(id,chapter_id,ordinal,start,end,text,kind) VALUES(?,?,?,?,?,?,?)',
                           (store.uid(), cid, j, s['start'], s['end'], s['text'], s['kind']))
    return {'id': bid}


@app.post('/api/books/{bid}/chapters')
def add_chapter(bid: str, body: ChapterAdd):
    if not body.text.strip():
        raise ValueError('Paste or upload the chapter text first.')
    with store.connect() as db:
        store.book(db, bid)
        store.assert_idle(db, bid)
        if db.execute('SELECT 1 FROM chapters WHERE book_id=? AND ordinal=?', (bid, body.number)).fetchone():
            raise ValueError('That chapter number already exists. Choose a different number.')
        cid = store.uid()
        title = body.title.strip() or f'Chapter {body.number}'
        db.execute('INSERT INTO chapters(id,book_id,ordinal,title,source) VALUES(?,?,?,?,?)', (cid, bid, body.number, title, body.text))
        for i, s in enumerate(spans(body.text)):
            db.execute('INSERT INTO segments(id,chapter_id,ordinal,start,end,text,kind) VALUES(?,?,?,?,?,?,?)',
                       (store.uid(), cid, i, s['start'], s['end'], s['text'], s['kind']))
        store.bump(db, bid)
    return {'id': cid}


@app.get('/api/books/{bid}')
def get_book(bid: str):
    with store.connect() as db:
        result = store.book(db, bid)
        result['settings'] = json.loads(result['settings'])
        result['chapters'] = store.rows(db, '''SELECT c.id,c.ordinal,c.title,c.mapped,
            COUNT(s.id) AS passages, COALESCE(SUM(s.review),0) AS review_count
            FROM chapters c LEFT JOIN segments s ON s.chapter_id=c.id WHERE c.book_id=?
            GROUP BY c.id ORDER BY c.ordinal''', (bid,))
        result['cast'] = store.cast(db, bid)
        result['jobs'] = store.rows(db, 'SELECT * FROM jobs WHERE book_id=? ORDER BY created DESC,rowid DESC LIMIT 30', (bid,))
        result['artifacts'] = store.rows(db, '''SELECT a.*,c.title AS chapter_title,j.options AS job_options FROM artifacts a JOIN jobs j ON j.id=a.job_id
            LEFT JOIN chapters c ON c.id=a.chapter_id WHERE j.book_id=? ORDER BY a.created DESC''', (bid,))
        for a in result['artifacts']:
            a['mode'] = json.loads(a.pop('job_options')).get('mode', 'full')
            a['format'] = Path(a['path']).suffix[1:].upper()
            a['stale'] = a['revision'] != result['revision']
            a.pop('path')
        return result


@app.get('/api/chapters/{cid}')
def chapter(cid: str):
    with store.connect() as db:
        r = db.execute('SELECT * FROM chapters WHERE id=?', (cid,)).fetchone()
        if not r:
            raise ValueError('Chapter not found')
        return {**dict(r), 'segments': store.rows(db, 'SELECT * FROM segments WHERE chapter_id=? ORDER BY ordinal', (cid,))}


@app.post('/api/books/{bid}/jobs')
def start_job(bid: str, body: JobRequest):
    if body.mapping_provider == 'gemini':
        cloud.key('gemini')
        if body.model not in cloud.MODELS:
            raise ValueError('Choose a supported Gemini model')
    if body.tts_provider != 'local':
        cloud.key(body.tts_provider)
        if body.mapping_provider != 'gemini':
            raise ValueError('Cloud casting requires Gemini mapping.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        store.book(db, bid)
        store.assert_idle(db, bid)
        if not db.execute('SELECT 1 FROM chapters WHERE book_id=?', (bid,)).fetchone():
            raise ValueError('Add a chapter before starting mapping.')
        if body.chapter_id and not db.execute('SELECT 1 FROM chapters WHERE id=? AND book_id=?', (body.chapter_id, bid)).fetchone():
            raise ValueError('Chapter does not belong to this book')
        jid = store.uid()
        db.execute('INSERT INTO jobs(id,book_id,type,options,state) VALUES(?,?,?,?,?)',
                   (jid, bid, body.type, body.model_dump_json(), 'queued'))
        db.execute('UPDATE books SET settings=? WHERE id=?', (body.model_dump_json(exclude={'type','chapter_id'}), bid))
    queue.wake.set()
    return {'id': jid}


@app.post('/api/jobs/{jid}/{action}')
def job_action(jid: str, action: str):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
        if not row:
            raise ValueError('Job not found')
        if action == 'pause':
            if row['state'] == 'queued':
                db.execute("UPDATE jobs SET state='paused',pause=0 WHERE id=?", (jid,))
            elif row['state'] == 'running':
                db.execute('UPDATE jobs SET pause=1 WHERE id=?', (jid,))
            else:
                raise ValueError('This job is not running')
        elif action == 'resume':
            if row['state'] not in ('paused', 'needs_review'):
                raise ValueError('Only paused or review-blocked jobs can resume. Start a new attempt after a failure; saved progress is reused.')
            store.assert_idle(db, row['book_id'])
            db.execute("UPDATE jobs SET state='queued',pause=0 WHERE id=?", (jid,))
        else:
            raise ValueError('Unknown job action')
    queue.wake.set()
    return {'ok': True}


@app.post('/api/books/{bid}/characters')
def add_character(bid: str, body: CharacterEdit):
    with store.connect() as db:
        store.book(db, bid)
        store.assert_idle(db, bid)
        if normalize(body.name) in identity_index(store.cast(db, bid)):
            raise ValueError('A character already uses that name or alias')
        cid = store.uid()
        db.execute('INSERT INTO characters(id,book_id,name,aliases,description,voice) VALUES(?,?,?,?,?,?)',
                   (cid, bid, body.name.strip(), json.dumps(body.aliases), body.description, json.dumps(validate(body.voice))))
        save_character_cloud_voice(db, cid, body.cloud_voice)
        store.bump(db, bid)
    return {'id': cid}


@app.put('/api/characters/{cid}')
def edit_character(cid: str, body: CharacterEdit):
    with store.connect() as db:
        c = db.execute('SELECT * FROM characters WHERE id=? AND merged_into IS NULL', (cid,)).fetchone()
        if not c:
            raise ValueError('Character not found')
        store.assert_idle(db, c['book_id'])
        if c['name'] == 'Narrator' and body.name != 'Narrator':
            raise ValueError('The narrator identity cannot be renamed')
        others = [x for x in store.cast(db, c['book_id']) if x['id'] != cid]
        index = identity_index(others)
        if any(normalize(n) in index for n in [body.name, *body.aliases]):
            raise ValueError('Another character uses this name or alias. Merge duplicates or resolve the conflict first.')
        if not body.name.strip():
            raise ValueError('Character name is required')
        db.execute('UPDATE characters SET name=?,aliases=?,description=?,voice=? WHERE id=?',
                   (body.name.strip(), json.dumps(body.aliases), body.description, json.dumps(validate(body.voice)), cid))
        save_character_cloud_voice(db, cid, body.cloud_voice)
        store.bump(db, c['book_id'])
    return {'ok': True}


@app.post('/api/characters/{cid}/merge')
def merge_character(cid: str, body: Merge):
    with store.connect() as db:
        source = db.execute('SELECT * FROM characters WHERE id=? AND merged_into IS NULL', (cid,)).fetchone()
        target = db.execute('SELECT * FROM characters WHERE id=? AND merged_into IS NULL', (body.target_id,)).fetchone()
        if not source or not target or source['book_id'] != target['book_id'] or cid == body.target_id:
            raise ValueError('Choose two different characters from the same book')
        if 'Narrator' in (source['name'], target['name']):
            raise ValueError('The narrator cannot be merged')
        store.assert_idle(db, source['book_id'])
        aliases = list(dict.fromkeys(json.loads(target['aliases']) + [source['name']] + json.loads(source['aliases'])))
        db.execute('UPDATE characters SET aliases=? WHERE id=?', (json.dumps(aliases), body.target_id))
        db.execute('UPDATE characters SET merged_into=? WHERE id=?', (body.target_id, cid))
        db.execute('UPDATE segments SET speaker=? WHERE speaker=?', (body.target_id, cid))
        store.bump(db, source['book_id'])
    return {'ok': True}


@app.put('/api/segments/{sid}')
def edit_segment(sid: str, body: SegmentEdit):
    with store.connect() as db:
        row = db.execute('SELECT s.*,c.book_id FROM segments s JOIN chapters c ON c.id=s.chapter_id WHERE s.id=?', (sid,)).fetchone()
        if not row:
            raise ValueError('Passage not found')
        store.assert_idle(db, row['book_id'])
        if body.kind != 'narration':
            if (not body.speaker and not body.needs_review) or (body.speaker and not db.execute('SELECT 1 FROM characters WHERE id=? AND book_id=? AND merged_into IS NULL', (body.speaker, row['book_id'])).fetchone()):
                raise ValueError('Choose a speaker for dialogue or internal thought')
        db.execute('UPDATE segments SET kind=?,speaker=?,review=?,locked=1,mapped=1,confidence=1,reason=? WHERE id=?',
                   (body.kind, body.speaker if body.kind != 'narration' else None, int(body.needs_review), 'Flagged for another review' if body.needs_review else 'Manually reviewed', sid))
        store.bump(db, row['book_id'])
    return {'ok': True}


@app.post('/api/preview')
def preview(body: Preview):
    if body.voice.get('provider') in cloud.PROVIDERS:
        v = CloudVoice.model_validate(body.voice)
        path, seconds, wall = cloud.render(body.text, {'provider': body.voice['provider'], **v.model_dump()}, {'max_cloud_chars':5000,'max_cloud_requests':15})
    else:
        path, seconds, wall = speech.render(body.text, body.voice)
    return {'url': '/api/audio/cache/' + path.name, 'seconds': seconds, 'generation_seconds': wall}


@app.get('/api/audio/cache/{name}')
def cached_audio(name: str):
    if len(name) != 68 or not name.endswith('.wav') or any(c not in '0123456789abcdef' for c in name[:-4]):
        raise ValueError('Invalid audio identifier')
    path = store.DATA / 'audio/cache' / name
    if not path.exists():
        raise ValueError('Audio not found')
    return FileResponse(path, media_type='audio/wav')


@app.get('/api/artifacts/{aid}')
def artifact(aid: str, download: bool = False):
    with store.connect() as db:
        a = db.execute('SELECT * FROM artifacts WHERE id=?', (aid,)).fetchone()
    if not a:
        raise ValueError('Export not found')
    path = (store.DATA / a['path']).resolve()
    if not path.is_relative_to(store.DATA.resolve()) or not path.is_file():
        raise ValueError('Export file missing')
    return FileResponse(path, media_type='audio/flac' if path.suffix == '.flac' else 'audio/wav', filename=path.name if download else None)


@app.get('/api/artifacts/{aid}/timeline')
def artifact_timeline(aid: str):
    with store.connect() as db:
        a = db.execute('SELECT a.*,j.book_id FROM artifacts a JOIN jobs j ON j.id=a.job_id WHERE a.id=?', (aid,)).fetchone()
        if not a:
            raise ValueError('Audio not found')
        stale = store.book(db, a['book_id'])['revision'] != a['revision']
    path = (store.DATA / a['path']).resolve()
    if not path.is_relative_to(store.DATA.resolve()):
        raise ValueError('Invalid audio path')
    manifest = path.with_suffix('.json')
    return {'stale': stale, 'segments': json.loads(manifest.read_text(encoding='utf-8')).get('timeline', []) if manifest.exists() else []}


@app.get('/api/books/{bid}/project')
def project_export(bid: str):
    with store.connect() as db:
        result = store.book(db, bid)
        original = store.DATA / 'sources' / (bid + '.txt')
        result['original_text'] = None
        if original.exists():
            with original.open(encoding='utf-8', newline='') as source_file:
                result['original_text'] = source_file.read()
        result['cast'] = store.cast(db, bid)
        result['chapters'] = store.rows(db, 'SELECT * FROM chapters WHERE book_id=? ORDER BY ordinal', (bid,))
        for c in result['chapters']:
            c['segments'] = store.rows(db, 'SELECT * FROM segments WHERE chapter_id=? ORDER BY ordinal', (c['id'],))
    return JSONResponse(result, headers={'Content-Disposition': 'attachment; filename="book-project.json"'})


@app.get('/api/sample')
def sample():
    return {'title': 'The Bridge at Dawn · original test story', 'text': (store.ROOT / 'samples/bridge.txt').read_text(encoding='utf-8')}


app.mount('/', StaticFiles(directory=store.ROOT / 'static', html=True), name='ui')
