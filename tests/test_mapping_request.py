import json

from app import cloud, store
from app.analysis import Mapping
from app.jobs import Queue
from tests.test_cloud import client, chapter_book


def test_gemini_mapping_uses_json_mode_and_keeps_schema_in_prompt(client, monkeypatch):
    sent=[]
    class Response:
        def json(self):
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({
                'characters':[], 'labels':[{'id':'0','kind':'narration','speaker':None,'confidence':1,'reason':'Narration'}]})}]}}]}
    def request(provider,path,body,*args):
        sent.append(body)
        return Response()
    monkeypatch.setattr(cloud,'request',request)
    result=cloud.GeminiAnalyzer(cloud.MODELS[0],'test',{}).analyze([{'id':'real-id','text':'The sun rose.'}],[],'The sun rose.')
    config=sent[0]['generationConfig']
    assert config['responseMimeType']=='application/json'
    assert 'responseSchema' not in config and 'responseJsonSchema' not in config
    assert '"labels"' in sent[0]['systemInstruction']['parts'][0]['text']
    assert result.labels[0].id=='real-id'


def test_provider_failure_finishes_attempt_and_cannot_resume(client, monkeypatch):
    bid,cid=chapter_book(client)
    jid=client.post(f'/api/books/{bid}/jobs',json={'type':'map'}).json()['id']
    q=Queue()
    def fail(job):
        q.stop.set()
        raise cloud.ProviderError('Quota reached',quota=True)
    monkeypatch.setattr(q,'process',fail)
    q.run()
    with store.connect() as db:
        assert db.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
    assert client.post(f'/api/jobs/{jid}/resume',json={}).status_code==400
    assert client.post(f'/api/books/{bid}/jobs',json={'type':'map'}).status_code==200
    assert client.get('/api/chapters/'+cid).json()['source'].startswith('Mira entered.')
