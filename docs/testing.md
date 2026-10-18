# 测试记录

验证日期：2026-10-18（Asia/Shanghai）。平台：Windows，Python 3.12.13、Node 24.16.0、Next.js 16.4.2、Browser Use 0.13.11，本机 Chrome。

## 实际执行结果

| 命令/项目 | 结果 | 覆盖与边界 |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | **48 passed** | 数据模型、日期、缺失信息、冲突、资格、去重、来源引用、API、SSE、CSV、取消、超时、重启、DPAPI、模型协议；新增吞掉取消异常、JSON 截断/缺字段与重复证据回归 |
| `npm.cmd run build` | **PASS** | Next.js 生产构建、TypeScript 检查、四个路由生成 |
| `npm.cmd audit --omit=dev` | **0 vulnerabilities** | npm 当时返回的生产依赖审计结果，不代表完整安全证明 |
| `python -m scripts.browser_smoke` | **PASS（浏览器链路）** | 真实本地 Chromium 打开 Bing 与竞赛官网、捕获标题/正文/截图 |
| `python -m scripts.agent_contract_smoke` | **PASS（脚本模型）** | 真正执行 Browser Use Agent.run，调用页面、保存、done 工具，原文核验生成带来源记录；没有调用真实模型 |
| `python -m scripts.redirect_security_smoke` | **PASS** | httpbin.org 公网重定向到 loopback，代理拒绝，内网探针命中 0 |
| `node scripts/ui-check.mjs` | **PASS** | 390/768/1440，每个宽度四个页面；无横向溢出、示例填充、未配置模型反馈、无 pageerror |
| `node scripts/ui-results-check.mjs` | **PASS（隔离 API 拦截）** | 三个宽度的真实来源卡片、详情展开、筛选、取消后保留结果的 UI 状态；不是实际模型任务取消测试 |
| `scripts/start.ps1` / `scripts/stop.ps1` | **PASS** | 隐藏后台启动生产前端及后端；停止已确认归属的进程，再启动成功；首页 HTTP 200、健康检查 ok |
| DeepSeek Flash 线上连接 | **PASS** | 用户授权后加密保存密钥，官方模型列表确认 deepseek-flash；真实结构化连接测试 HTTP 200 |
| 真实自主搜索、导出、SSE | **已运行，首轮部分成功** | 原始需求已保存有来源的真实记录；失败和部分成功任务均保留，最新复测见 live-acceptance.json |
| 限定一项赛事的真实核验 | **PASS** | 最终任务 completed，6 步，1 条有原文依据的记录；没有把广泛搜索的 partial 改成 completed |
| 真实浏览器取消、30 秒超时 | **PASS** | 取消状态 cancelled；超时约 30.2 秒后 failed，active_tasks=0，300 秒默认配置恢复 |

可机器读取的结果：`browser-smoke.json`、`agent-contract-smoke.json`、`redirect-security-smoke.json`、`ui-results.json`、`ui-result-cards.json`。测试用数据从不写入生产赛事表。UI 回归截图标记 `UI TEST ONLY`，仅自动化测试的浏览器拦截 API，不给生产应用添加 Mock 开关。

## 必须测试场景对应

1. **真实搜索**：已使用用户授权的 DeepSeek 服务和 Browser Use 访问赛事页并保存证据；多次真实执行发现并修复结构化协议、重复保存问题，结果与失败记录见 live-acceptance.json。
2. **过期识别**：2024 截止时间在 2026 测试日期标记“已结束”，通过。
3. **未公布时间**：缺少截止、开始、当年届次时均不推断“报名中”，通过。
4. **失败保留**：隔离执行器保存一项原文证据后模拟异常，任务 partial，结果及导出保留，通过。
5. **取消**：异步执行器、前端取消状态及实际浏览器任务取消均通过。Browser Use 转换 CancelledError 时仍正确保留用户取消意图。
6. **导出**：有效测试记录 CSV 内容一致、Markdown 输出、非法格式拒绝、公式注入转义，通过。
7. **响应式**：390、768、1440 像素：首页、任务、赛事、设置及结果卡片均未横向溢出，通过。
8. **安全**：密钥不回显、错误不带原始输入、非法 Origin/Host、私有 IP/IPv6/域名、混合 DNS 结果、DNS rebinding、CSV 公式、预算输入验证、超时、DPAPI 与真实公网跳转拦截，通过对应范围。

## 修复记录

- 初次集成 Browser 构造参数使用了错误的 CAPTCHA 参数名，检查 0.13.11 源码后改为 `captcha_solver=False`。
- SQLAlchemy 查询触发 autoflush，TaskCompetition 在赛事插入前写入导致外键错误；显式先 flush Competition，再插入关系。
- 本机 Fake-IP DNS 返回 198.18/15，被安全策略拒绝；独立 HTTPS DNS 解析真实公网地址后再固定 IP 连接，保留私网拒绝。
- Browser Use 将嵌套 Pydantic 工具参数转为 dict；保存工具入口重新 `Candidate.model_validate`，随后真实 Agent 契约测试通过。
- 页面导航后 DOM 正文可能尚未生成；增加有界 DOM 就绪检查。
- 手机端旋转装饰图形产生水平溢出；限制装饰区域并回归所有宽度。
- 官方适配器只识别 deepseek-v4 名称，deepseek-flash 没有发出关闭思考参数；本地适配层补齐 thinking=disabled。
- 实测函数参数 JSON 连续缺少末尾括号，finish_reason=tool_calls，989–1015 输出 token，并非长度截断。改用 DeepSeek 原生 JSON Output，仍执行完整 Pydantic 校验，不猜测修补字段。官方依据：https://api-docs.deepseek.com/guides/json_mode/。
- 模型给赛事名称添加赛道说明导致原文核验拒绝；增加逐字字段说明和具体拒绝反馈，不放松证据标准。
- Browser Use 会把取消异常转为普通错误；任务状态优先保留取消意图，并检查时间上下文是否已过期。
- 重复保存同一证据导致增长与步数消耗；证据幂等合并、明确保存回执、重复调用保护和明确的预算错误信息。
- 恢复 Browser Use 的步骤评估与记忆字段（use_thinking=True）；DeepSeek 服务端仍 thinking=disabled。限定任务重试正常完成，保留此前重复保存的失败/部分结果。单一正例不能证明所有自然语言任务稳定。

## 截图

正常首页：`screenshots/home-1440.png`、`home-768.png`、`home-390.png`。
设置：`screenshots/settings-*.png`。
带结果的隔离 UI 回归：`screenshots/result-ui-test-*.png`。
真实网页截图：`screenshots/browser-smoke.jpg`。

## 真实验收复现

先通过页面执行“寻找适合大一学生参加的人工智能相关比赛。”。运行 `python -m scripts.live_acceptance <task-id>` 可核对导出、SSE，并额外创建取消和超时测试；该脚本会调用已配置的计费模型，结束后恢复原设置。实际报告 `live-acceptance.json`，首轮失败保留在 `live-acceptance-first-attempt.json`，真实导出为 `live-search.csv` / `live-search.md`。脚本不会删除任务。密钥扫描未在 78 个非忽略项目文件中发现明文密钥。
