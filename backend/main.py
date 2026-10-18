import asyncio
import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from importlib.metadata import version
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse, FileResponse
from sqlalchemy import delete, select
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import settings, load_settings, public_settings, save_settings, SettingsUpdate
from .db import Base, engine, Session, SearchTask, TaskEvent, Competition, CompetitionSource, TaskCompetition, event_dict
from .schemas import TaskCreate
from .tasks import ACTIVE, TERMINAL, manager, emit
from .verification import registration_status


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    load_settings()
    manager.recover()
    yield
    await manager.close()


app = FastAPI(title='赛探 AI API', version='0.1.0', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.middleware('http')
async def local_access(request, call_next):
    origin = request.headers.get('origin')
    if origin and origin not in ('http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:8000', 'http://127.0.0.1:8000'):
        return JSONResponse({'error': {'code': 'ORIGIN_DENIED', 'message': '仅允许本地应用访问'}}, status_code=403)
    if int(request.headers.get('content-length', '0')) > 32768:
        return JSONResponse({'error': {'code': 'TOO_LARGE', 'message': '请求内容过长'}}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(HTTPException)
async def http_error(_, error):
    return JSONResponse({'error': {'code': str(error.status_code), 'message': str(error.detail)}}, status_code=error.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_, error):
    # Do not echo rejected input, which may contain API credentials.
    return JSONResponse({'error': {'code': 'VALIDATION_ERROR', 'message': '输入不符合要求，请检查字段长度、格式及数值范围'}}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(_, error):
    logging.getLogger(__name__).error('Request failed (%s)', type(error).__name__)
    return JSONResponse({'error': {'code': 'INTERNAL_ERROR', 'message': '服务处理失败，请稍后重试'}}, status_code=500)


def require_task(session, task_id):
    task = session.get(SearchTask, task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    return task


def task_data(session, task, detail=False):
    data = {k: getattr(task, k) for k in ('id', 'query', 'filters', 'status', 'created_at', 'started_at', 'ended_at', 'error', 'config')}
    results = [link.snapshot for link in session.scalars(select(TaskCompetition).where(TaskCompetition.task_id == task.id))]
    data['result_count'] = len(results)
    if detail:
        events = list(session.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id).order_by(TaskEvent.id)))
        data['results'] = results
        data['events'] = [event_dict(e) for e in events]
        visited = {e.payload['url'] for e in events if e.type == 'page_visited'}
        verified = sum(c['verification_status'] == '已核实原文' for c in results)
        data['stats'] = {'visited': len(visited), 'candidates': len(results), 'verified': verified, 'pending': len(results) - verified}
    return data


@app.get('/api/health')
def health():
    return {'data': {'status': 'ok', 'browser_use_version': version('browser-use'), 'model_configured': bool(settings.api_key.get_secret_value()), 'model': settings.model, 'active_tasks': len(manager.jobs), 'mode': 'local-single-process'}}


@app.get('/api/settings')
def get_settings():
    return {'data': public_settings()}


@app.put('/api/settings')
async def update_settings(update: SettingsUpdate):
    if manager.jobs:
        raise HTTPException(409, '请等待或取消当前任务后修改设置')
    from .security import check_url, resolve_public
    try:
        target = check_url(update.api_base_url)
        await resolve_public(target.hostname, target.port or 443)
        save_settings(update)
    except ValueError:
        raise HTTPException(422, '配置无法安全保存：请确认公网 HTTPS API 地址；非 Windows 平台请通过 .env 设置密钥')
    return {'data': public_settings()}


@app.post('/api/settings/test')
async def test_model():
    if not settings.api_key.get_secret_value():
        raise HTTPException(409, '请先配置 API Key')
    from pydantic import BaseModel
    from .agent import create_llm
    from browser_use.llm.messages import SystemMessage, UserMessage
    class Probe(BaseModel):
        ok: bool
    try:
        async with asyncio.timeout(70):
            result = await create_llm(settings).ainvoke([SystemMessage(content='Return valid JSON only.'), UserMessage(content='Return {"ok":true}.')], output_format=Probe)
        if result.completion.ok is not True:
            raise ValueError()
    except Exception:
        raise HTTPException(502, '模型结构化响应测试失败，请检查密钥、余额、模型 ID、API 地址与兼容性')
    return {'data': {'ok': True, 'message': '模型连通与结构化响应测试通过；完整 Agent 兼容性仍需真实搜索验证。'}}


@app.post('/api/tasks', status_code=201)
async def create_task(body: TaskCreate):
    if not settings.api_key.get_secret_value():
        raise HTTPException(409, '模型尚未配置，请先在设置页填写后端 API Key')
    if manager.jobs:
        raise HTTPException(409, '已有任务运行中，请等待完成或取消后再搜索')
    with Session.begin() as session:
        task = SearchTask(query=body.query.strip(), filters=body.filters.model_dump(), config=public_settings())
        session.add(task)
        session.flush()
        task_id = task.id
    emit(task_id, 'task_created', '任务已创建', {'stage': 0})
    manager.launch(task_id)
    return {'data': {'id': task_id, 'status': 'queued'}}


@app.get('/api/tasks')
def list_tasks(limit: int = Query(100, ge=1, le=200)):
    with Session() as session:
        return {'data': [task_data(session, t) for t in session.scalars(select(SearchTask).order_by(SearchTask.created_at.desc()).limit(limit))]}


@app.get('/api/tasks/{task_id}')
def get_task(task_id: str):
    with Session() as session:
        return {'data': task_data(session, require_task(session, task_id), True)}


@app.post('/api/tasks/{task_id}/cancel')
async def cancel_task(task_id: str):
    with Session() as session:
        require_task(session, task_id)
    await manager.cancel(task_id)
    return get_task(task_id)


@app.delete('/api/tasks/{task_id}')
async def delete_task(task_id: str):
    with Session.begin() as session:
        task = require_task(session, task_id)
        if task.status in ACTIVE:
            raise HTTPException(409, '请先取消运行中的任务')
        session.delete(task)
    # A single, explicitly identified screenshot file only; no directory cleanup.
    path = settings.data_dir / f'{task.id}.jpg'
    if path.exists():
        path.unlink()
    return {'data': {'deleted': task_id, 'note': '赛事仍保留在竞赛清单中'}}


@app.get('/api/tasks/{task_id}/screenshot')
def screenshot(task_id: str):
    with Session() as session:
        task = require_task(session, task_id)
        path = settings.data_dir / f'{task.id}.jpg'
    if not path.exists():
        raise HTTPException(404, '暂无浏览器截图')
    return FileResponse(path, media_type='image/jpeg')


@app.get('/api/tasks/{task_id}/events')
async def stream_events(task_id: str, request: Request, after: int = Query(0, ge=0)):
    with Session() as session:
        require_task(session, task_id)
    try:
        cursor = max(after, int(request.headers.get('last-event-id', '0')))
    except ValueError:
        raise HTTPException(422, 'Last-Event-ID 必须是整数')
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with Session() as session:
                task = require_task(session, task_id)
                events = [event_dict(e) for e in session.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.id > cursor).order_by(TaskEvent.id).limit(200))]
                terminal = task.status in TERMINAL
            for e in events:
                cursor = e['id']
                yield f'id: {cursor}\nevent: progress\ndata: {json.dumps(e, ensure_ascii=False)}\n\n'
            if terminal and len(events) < 200:
                yield 'event: end\ndata: {}\n\n'
                break
            yield ': heartbeat\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})


