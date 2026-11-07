"""Single-user hosted entry point. Never start a public studio without authentication."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if not os.environ.get('TTSAI_PASSWORD'):
    raise SystemExit('Set TTSAI_PASSWORD before launching the hosted studio.')
hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if hostname:
    os.environ.setdefault('TTSAI_HOSTS', hostname)
    os.environ.setdefault('TTSAI_PUBLIC_URL', 'https://' + hostname)
if not os.environ.get('TTSAI_PUBLIC_URL') or not os.environ.get('TTSAI_HOSTS'):
    raise SystemExit('Set TTSAI_HOSTS and TTSAI_PUBLIC_URL for this deployment.')
import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', '8767')), workers=1)
