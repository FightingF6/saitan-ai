import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from backend.config import settings
from backend.main import app
from backend.db import Session, SearchTask, TaskEvent, Competition, CompetitionSource, TaskCompetition
from backend.tasks import manager, emit
from backend.schemas import Candidate


@pytest.fixture
def client():
    with TestClient(app) as client:
        with Session.begin() as s:
            for model in (TaskCompetition,CompetitionSource,TaskEvent,Competition,SearchTask):s.execute(delete(model))
        settings.api_key=SecretStr('')
        yield client


def test_config_key_not_exposed_and_required(client):
    assert client.post('/api/tasks',json={'query':'寻找人工智能竞赛'}).status_code==409
    settings.api_key=SecretStr('test-secret-never-expose')
    assert 'test-secret' not in client.get('/api/settings').text
    assert client.get('/api/settings').json()['data']['api_key_configured']


def test_validation_and_origin(client):
    assert client.post('/api/tasks',json={'query':'短'}).status_code==422
    r=client.put('/api/settings',json={'api_key':'my-secret','max_steps':10000})
    assert r.status_code==422 and 'my-secret' not in r.text
    assert client.post('/api/tasks',headers={'Origin':'https://evil.example'},json={'query':'有效搜索条件'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==400


def seed_task():
    with Session.begin() as s:
        t=SearchTask(query='测试任务',filters={},config={},status='completed');s.add(t);s.flush();return t.id


def test_sse_replay_and_terminal_close(client):
    task_id=seed_task()
    emit(task_id,'page_visited','访问公开通知',{'url':'https://example.com'})
    emit(task_id,'task_completed','完成')
    first=client.get(f'/api/tasks/{task_id}/events').text
    assert 'event: progress' in first and 'event: end' in first
    ids=[int(x.split(': ')[1]) for x in first.splitlines() if x.startswith('id: ')]
    assert ids==sorted(ids)
    replay=client.get(f'/api/tasks/{task_id}/events',headers={'Last-Event-ID':str(ids[0])}).text
    assert f'id: {ids[0]}\n' not in replay and f'id: {ids[1]}\n' in replay


def test_exports_missing_tasks_and_delete(client):
    task_id=seed_task()
    assert client.get(f'/api/tasks/{task_id}/export?format=csv').text.startswith('\ufeffname,')
    assert '赛探 AI' in client.get(f'/api/tasks/{task_id}/export?format=md').text
    assert client.get(f'/api/tasks/{task_id}/export?format=exe').status_code==422
    assert client.delete(f'/api/tasks/{task_id}').status_code==200
    assert client.get(f'/api/tasks/{task_id}').status_code==404


@pytest.mark.asyncio
async def test_manager_partial_failure_preserves_evidence(monkeypatch,client):
    async def failing(task_id,query,filters,config,event,accept):
        url='https://example.com/2026'
        c=Candidate(name='测试人工智能竞赛',source_urls=[url],evidence=[{'field':'name','quote':'测试人工智能竞赛','source_url':url}])
        await accept(c,{url:{'text':'测试人工智能竞赛','title':'竞赛通知','captured_at':'2026-10-18'}})
        raise RuntimeError('simulated provider failure, test only')
    monkeypatch.setattr('backend.agent.execute',failing)
    tid=seed_task();await manager.run(tid)
    result=client.get(f'/api/tasks/{tid}').json()['data']
    assert result['status']=='partial' and result['result_count']==1
    assert result['results'][0]['source_urls']==['https://example.com/2026']
    assert '测试人工智能竞赛' in client.get(f'/api/tasks/{tid}/export?format=csv').text
    assert 'simulated provider' not in json.dumps(result)


@pytest.mark.asyncio
async def test_cancellation_and_resource_release(monkeypatch,client):
    released=asyncio.Event()
    started=asyncio.Event()
    async def blocking(*args):
        try:started.set();await asyncio.sleep(30)
        finally:released.set()
    monkeypatch.setattr('backend.agent.execute',blocking)
    tid=seed_task();manager.launch(tid);await started.wait();await manager.cancel(tid)
    assert released.is_set()
    with Session() as s:assert s.get(SearchTask,tid).status=='cancelled'


def test_restart_marks_interrupted(client):
    tid=seed_task()
    with Session.begin() as s:s.get(SearchTask,tid).status='running'
    manager.recover()
    assert client.get(f'/api/tasks/{tid}').json()['data']['status']=='interrupted'


@pytest.mark.asyncio
async def test_timeout_is_failure_and_releases_resources(monkeypatch,client):
    released=[]
    async def hanging(*args):
        try:await asyncio.sleep(10)
        finally:released.append(True)
    monkeypatch.setattr('backend.agent.execute',hanging)
    monkeypatch.setattr(settings,'timeout_seconds',0.02)
    tid=seed_task();await manager.run(tid)
    result=client.get(f'/api/tasks/{tid}').json()['data']
    assert result['status']=='failed' and '超时' in result['error'] and released


def test_settings_encryption_roundtrip(client):
    import os
    if os.name!='nt':pytest.skip('Windows DPAPI')
    from backend.config import _protect, _unprotect
    encrypted=_protect('unit-test-secret')
    assert 'unit-test-secret' not in encrypted
    assert _unprotect(encrypted)=='unit-test-secret'


@pytest.mark.parametrize('converted_error', [False, True])
async def test_browser_consuming_cancellation_preserves_user_intent(monkeypatch, client, converted_error):
    started = asyncio.Event()
    async def consuming(*args):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            if converted_error:
                raise RuntimeError('browser converted cancellation')
    monkeypatch.setattr('backend.agent.execute', consuming)
    tid = seed_task()
    manager.launch(tid)
    await started.wait()
    await manager.cancel(tid)
    assert client.get(f'/api/tasks/{tid}').json()['data']['status'] == 'cancelled'


@pytest.mark.parametrize('converted_error', [False, True])
async def test_browser_consuming_timeout_still_reports_timeout(monkeypatch, client, converted_error):
    async def consuming(*args):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            if converted_error:
                raise RuntimeError('browser converted timeout')
    monkeypatch.setattr('backend.agent.execute', consuming)
    monkeypatch.setattr(settings, 'timeout_seconds', 0.02)
    tid = seed_task()
    await manager.run(tid)
    result = client.get(f'/api/tasks/{tid}').json()['data']
    assert result['status'] == 'failed' and '超时' in result['error']


def test_create_concurrency_cancel_and_config_redaction(monkeypatch,client):
    async def waiting(*args):await asyncio.sleep(30)
    monkeypatch.setattr('backend.agent.execute',waiting)
    settings.api_key=SecretStr('test-only-private-key')
    first=client.post('/api/tasks',json={'query':'寻找适合大一学生参加的人工智能相关比赛。'})
    assert first.status_code==201
    tid=first.json()['data']['id']
    assert client.post('/api/tasks',json={'query':'并发测试搜索需求'}).status_code==409
    assert client.delete(f'/api/tasks/{tid}').status_code==409
    response=client.post(f'/api/tasks/{tid}/cancel')
    assert response.status_code==200 and response.json()['data']['status']=='cancelled'
    assert 'test-only-private-key' not in response.text
