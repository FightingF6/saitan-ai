# 系统架构

## 模块

| 路径 | 职责 |
|---|---|
| `frontend/app` | App Router 的首页、任务、赛事、设置路由与全局样式 |
| `frontend/components/workspace.tsx` | 搜索表单、实时执行面板、卡片、历史、配置 |
| `frontend/lib/api.ts` | API 错误统一处理及前端数据类型 |
| `backend/main.py` | 输入校验、任务/赛事 API、SSE、配置、健康检查、导出 |
| `backend/tasks.py` | 异步运行、并发限制、取消、超时、重启中断、增量保存 |
| `backend/agent.py` | 官方模型适配器、只读工具、浏览器事件、截图和网页捕获 |
| `backend/security.py` | URL / DNS 检查、公网 IP 固定代理、防内网跳转 |
| `backend/verification.py` | 逐字段原文比对、日期状态、资格提示、去重及冲突 |
| `backend/config.py` | 环境变量、Windows DPAPI、脱敏公开配置 |
| `backend/db.py` | SQLAlchemy 模型、SQLite 外键/WAL |

## 数据与一致性

SearchTask 关联 TaskEvent 和 TaskCompetition。Competition 存储最新赛事证据，CompetitionSource 保存来源 URL、标题、类型、抓取时间、状态和引用。TaskCompetition 保存当次不可被后续搜索覆盖的 JSON 快照，保证历史导出对应当时结果。

任务状态：queued → running → completed / failed / partial / cancelled。取消中使用 cancelling；重启发现未结束任务标记 interrupted，已有结果和事件保留，不自动重跑计费模型。首次建库使用 SQLAlchemy create_all；未来修改 schema 应引入 Alembic 迁移，当前无自动升级已有 schema 的能力。

并发与生命周期：仅限单后端进程。创建请求检查进程内任务表，一个任务占用一个浏览器。普通 API 不等待 Agent 搜索，取消接口等待清理完成。任务超时包裹完整 Agent 链路，finally 最多额外等待 15 秒浏览器退出。杀进程时下次启动标记 interrupted。

## SSE 与恢复

事件按 SQLite 自增 ID 排序；客户端通过 Last-Event-ID 或 after 游标回放。重复事件按 ID 去重，终态发送 end 后关闭流。页面刷新从任务详情恢复事件、截图、结果与统计；sessionStorage 只保存当前任务 ID。SSE 异常时浏览器自动重连，TanStack Query 每五秒读取实际任务状态作为降级；不以计时器伪造阶段完成。

当前 API 采用 `{data: ...}` / `{error: {code, message}}`，SSE 使用事件对象。错误不会回显输入密钥或服务商错误堆栈。参数限制、模型预算限制见 OpenAPI `/docs`。

## 部署边界

前端通过 Next.js rewrite 同源访问绑定 127.0.0.1 的后端。只允许明确的 localhost/127.0.0.1 Origin 和 Host。无登录、多租户与公网 API 鉴权。生产化需独立 worker/队列、PostgreSQL、迁移、TLS、认证、服务端速率限制、OS/容器网络出站策略与秘密管理服务。当前设计未部署到公开网站。
