"""Isolated UI acceptance server with synthetic provider responses; never production inference."""
import json
import os
from pathlib import Path
import sys
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if not os.environ.get('TTSAI_DATA') or Path(os.environ['TTSAI_DATA']).resolve()==Path(__file__).resolve().parents[1]/'data':
    raise SystemExit('An isolated TTSAI_DATA directory is required.')
from app import cloud,store
from app.main import app

cloud._keys={'gemini':'synthetic-test-key'}
def json_response(model,instruction,payload,*args):
    if 'available_voices' in payload:
        return json.dumps({'voices':[{'character_id':c['id'],'voice_id':'Kore' if c['name']=='Narrator' else 'Leda',
             'direction':'Clear and natural','reason':'Synthetic test casting'} for c in payload['characters']]})
    return json.dumps({'characters':[{'name':'Mira','aliases':[],'description':'A woman with a clear voice','profile':'feminine'}],
        'labels':[{'id':s['id'],'kind':'dialogue' if '“' in s['text'] else 'narration',
        'speaker': 'Mira' if '“' in s['text'] and 'Who' not in s['text'] else None,
        'confidence':.4 if 'Who' in s['text'] else 1,'reason':'Synthetic test attribution'} for s in payload['segments']]})
cloud.gemini_json=json_response
def render(text,voice,options,*args):
    path=store.DATA/'audio/cache'/(store.uid()+'.wav');path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*12000)
    return path,.5,.01
cloud.render=render
