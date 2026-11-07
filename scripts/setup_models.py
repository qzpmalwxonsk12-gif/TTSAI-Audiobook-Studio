import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
models = ROOT / 'models'
models.mkdir(exist_ok=True)
manifest = {}
for name in ['kokoro-v1.0.onnx', 'voices-v1.0.bin']:
    dest = models / name
    url = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/' + name
    if not dest.exists():
        print('Downloading', name, flush=True)
        urllib.request.urlretrieve(url, str(dest) + '.part')
        Path(str(dest) + '.part').replace(dest)
    manifest[name] = {'url': url, 'bytes': dest.stat().st_size, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
    print(name, manifest[name], flush=True)
(models / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11435', OLLAMA_MODELS=str(models / 'ollama'), OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1')
log = (models / 'ollama.log').open('a')
try:
    urllib.request.urlopen('http://127.0.0.1:11435/api/tags', timeout=2)
except Exception:
    subprocess.Popen(['ollama', 'serve'], env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(30):
        try:
            urllib.request.urlopen('http://127.0.0.1:11435/api/tags', timeout=2)
            break
        except Exception:
            time.sleep(1)
req = urllib.request.Request('http://127.0.0.1:11435/api/pull', data=json.dumps({'model': 'qwen3:4b', 'stream': True}).encode(), headers={'Content-Type': 'application/json'})
last = ''
with urllib.request.urlopen(req, timeout=600) as response:
    for line in response:
        event = json.loads(line)
        if 'error' in event:
            raise RuntimeError(event['error'])
        status = event.get('status', '')
        if event.get('total'):
            status += ' ' + str(int(event.get('completed', 0) / event['total'] * 10) * 10) + '%'
        if status != last:
            print(status, flush=True)
            last = status
