"""Book-scoped, transactional storage. Source text is immutable after import."""
import json
import os
from pathlib import Path
import sqlite3
import uuid

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('TTSAI_DATA', ROOT / 'data'))


def uid():
    return uuid.uuid4().hex


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'library.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS books(id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS chapters(id TEXT PRIMARY KEY, book_id TEXT REFERENCES books(id), ordinal INTEGER, title TEXT, source TEXT, mapped INTEGER DEFAULT 0, UNIQUE(book_id, ordinal));
        CREATE TABLE IF NOT EXISTS characters(id TEXT PRIMARY KEY, book_id TEXT REFERENCES books(id), name TEXT, aliases TEXT DEFAULT '[]', description TEXT DEFAULT '', voice TEXT, merged_into TEXT, UNIQUE(book_id,name));
        CREATE TABLE IF NOT EXISTS segments(id TEXT PRIMARY KEY, chapter_id TEXT REFERENCES chapters(id), ordinal INTEGER, start INTEGER, end INTEGER, text TEXT, kind TEXT, speaker TEXT REFERENCES characters(id), confidence REAL DEFAULT 0, review INTEGER DEFAULT 1, locked INTEGER DEFAULT 0, reason TEXT DEFAULT '', mapped INTEGER DEFAULT 0, UNIQUE(chapter_id,ordinal));
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, book_id TEXT REFERENCES books(id), type TEXT, options TEXT, state TEXT, message TEXT DEFAULT '', completed INTEGER DEFAULT 0, total INTEGER DEFAULT 0, pause INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP, updated TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id), chapter_id TEXT, path TEXT, seconds REAL, revision INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS analysis_log(id TEXT PRIMARY KEY, book_id TEXT, chapter_id TEXT, provider TEXT, payload TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS cloud_cast(character_id TEXT REFERENCES characters(id), provider TEXT, voice_id TEXT, direction TEXT DEFAULT '', reason TEXT DEFAULT '', PRIMARY KEY(character_id,provider));
        CREATE TABLE IF NOT EXISTS cloud_usage(scope TEXT, provider TEXT, chars INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(books)')}
        if 'settings' not in columns:
            db.execute("ALTER TABLE books ADD COLUMN settings TEXT DEFAULT '{}'")
        if 'voice_profile' not in {r['name'] for r in db.execute('PRAGMA table_info(characters)')}:
            db.execute("ALTER TABLE characters ADD COLUMN voice_profile TEXT DEFAULT 'neutral'")
        cast_columns = {r['name'] for r in db.execute('PRAGMA table_info(cloud_cast)')}
        for name, default in [('pitch_semitones', 0), ('speed', 1)]:
            if name not in cast_columns:
                db.execute(f'ALTER TABLE cloud_cast ADD COLUMN {name} REAL DEFAULT {default}')
        db.execute("UPDATE jobs SET state='paused', pause=0, message='Interrupted. Resume to continue from saved progress.' WHERE state IN ('running','queued')")


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


def book(db, book_id):
    r = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
    if not r:
        raise ValueError('Book not found')
    return dict(r)


def cast(db, book_id):
    result = rows(db, 'SELECT * FROM characters WHERE book_id=? AND merged_into IS NULL ORDER BY name', (book_id,))
    for r in result:
        r['aliases'] = json.loads(r['aliases'])
        r['voice'] = json.loads(r['voice'])
        r['cloud_voices'] = {v['provider']: v for v in rows(db, 'SELECT * FROM cloud_cast WHERE character_id=?', (r['id'],))}
    return result


def bump(db, book_id):
    db.execute('UPDATE books SET revision=revision+1 WHERE id=?', (book_id,))


def assert_idle(db, book_id):
    if db.execute("SELECT 1 FROM jobs WHERE book_id=? AND state IN ('queued','running')", (book_id,)).fetchone():
        raise ValueError('Pause the active job and wait for it to stop before editing this book.')
