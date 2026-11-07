import asyncio
import base64
import io
import json
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from app import cloud, store, voices
from app.main import app
from app.jobs import queue, Queue, Paused


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.setattr(voices, 'DATA', tmp_path)
    monkeypatch.setattr(queue, 'start', lambda: None)
    monkeypatch.setattr(queue, 'close', lambda: None)
    monkeypatch.setattr(cloud, '_keys', {'gemini':'test-key','elevenlabs':'test-key','hume':'test-key'})
    monkeypatch.setattr(cloud, '_catalogs', {})
    with TestClient(app) as c:
        yield c


def chapter_book(c):
    bid=c.post('/api/books',json={'title':'Cloud test'}).json()['id']
    cid=c.post(f'/api/books/{bid}/chapters',json={'number':1,'text':'Mira entered.\n\n“Hello,” Mira said.\n\nThe door closed.'}).json()['id']
    return bid,cid


def test_empty_book_numbered_chapters_and_exact_text(client):
    bid=client.post('/api/books',json={'title':'A novel'}).json()['id']
    assert client.get('/api/books/'+bid).json()['chapters']==[]
    assert client.post(f'/api/books/{bid}/jobs',json={'type':'map'}).status_code==400
    source='  😀 “Don’t move.”\r\n\r\nThe end.  '
    a=client.post(f'/api/books/{bid}/chapters',json={'number':72,'text':source}).json()['id']
    assert client.post(f'/api/books/{bid}/chapters',json={'number':1,'text':'First.'}).status_code==200
    assert client.post(f'/api/books/{bid}/chapters',json={'number':72,'text':'Overwrite?'}).status_code==400
    assert [c['ordinal'] for c in client.get('/api/books/'+bid).json()['chapters']]==[1,72]
    assert client.get('/api/chapters/'+a).json()['source']==source
    export=client.get(f'/api/books/{bid}/project').json()
    assert export['chapters'][1]['source']==source


def test_cloud_credentials_never_return_or_persist(client):
    secret='private-test-secret'
    r=client.put('/api/connections/gemini',json={'key':secret})
    assert secret not in r.text
    assert client.get('/api/connections').json()['connected']['gemini']
    assert secret.encode() not in (store.DATA/'library.sqlite3').read_bytes()
    client.put('/api/connections/gemini',json={'key':''})
    bid,cid=chapter_book(client)
    assert client.post(f'/api/books/{bid}/jobs',json={'type':'map','mapping_provider':'gemini','model':'gemini-3.8-flash','tts_provider':'gemini'}).status_code==400


def test_request_allowance_is_durable(client):
    cloud.reserve('limited','gemini',50,{'max_cloud_requests':2,'max_cloud_chars':100})
    with pytest.raises(cloud.ProviderError,match='allowance'):
        cloud.reserve('limited','gemini',51,{'max_cloud_requests':2,'max_cloud_chars':100})
    cloud.reserve('limited','gemini',50,{'max_cloud_requests':2,'max_cloud_chars':100})
    with pytest.raises(cloud.ProviderError):
        cloud.reserve('limited','gemini',0,{'max_cloud_requests':2,'max_cloud_chars':100})
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM cloud_usage').fetchone()[0]==2


