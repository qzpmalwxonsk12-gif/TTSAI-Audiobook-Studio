import json

import httpx
import pytest

from app import cloud, store, usage
from tests.test_cloud import client, chapter_book


@pytest.fixture(autouse=True)
def isolated_usage(monkeypatch):
    monkeypatch.setattr(usage, '_cache', {})


def test_usage_distinguishes_account_from_local_and_job_allowance(client, monkeypatch):
    monkeypatch.setattr(usage.httpx, 'get', lambda *a, **kw: httpx.Response(200, json={
        'character_count':2500,'character_limit':10000,'tier':'free','next_character_count_reset_unix':1791449903}))
    bid, cid = chapter_book(client)
    jid = client.post(f'/api/books/{bid}/jobs', json={'type':'map','mapping_provider':'gemini','model':cloud.MODELS[0],
        'tts_provider':'hume','max_cloud_requests':4,'max_cloud_chars':1000}).json()['id']
    cloud.reserve(jid, 'gemini', 0, {})
    cloud.reserve(jid, 'hume', 250, {})
    with store.connect() as db:
        db.execute("INSERT INTO cloud_usage(scope,provider,chars,created) VALUES('old','hume',99,'2000-01-01 00:00:00')")
    result = client.get('/api/usage', params={'book_id':bid}).json()
    providers = {p['provider']:p for p in result['providers']}
    assert providers['elevenlabs']['account']['percent_used'] == 25
    assert providers['elevenlabs']['account']['remaining'] == 7500
    assert providers['elevenlabs']['local']['requests'] == 0
    assert providers['gemini']['account'] is None and providers['hume']['account'] is None
    assert providers['hume']['local']['speech_characters'] == 250
    assert result['job']['request_percent'] == 50
    assert result['job']['character_percent'] == 25
    assert 'test-key' not in json.dumps(result)


def test_balance_permission_failure_is_not_zero_and_is_cached(client, monkeypatch):
    calls=[]
    def get(*a, **kw):
        calls.append(True)
        return httpx.Response(403,json={'detail':{'message':'private-test-key'}})
    monkeypatch.setattr(usage.httpx, 'get', get)
    for _ in range(2):
        result=client.get('/api/usage').json()['providers'][1]['account']
        assert not result['available'] and 'used' not in result
        assert 'User: Read' in result['message'] and 'private-test-key' not in str(result)
    assert len(calls)==1
    cloud.set_key('elevenlabs','replacement-key')
    client.get('/api/usage')
    assert len(calls)==2


def test_zero_allowance_and_missing_key_do_not_fake_percentage(client, monkeypatch):
    monkeypatch.setattr(usage.httpx,'get',lambda *a,**kw:httpx.Response(200,json={'character_count':0,'character_limit':0}))
    account=client.get('/api/usage').json()['providers'][1]['account']
    assert account['available'] and account['percent_used'] is None
    cloud.set_key('elevenlabs','')
    monkeypatch.setattr(usage.httpx,'get',lambda *a,**kw:pytest.fail('Disconnected key must not make a request'))
    account=client.get('/api/usage').json()['providers'][1]['account']
    assert not account['available'] and 'used' not in account
