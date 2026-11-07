"""Portable Windows launcher: separate local model server, loopback web app."""
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ.setdefault('HF_HOME', str(ROOT / 'models' / 'huggingface'))
os.environ.setdefault('OMP_NUM_THREADS', '4')


def alive(url):
    try:
        return urllib.request.urlopen(url, timeout=2).status == 200
    except Exception:
        return False


if __name__ == '__main__':
    if alive('http://127.0.0.1:8767/health'):
        webbrowser.open('http://127.0.0.1:8767')
        raise SystemExit(0)
    if os.environ.get('TTSAI_LOCAL_ENGINES') == '1' and not alive('http://127.0.0.1:11435/api/tags') and shutil.which('ollama'):
        (ROOT / 'models').mkdir(exist_ok=True)
        env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11435', OLLAMA_MODELS=str(ROOT / 'models/ollama'),
                   OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1')
        log = (ROOT / 'models/ollama.log').open('a')
        subprocess.Popen(['ollama', 'serve'], env=env, stdout=log, stderr=log,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    def open_ready():
        for _ in range(30):
            if alive('http://127.0.0.1:8767/health'):
                webbrowser.open('http://127.0.0.1:8767')
                return
            time.sleep(1)
    threading.Thread(target=open_ready, daemon=True).start()
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8767, workers=1)