def test_http_quota_sanitized_and_cancelled(client,monkeypatch):
    original=httpx.AsyncClient
    async def handler(req):
        return httpx.Response(429,json={'error':'private-test-secret'})
    monkeypatch.setattr(cloud.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(cloud.ProviderError) as exc:
        cloud.request('gemini','/models',{'test':True})
    assert exc.value.quota and 'private-test-secret' not in str(exc.value)


def test_http_pause_closes_waiting_request(client,monkeypatch):
    original=httpx.AsyncClient
    started=[];closed=[]
    async def handler(req):
        started.append(True)
        try:
            await asyncio.sleep(60)
        finally:
            closed.append(True)
    monkeypatch.setattr(cloud.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    def check():
        if started:
            raise Paused()
    with pytest.raises(Paused):
        cloud.request('gemini','/models',{'test':True},checkpoint=check)
    assert closed


def test_mapping_rejects_foreign_ids(client,monkeypatch):
    monkeypatch.setattr(cloud,'gemini_json',lambda *a:json.dumps({'characters':[],'labels':[{'id':'elsewhere','kind':'narration','speaker':None,'confidence':1,'reason':''}]}))
    with pytest.raises(cloud.ProviderError,match='invented'):
        cloud.GeminiAnalyzer('gemini-3.8-flash','test',{}).analyze([{'id':'s','text':'hello'}],[],'')


def test_casting_persistent_and_manual_selection_survives(client,monkeypatch):
    bid,cid=chapter_book(client)
    person=client.get('/api/books/'+bid).json()['cast'][0]
    calls=[]
    def cast(*args):
        calls.append(True)
        return json.dumps({'voices':[{'character_id':person['id'],'voice_id':'Kore','direction':'Calm','reason':'Artistic choice'}]})
    monkeypatch.setattr(cloud,'gemini_json',cast)
    job={'id':'cast-job','book_id':bid};options={'tts_provider':'gemini','model':'gemini-3.8-flash'}
    cloud.cast_book(job,options,lambda:None)
    cloud.cast_book(job,options,lambda:None)
    assert len(calls)==1
    r=client.put('/api/characters/'+person['id']+'/cloud-voice/gemini',json={'voice_id':'Leda','direction':'Gentle'})
    assert r.status_code==200
    cloud.cast_book(job,options,lambda:None)
    assert client.get('/api/books/'+bid).json()['cast'][0]['cloud_voices']['gemini']['voice_id']=='Leda'


def test_hume_catalog_uses_documented_response(client,monkeypatch):
    monkeypatch.setattr(cloud,'request',lambda *a,**kw:httpx.Response(200,json={'voices_page':[{'id':'abc','name':'Test voice','provider':'HUME_AI'}]}))
    assert cloud.catalog('hume')[0]['id']=='abc'


@pytest.mark.parametrize('provider',['gemini','elevenlabs','hume'])
def test_cloud_audio_decodes_resamples_and_caches(client,monkeypatch,provider):
    import numpy as np
    import soundfile as sf
    calls=[];buf=io.BytesIO()
    sf.write(buf,np.ones(4800,dtype='float32')*.1,48000,format='WAV',subtype='PCM_16')
    def response(*args,**kwargs):
        calls.append(args)
        if provider=='gemini':
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'inlineData':{'mimeType':'audio/L16;codec=pcm;rate=24000','data':base64.b64encode(b'\x01\x00'*2400).decode()}}]}}]})
        if provider=='hume':
            return httpx.Response(200,json={'generations':[{'audio':base64.b64encode(buf.getvalue()).decode()}]})
        mp3=io.BytesIO()
        sf.write(mp3,np.ones(4800,dtype='float32')*.1,48000,format='MP3')
        return httpx.Response(200,content=mp3.getvalue())
    monkeypatch.setattr(cloud,'request',response)
    voice={'provider':provider,'voice_id':'Kore' if provider=='gemini' else 'example','direction':'Soft'}
    path,seconds,wall=cloud.render('Hello',voice,{})
    with wave.open(str(path)) as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(24000,1,2)
    assert seconds==pytest.approx(.1,abs=.05)  # MP3 can include encoder padding.
    assert cloud.render('Hello',voice,{})[2]==0
    assert len(calls)==1
    cloud.render('Hello',{**voice,'direction':'Brighter'},{})
    assert len(calls)==2


def test_production_timeline_fallback_and_staleness(client,monkeypatch,tmp_path):
    bid,cid=chapter_book(client)
    narrator=client.get('/api/books/'+bid).json()['cast'][0]
    client.put('/api/characters/'+narrator['id']+'/cloud-voice/gemini',json={'voice_id':'Kore'})
    with store.connect() as db:
        db.execute('UPDATE segments SET mapped=1')
    jid=client.post(f'/api/books/{bid}/jobs',json={'type':'render','mapping_provider':'gemini','model':'gemini-3.8-flash','tts_provider':'gemini','allow_unresolved':True}).json()['id']
    with store.connect() as db:
        job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
    def render(text,voice,*args):
        path=tmp_path/'clip.wav'
        with wave.open(str(path),'wb') as w:
            w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*2400)
        return path,.1,.01
    monkeypatch.setattr(cloud,'render',render)
    Queue().process(job)
    b=client.get('/api/books/'+bid).json()
    for a in b['artifacts']:
        t=client.get('/api/artifacts/'+a['id']+'/timeline').json()
        assert t['segments'][0]['start']==0 and not t['stale']
        assert all(s['speaker']==narrator['id'] for s in t['segments'])
        assert t['segments'][1]['start']==pytest.approx(.26)
        assert t['segments'][-1]['end']==pytest.approx(a['seconds'])
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='complete' WHERE id=?",(jid,))
    sid=client.get('/api/chapters/'+cid).json()['segments'][0]['id']
    client.put('/api/segments/'+sid,json={'kind':'narration'})
    assert all(client.get('/api/artifacts/'+a['id']+'/timeline').json()['stale'] for a in b['artifacts'])


