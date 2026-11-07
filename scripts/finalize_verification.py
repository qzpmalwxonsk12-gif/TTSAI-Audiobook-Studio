import hashlib
import io
import json
from pathlib import Path
import sys
import time
import urllib.request
import numpy as np
import soundfile as sf
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import store
from app.analysis import apply_source_evidence
BASE='http://127.0.0.1:8767/api'
def api(path, body=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=180))
report_path=ROOT/'docs/runtime-report.json'
report=json.loads(report_path.read_text(encoding='utf-8'))
initial=ROOT/'docs/runtime-initial.json'
if not initial.exists():
    initial.write_text(json.dumps(report,indent=2),encoding='utf-8')
bid=report['book_id']
before=api('/books/'+bid)
voices={c['id']:c['voice'] for c in before['cast']}
with store.connect() as db:
    for c in store.rows(db,'SELECT * FROM chapters WHERE book_id=? ORDER BY ordinal',(bid,)):
        segments=store.rows(db,'SELECT * FROM segments WHERE chapter_id=? ORDER BY ordinal',(c['id'],))
        apply_source_evidence(db,bid,c['id'],segments,c['source'])
    store.bump(db,bid)
after=api('/books/'+bid)
assert {c['id']:c['voice'] for c in after['cast']}==voices
names={c['name']:c['id'] for c in after['cast']}
chapters=[api('/chapters/'+c['id']) for c in after['chapters']]
returning=next(s for s in chapters[-1]['segments'] if 'I told you I would come back' in s['text'])
thought=next(s for s in chapters[1]['segments'] if 'This is going to work' in s['text'])
unknown=next(s for s in chapters[0]['segments'] if 'Did you hear that?' in s['text'])
assert returning['speaker']==names['Sam']
assert thought['speaker']==names['Mira'] and thought['kind']=='thought'
assert unknown['speaker'] is None and unknown['review']==1
report['source_evidence_replay']={'sam_return_correct':True,'explicit_thought_correct':True,'ambiguous_line_flagged':True,'saved_voices_unchanged':True,
 'note':'Applied production source-evidence postprocessing to saved real model annotations. Original model-only errors are retained in runtime-initial.json.'}
def run(mode, thoughts=True):
    start=time.perf_counter()
    jid=api('/books/'+bid+'/jobs',{'type':'render','mode':mode,'thoughts':thoughts,'allow_unresolved':True})['id']
    last=''
    while time.perf_counter()-start<300:
        b=api('/books/'+bid)
        j=next(j for j in b['jobs'] if j['id']==jid)
        state=j['state']+': '+j['message']
        if state!=last:
            print(state,flush=True);last=state
        if j['state'] in ('complete','failed','needs_review','paused'):
            assert j['state']=='complete',j
            break
        time.sleep(2)
    else: raise TimeoutError('Rendering test timed out')
    artifacts=[]
    for a in b['artifacts']:
        if a['job_id']!=jid: continue
        raw=urllib.request.urlopen(BASE+'/artifacts/'+a['id']).read()
        pcm,sr=sf.read(io.BytesIO(raw),dtype='int16')
        assert sr==24000 and len(pcm)>0 and np.max(np.abs(pcm.astype(np.int32)))>100
        artifacts.append({**a,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    assert len(artifacts)==4
    return {'job_id':jid,'wall_seconds':time.perf_counter()-start,'artifacts':artifacts}
report['corrected_full_export']=run('full')
report['dialogue_only_export']=run('dialogue',False)
def total(d):return next(a['seconds'] for a in d['artifacts'] if a['chapter_id'] is None)
assert total(report['dialogue_only_export'])<total(report['corrected_full_export'])
line='Welcome back, Sam. The bridge is still standing.'
samvoice=voices[names['Sam']]
a=api('/preview',{'voice':samvoice,'text':line})
b=api('/preview',{'voice':samvoice,'text':line})
c=api('/preview',{'voice':voices[names['Mira']],'text':line})
assert a['url']==b['url'] and b['generation_seconds']==0
raw_a=urllib.request.urlopen('http://127.0.0.1:8767'+a['url']).read()
raw_c=urllib.request.urlopen('http://127.0.0.1:8767'+c['url']).read()
assert hashlib.sha256(raw_a).digest()!=hashlib.sha256(raw_c).digest()
report['preview_benchmark']=a
report['cache_reuse_verified']=True
report['distinct_voice_waveforms_verified']=True
report['post_correction_cast']=after['cast']
report['completed']=time.strftime('%Y-%m-%d %H:%M:%S')
report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'mapping_seconds':report['mapping_seconds'],'full_audio_seconds':total(report['corrected_full_export']),'dialogue_audio_seconds':total(report['dialogue_only_export']),'full_rerender_wall_seconds':report['corrected_full_export']['wall_seconds'],'preview':a,'cast_persistence':True,'distinct_voice_waveforms':True}),flush=True)
