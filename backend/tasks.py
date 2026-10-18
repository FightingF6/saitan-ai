import asyncio
import logging
from contextlib import suppress
from sqlalchemy import select
from .config import settings
from .db import Session, SearchTask, TaskEvent, Competition, CompetitionSource, TaskCompetition, now
from .verification import local_today, merge_evidence, verify
from .agent import AgentIncomplete

ACTIVE = ('queued', 'running', 'cancelling')
TERMINAL = ('completed', 'partial', 'failed', 'cancelled', 'interrupted')


def emit(task_id, kind, message, payload=None):
    with Session.begin() as session:
        session.add(TaskEvent(task_id=task_id, type=kind, message=message, payload=payload or {}))


class TaskManager:
    def __init__(self):
        self.jobs = {}

    def recover(self):
        with Session.begin() as s:
            for task in s.scalars(select(SearchTask).where(SearchTask.status.in_(ACTIVE))):
                task.status, task.ended_at, task.error = 'interrupted', now(), '服务重启，任务已中断；已有结果已保留，请重新搜索。'
                s.add(TaskEvent(task_id=task.id, type='task_interrupted', message=task.error, payload={}))

    def launch(self, task_id):
        self.jobs[task_id] = asyncio.create_task(self.run(task_id))

    async def run(self, task_id):
        config = settings.model_copy(deep=True)
        try:
            with Session.begin() as s:
                task = s.get(SearchTask, task_id)
                task.status, task.started_at = 'running', now()
                query, filters = task.query, task.filters
            emit(task_id, 'planning_started', '正在解析需求与筛选条件', {'stage': 0})
            emit(task_id, 'planning_completed', '搜索计划已生成，优先查找本届报名通知及高校公告', {'stage': 1, 'keywords': [f'{local_today().year} {filters.get("category", "")} 大学生竞赛 报名通知', query], 'page_budget': config.max_pages})

            async def event(kind, message, payload):
                emit(task_id, kind, message, payload)

            async def accept(candidate, pages):
                data = verify(candidate, pages, filters)
                if not data:
                    emit(task_id, 'evidence_rejected', '候选信息缺少可比对的赛事名称或来源，未加入结果', {'stage': 5})
                    return False
                with Session.begin() as s:
                    existing = s.get(TaskCompetition, (task_id, data['id']))
                    if existing:
                        data = merge_evidence(existing.snapshot, data)
                        existing.snapshot = data
                    else:
                        count = len(list(s.scalars(select(TaskCompetition).where(TaskCompetition.task_id == task_id))))
                        if count >= config.default_count:
                            return False
                    comp = s.get(Competition, data['id'])
                    if comp:
                        comp.data = data
                    else:
                        s.add(Competition(id=data['id'], name=data['name'], data=data))
                    s.flush()
                    if not existing:
                        s.add(TaskCompetition(task_id=task_id, competition_id=data['id'], snapshot=data))
                    for source in data['sources']:
                        present = s.scalar(select(CompetitionSource).where(CompetitionSource.competition_id == data['id'], CompetitionSource.url == source['url']))
                        if not present:
                            s.add(CompetitionSource(competition_id=data['id'], **source))
                emit(task_id, 'competition_found', f'已保存：{data["name"]}', {'stage': 5, 'competition_id': data['id']})
                emit(task_id, 'verification_updated', f'原文核验：{data["registration_status"]}', {'stage': 5, 'competition_id': data['id']})
                return True

            from .agent import execute
            deadline = asyncio.timeout(config.timeout_seconds)
            try:
                async with deadline:
                    await execute(task_id, query, filters, config, event, accept)
            except Exception:
                # Browser Use can convert cancellation into a tool/runtime error.
                if deadline.expired():
                    raise TimeoutError from None
                raise
            if deadline.expired():
                raise TimeoutError
            self.finish(task_id, 'completed', None)
        except asyncio.CancelledError:
            self.finish(task_id, 'cancelled', '任务已取消，已有结果已保留')
        except TimeoutError:
            self.finish(task_id, 'failed', '搜索已超时，已有结果已保留；可调整时间预算后重试')
        except AgentIncomplete as error:
            self.finish(task_id, 'failed', str(error))
        except Exception as error:
            logging.getLogger(__name__).warning('Agent task failed (%s)', type(error).__name__)
            self.finish(task_id, 'failed', 'Agent 执行失败，请检查模型密钥、余额、模型兼容性及网络。已有结果已保留。')
        finally:
            self.jobs.pop(task_id, None)

    def finish(self, task_id, status, error):
        with Session.begin() as s:
            task = s.get(SearchTask, task_id)
            if not task:
                return
            # Explicit user cancellation wins even when the browser library
            # consumes CancelledError and returns normally or raises another error.
            if task.status == 'cancelling':
                status, error = 'cancelled', '任务已取消，已有结果已保留'
            has_results = s.scalar(select(TaskCompetition).where(TaskCompetition.task_id == task_id)) is not None
            if status == 'failed' and has_results:
                status = 'partial'
            task.status, task.ended_at, task.error = status, now(), error
            s.add(TaskEvent(task_id=task_id, type=f'task_{status}', message=error or '搜索结束，竞赛清单已生成', payload={'stage': 6}))

    async def cancel(self, task_id):
        job = self.jobs.get(task_id)
        if job and not job.done():
            with Session.begin() as s:
                s.get(SearchTask, task_id).status = 'cancelling'
            emit(task_id, 'task_cancelling', '正在停止 Agent 并释放浏览器', {})
            job.cancel()
            # The task may have been cancelled before its coroutine first ran.
            with suppress(asyncio.CancelledError):
                await job
            with Session() as s:
                unfinished = s.get(SearchTask, task_id).status in ACTIVE
            if unfinished:
                self.finish(task_id, 'cancelled', '任务已取消')
            self.jobs.pop(task_id, None)

    async def close(self):
        for task_id in list(self.jobs):
            await self.cancel(task_id)


manager = TaskManager()
