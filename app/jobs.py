"""Single-worker, resumable production queue with per-segment audio caching."""
import json
import threading
import time
import traceback

from . import store
from .analysis import OllamaAnalyzer, save_mapping, apply_source_evidence
from .text import batches
from .voices import speech, join_wavs, join_flac
from . import cloud


class Paused(Exception):
    pass


class ReviewNeeded(Exception):
    pass


class Queue:
    def __init__(self):
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        self.stop.clear()
        self.thread = threading.Thread(target=self.run, daemon=True, name='audiobook-worker')
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()

    def checkpoint(self, job_id, message=None, completed=None, total=None):
        with store.connect() as db:
            job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not job or job['pause'] or self.stop.is_set():
                raise Paused()
            for key, value in [('message', message), ('completed', completed), ('total', total)]:
                if value is not None:
                    db.execute(f'UPDATE jobs SET {key}=?,updated=CURRENT_TIMESTAMP WHERE id=?', (value, job_id))

    def run(self):
        while not self.stop.is_set():
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                job = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created,rowid LIMIT 1").fetchone()
                if job:
                    job = dict(job)
                    db.execute("UPDATE jobs SET state='running',updated=CURRENT_TIMESTAMP WHERE id=?", (job['id'],))
            if not job:
                self.wake.wait(1)
                self.wake.clear()
                continue
            try:
                self.process(job)
                state, message = 'complete', 'Finished. Audio and progress are saved locally.'
            except Paused:
                state, message = 'paused', 'Paused at a safe checkpoint. Resume to continue.'
            except ReviewNeeded as exc:
                state, message = 'needs_review', str(exc)
            except cloud.ProviderError as exc:
                state, message = 'failed', str(exc)
            except Exception as exc:
                state, message = 'failed', f'{type(exc).__name__}: {exc}'
                traceback.print_exc()
            with store.connect() as db:
                db.execute('UPDATE jobs SET state=?,message=?,updated=CURRENT_TIMESTAMP WHERE id=?', (state, message, job['id']))

    def map_chapter(self, job, chapter, options, all_chapters):
        with store.connect() as db:
            segments = store.rows(db, 'SELECT * FROM segments WHERE chapter_id=? AND mapped=0 AND locked=0 ORDER BY ordinal', (chapter['id'],))
        for batch in batches(segments):
            self.checkpoint(job['id'], 'Identifying speakers · ' + chapter['title'])
            a = max(0, batch[0]['start'] - 1600)
            b = min(len(chapter['source']), batch[-1]['end'] + 4000)
            idx = next(i for i, c in enumerate(all_chapters) if c['id'] == chapter['id'])
            context = chapter['source'][a:b]
            if b == len(chapter['source']) and idx + 1 < len(all_chapters):
                context += '\nNEXT CHAPTER:\n' + all_chapters[idx + 1]['source'][:2500]
            if a == 0 and idx:
                context = all_chapters[idx - 1]['source'][-1200:] + '\nCURRENT CHAPTER:\n' + context
            with store.connect() as db:
                cast = store.cast(db, job['book_id'])
            if options.get('mapping_provider') == 'gemini':
                result = cloud.GeminiAnalyzer(options['model'], job['id'], options).analyze(batch, cast, context, checkpoint=lambda: self.checkpoint(job['id']))
            else:
                with speech.lock:
                    speech.unload()
                    result = OllamaAnalyzer(options.get('model', 'qwen3:4b')).analyze(batch, cast, context, checkpoint=lambda: self.checkpoint(job['id']))
            self.checkpoint(job['id'])
            with store.connect() as db:
                save_mapping(db, job['book_id'], chapter['id'], batch, result, options.get('model', 'qwen3:4b'))
                apply_source_evidence(db, job['book_id'], chapter['id'], batch, chapter['source'])
        with store.connect() as db:
            db.execute('UPDATE chapters SET mapped=1 WHERE id=?', (chapter['id'],))

    def render_chapter(self, job, chapter, options):
        with store.connect() as db:
            segments = store.rows(db, 'SELECT * FROM segments WHERE chapter_id=? ORDER BY ordinal', (chapter['id'],))
            cast = {c['id']: c for c in store.cast(db, job['book_id'])}
            revision = store.book(db, job['book_id'])['revision']
        if any(not s['mapped'] for s in segments):
            raise ReviewNeeded('Map this chapter first. Unmapped source text cannot be silently exported.')
        selected = [s for s in segments if (s['kind'] != 'thought' or options.get('thoughts', False)) and (options.get('mode', 'full') == 'full' or s['kind'] in ('dialogue', 'thought'))]
        if not selected:
            return None
        if any(s['review'] for s in selected) and not options.get('allow_unresolved', False):
            raise ReviewNeeded('Review flagged passages, then resume. Alternatively start a new job with narrator fallback explicitly enabled.')
        narrator = next(c for c in cast.values() if c['name'] == 'Narrator')
        paths, duration, compute, timeline = [], 0.0, 0.0, []
        provider = options.get('tts_provider', 'local')
        if provider != 'local' and any(provider not in c['cloud_voices'] for c in cast.values()):
            raise ReviewNeeded('Run Step 1 to assign voices for this provider before producing audio.')
        for i, s in enumerate(selected):
            self.checkpoint(job['id'], f"Speaking · {chapter['title']} · passage {i+1}/{len(selected)}")
            person = cast.get(s['speaker'], narrator)
            if s['review'] and options.get('allow_unresolved', False):
                person = narrator
            if provider == 'local':
                path, seconds, wall = speech.render(s['text'], person['voice'])
            else:
                path, seconds, wall = cloud.render(s['text'], person['cloud_voices'][provider], options,
                                                   lambda: self.checkpoint(job['id']), job['id'])
            paths.append(path)
            if i:
                duration += .16
            timeline.append({'id': s['id'], 'chapter_id': chapter['id'], 'start': duration, 'end': duration+seconds,
                             'speaker': person['id'], 'kind': s['kind']})
            duration += seconds
            compute += wall
        self.checkpoint(job['id'])
        out = store.DATA / 'audio' / 'exports' / job['id'] / f"{chapter['ordinal']:04d}-{chapter['id'][:8]}-{store.uid()[:8]}.wav"
        seconds = join_wavs(paths, out)
        # Human-readable production manifest supports attribution corrections and future video tools.
        manifest = {'chapter': chapter['title'], 'revision': revision, 'audio_seconds': seconds, 'timeline': timeline,
                    'uncached_generation_seconds': compute, 'options': options,
                    'segments': [{'id': s['id'], 'speaker': s['speaker'], 'review': bool(s['review']), 'text': s['text']} for s in selected],
                    'cast': list(cast.values())}
        out.with_suffix('.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        with store.connect() as db:
            db.execute('INSERT INTO artifacts(id,job_id,chapter_id,path,seconds,revision) VALUES(?,?,?,?,?,?)',
                       (store.uid(), job['id'], chapter['id'], str(out.relative_to(store.DATA)), seconds, revision))
        return out

    def process(self, job):
        options = json.loads(job['options'])
        with store.connect() as db:
            all_chapters = store.rows(db, 'SELECT * FROM chapters WHERE book_id=? ORDER BY ordinal', (job['book_id'],))
        chapters = [c for c in all_chapters if not options.get('chapter_id') or c['id'] == options['chapter_id']]
        if not chapters:
            raise ValueError('No chapters selected')
        # Full-book mapping and rendering are distinct jobs, creating a cast-review gate.
        self.checkpoint(job['id'], completed=0, total=len(chapters))
        paths = []
        for i, chapter in enumerate(chapters):
            self.checkpoint(job['id'], completed=i)
            if job['type'] in ('map', 'listen'):
                self.map_chapter(job, chapter, options, all_chapters)
                if options.get('tts_provider', 'local') != 'local':
                    self.checkpoint(job['id'], 'Choosing persistent character voices')
                    cloud.cast_book(job, options, lambda: self.checkpoint(job['id']))
            if job['type'] in ('render', 'listen'):
                path = self.render_chapter(job, chapter, options)
                if path:
                    paths.append(path)
            self.checkpoint(job['id'], completed=i + 1)
        if paths and job['type'] in ('render', 'listen'):
            self.checkpoint(job['id'], 'Assembling audiobook')
            out = store.DATA / 'audio' / 'exports' / job['id'] / ('audiobook-' + store.uid()[:8] + '.flac')
            seconds = join_flac(paths, out, pause_seconds=.7)
            timeline, offset = [], 0.0
            for i, path in enumerate(paths):
                manifest = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
                if i:
                    offset += .7
                timeline.extend({**s, 'start': s['start']+offset, 'end': s['end']+offset} for s in manifest['timeline'])
                offset += manifest['audio_seconds']
            out.with_suffix('.json').write_text(json.dumps({'timeline': timeline, 'audio_seconds': seconds}), encoding='utf-8')
            with store.connect() as db:
                rev = store.book(db, job['book_id'])['revision']
                # Only this run's chapter exports can be promoted after listen-mode mapping.
                # Earlier exports from a resumed job retain their original revision.
                for path in paths:
                    db.execute('UPDATE artifacts SET revision=? WHERE job_id=? AND path=?', (rev, job['id'], str(path.relative_to(store.DATA))))
                db.execute('INSERT INTO artifacts(id,job_id,path,seconds,revision) VALUES(?,?,?,?,?)',
                           (store.uid(), job['id'], str(out.relative_to(store.DATA)), seconds, rev))


queue = Queue()
