"""Exact saved blend recipes; voice identity is never re-prompted each chapter."""
import hashlib
import json
import random
import threading
import time
import wave
from pathlib import Path

from .store import ROOT, DATA

MALE = ['am_adam', 'am_echo', 'am_eric', 'am_fenrir', 'am_liam', 'am_michael', 'am_onyx', 'am_puck', 'am_santa']
FEMALE = ['af_heart', 'af_bella', 'af_nicole', 'af_sarah', 'af_sky', 'af_nova', 'af_river', 'af_jessica']
BASES = MALE + FEMALE


def recipe(seed, profile='neutral'):
    rng = random.Random(seed)
    pool = MALE if profile == 'masculine' else FEMALE if profile == 'feminine' else BASES
    a, b = rng.sample(pool, 2)
    return {'engine': 'kokoro-v1.0', 'a': a, 'b': b, 'mix': round(rng.uniform(.2, .8), 4), 'speed': round(rng.uniform(.94, 1.06), 3), 'lang': 'en-us'}


def validate(v):
    if v.get('engine') != 'kokoro-v1.0' or v.get('a') not in BASES or v.get('b') not in BASES:
        raise ValueError('Unsupported voice recipe')
    if not 0 <= float(v['mix']) <= 1 or not .7 <= float(v['speed']) <= 1.3 or v.get('lang') != 'en-us':
        raise ValueError('Voice blend or speed is outside supported limits')
    return {**v, 'mix': float(v['mix']), 'speed': float(v['speed'])}


class SpeechEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.model = None
        self.fingerprint = None

    def unload(self):
        import gc
        with self.lock:
            self.model = None
            gc.collect()

    def ready(self):
        return all((ROOT / 'models' / f).exists() for f in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'))

    def load(self):
        if self.model is None:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            if not self.ready():
                raise ValueError('Speech models missing. Run Setup.cmd first.')
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            opts.inter_op_num_threads = 1
            session = ort.InferenceSession(str(ROOT / 'models/kokoro-v1.0.onnx'), sess_options=opts, providers=['CPUExecutionProvider'])
            self.model = Kokoro.from_session(session, str(ROOT / 'models/voices-v1.0.bin'))
            # Hash actual model bytes so replacing weights invalidates cached speech.
            digest = hashlib.sha256()
            for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
                with (ROOT / 'models' / name).open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''):
                        digest.update(chunk)
            self.fingerprint = digest.hexdigest()

    def render(self, text, voice):
        import numpy as np
        import soundfile as sf
        voice = validate(voice)
        with self.lock:
            self.load()
            key = hashlib.sha256(json.dumps([self.fingerprint, text, voice], sort_keys=True).encode()).hexdigest()
            dest = DATA / 'audio' / 'cache' / (key + '.wav')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                with wave.open(str(dest)) as w:
                    seconds = w.getnframes() / w.getframerate()
                return dest, seconds, 0.0
            start = time.perf_counter()
            blend = self.model.get_voice_style(voice['a']) * (1 - voice['mix']) + self.model.get_voice_style(voice['b']) * voice['mix']
            samples, sr = self.model.create(text, voice=blend, speed=voice['speed'], lang=voice['lang'])
            if len(samples) == 0 or not np.isfinite(samples).all():
                raise RuntimeError('Speech engine produced invalid audio')
            tmp = dest.with_suffix('.part')
            sf.write(str(tmp), samples, sr, format='WAV', subtype='PCM_16')
            tmp.replace(dest)
            return dest, len(samples) / sr, time.perf_counter() - start


def join_wavs(paths, dest, pause_seconds=.16):
    """Stream PCM to disk rather than loading a book into RAM. WAV is capped at 4 GB."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix('.part')
    frames = 0
    try:
        with wave.open(str(tmp), 'wb') as out:
            out.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            gap = b'\0\0' * int(24000 * pause_seconds)
            for i, path in enumerate(paths):
                with wave.open(str(path), 'rb') as inp:
                    if (inp.getnchannels(), inp.getsampwidth(), inp.getframerate()) != (1, 2, 24000):
                        raise ValueError('Incompatible audio format')
                    if (frames + inp.getnframes() + len(gap) // 2) * 2 > 4_000_000_000:
                        raise ValueError('Combined WAV exceeds 4 GB. Use the separate chapter exports.')
                    if i:
                        out.writeframesraw(gap)
                        frames += len(gap) // 2
                    for chunk in iter(lambda: inp.readframes(65536), b''):
                        out.writeframesraw(chunk)
                        frames += len(chunk) // 2
        tmp.replace(dest)
        return frames / 24000
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


speech = SpeechEngine()


def join_flac(paths, dest, pause_seconds=.7):
    """Stream a long book into lossless FLAC, avoiding WAV's 4 GB RIFF limit."""
    import numpy as np
    import soundfile as sf
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix('.part')
    frames = 0
    try:
        with sf.SoundFile(str(tmp), 'w', samplerate=24000, channels=1, format='FLAC', subtype='PCM_16') as out:
            for i, path in enumerate(paths):
                with sf.SoundFile(str(path)) as inp:
                    if inp.samplerate != 24000 or inp.channels != 1:
                        raise ValueError('Incompatible audio format')
                    if i:
                        gap = np.zeros(int(24000 * pause_seconds), dtype=np.int16)
                        out.write(gap)
                        frames += len(gap)
                    for block in inp.blocks(blocksize=65536, dtype='int16'):
                        out.write(block)
                        frames += len(block)
        tmp.replace(dest)
        return frames / 24000
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