@app.get('/api/competitions')
def list_competitions(q: str = Query('', max_length=200), category: str = Query('', max_length=80), status: str = Query('', max_length=20)):
    with Session() as session:
        records = [c.data for c in session.scalars(select(Competition).order_by(Competition.name))]
    for record in records:
        record['registration_status'] = registration_status(record)
    return {'data': [c for c in records if q.lower() in c['name'].lower() and (not category or category in (c['category'] or '')) and (not status or status == c['registration_status'])]}


@app.get('/api/competitions/{competition_id}')
def get_competition(competition_id: str):
    with Session() as session:
        comp = session.get(Competition, competition_id)
        if not comp:
            raise HTTPException(404, '赛事不存在')
        return {'data': comp.data}


def csv_safe(value):
    value = str(value or '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) or value.startswith(('\t', '\r', '\n')) else value


def markdown_safe(value):
    import html
    return html.escape(str(value or '暂未核实')).replace('[', '\\[').replace(']', '\\]').replace('*', '\\*').replace('\n', ' ')


def export_data(records, format):
    fields = ['name', 'edition', 'category', 'eligible_grades', 'eligible_majors', 'participation_type', 'registration_start', 'registration_deadline', 'registration_status', 'verification_status', 'last_verified_at', 'source_urls']
    if format == 'csv':
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(fields)
        for row in records:
            writer.writerow([csv_safe(' | '.join(row[k]) if isinstance(row.get(k), list) else row.get(k)) for k in fields])
        content, media = '\ufeff' + output.getvalue(), 'text/csv; charset=utf-8'
    else:
        content = '# 赛探 AI · 竞赛清单\n\n信息来自实际访问网页；原文比对不等同于主办方背书。\n\n'
        for row in records:
            content += f'## {markdown_safe(row["name"])}\n\n'
            content += '\n'.join(f'- {k}: {markdown_safe(row.get(k))}' for k in fields[:-1]) + '\n'
            content += '\n'.join(f'- 来源：{markdown_safe(url)}' for url in row['source_urls']) + '\n\n'
        media = 'text/markdown; charset=utf-8'
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="saitan-competitions.{format}"'})


@app.get('/api/tasks/{task_id}/export')
def export_task(task_id: str, format: str = Query('csv', pattern='^(csv|md)$')):
    with Session() as session:
        require_task(session, task_id)
        records = [link.snapshot for link in session.scalars(select(TaskCompetition).where(TaskCompetition.task_id == task_id))]
    return export_data(records, format)


@app.get('/api/export')
def export_all(format: str = Query('csv', pattern='^(csv|md)$')):
    with Session() as session:
        return export_data([c.data for c in session.scalars(select(Competition))], format)


@app.delete('/api/data')
async def clear_records():
    if manager.jobs:
        raise HTTPException(409, '请先取消运行中的任务')
    # Only database rows. No batch filesystem deletion; residual screenshots are documented.
    with Session.begin() as session:
        for model in (TaskCompetition, CompetitionSource, TaskEvent, Competition, SearchTask):
            session.execute(delete(model))
    return {'data': {'message': '数据库记录已清空。磁盘截图文件未批量删除，可手动清理 data 中的 JPG。'}}