def test_hosted_password_protects_keys_and_books(client,monkeypatch):
    monkeypatch.setenv('TTSAI_PASSWORD','private-password')
    assert client.get('/api/books').status_code==401
    assert client.get('/api/connections').status_code==401
    assert client.get('/health').status_code==200
    assert client.get('/api/books',auth=('studio','private-password')).status_code==200


def test_unknown_speaker_can_remain_flagged(client):
    bid,cid=chapter_book(client)
    s=client.get('/api/chapters/'+cid).json()['segments'][1]
    r=client.put('/api/segments/'+s['id'],json={'kind':'dialogue','speaker':None,'needs_review':True})
    assert r.status_code==200
    assert client.get('/api/chapters/'+cid).json()['segments'][1]['review']==1


def test_character_and_cloud_voice_edit_is_atomic(client):
    bid,cid=chapter_book(client)
    person=client.get('/api/books/'+bid).json()['cast'][0]
    before=person['description']
    r=client.put('/api/characters/'+person['id'],json={'name':person['name'],'description':'Must not persist','voice':person['voice'],
        'cloud_voice':{'provider':'gemini','voice_id':'invented-voice'}})
    assert r.status_code==400
    after=client.get('/api/books/'+bid).json()['cast'][0]
    assert after['description']==before and not after['cloud_voices']

def test_deepgram_render_cache_pitch_and_auth(client, monkeypatch):
    import numpy as np
    import soundfile as sf
    cloud.set_key('deepgram', 'fake-deepgram')
    calls=[]
    buf=io.BytesIO()
    sf.write(buf, .2*np.sin(2*np.pi*220*np.arange(24000)/24000),24000,format='WAV')
    async def fake(method,url,headers,body,checkpoint):
        calls.append((url,headers,body))
        return httpx.Response(200,content=buf.getvalue())
    monkeypatch.setattr(cloud,'_http',fake)
    voice={'provider':'deepgram','voice_id':'aura-2-luna-en','direction':'Do not speak this','speed':1,'pitch_semitones':0}
    base,seconds,_=cloud.render('Hello.',voice,{})
    changed,shifted,_=cloud.render('Hello.',{**voice,'pitch_semitones':1.2},{})
    assert base != changed and abs(seconds-shifted)<.15
    assert len(calls)==1
    assert calls[0][1]=={'Authorization':'Token fake-deepgram'}
    assert calls[0][2]=={'text':'Hello.'}
    assert 'speed=1.0' in calls[0][0]
    assert cloud.render('Hello.',{**voice,'pitch_semitones':1.2},{})[2]==0
    cloud.render('Hello.',{**voice,'speed':.9},{})
    assert len(calls)==2
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM cloud_usage WHERE provider='deepgram'").fetchone()[0]==2


def test_deepgram_saved_character_controls(client):
    bid,cid=chapter_book(client)
    person=client.get('/api/books/'+bid).json()['cast'][0]
    url='/api/characters/'+person['id']+'/cloud-voice/deepgram'
    value={'voice_id':'aura-2-atlas-en','speed':.9,'pitch_semitones':-1.2}
    assert client.put(url,json=value).status_code==200
    saved=client.get('/api/books/'+bid).json()['cast'][0]['cloud_voices']['deepgram']
    assert saved['speed']==.9 and saved['pitch_semitones']==-1.2
    assert client.put(url,json={**value,'speed':2}).status_code==422
    assert client.put(url,json={**value,'voice_id':'unknown'}).status_code==400
