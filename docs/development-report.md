# 赛探 AI 开发报告

日期：2026-10-18。**Final Verdict：READY FOR DEMO（本地演示）。** 项目已接入真实 DeepSeek 服务，限定任务已正常完成，搜索、原文保存、导出和任务生命周期均已实测；广泛搜索覆盖仍有不足，不宣称所有搜索都能找到当前可报名的赛事。

## 1. Development Summary

在空目录从零实现可启动的前后端、本地浏览器 Agent、持久数据、实时执行视图、历史与导出、模型设置、测试及文档。使用真实 Browser Use，未向生产数据库填充任何假赛事。参考图片未提供，视觉按文字需求设计。

## 2. Technical Architecture

Next.js 16 App Router + TypeScript + Tailwind 4 + Radix/CVA Button（shadcn/ui 模式）+ Lucide + TanStack Query。FastAPI + Pydantic + SQLAlchemy + SQLite/WAL。uv 管理 Python 3.12，Browser Use 固定 0.13.11。单进程异步任务管理，最大一项活跃搜索，SSE 事件持久化。Windows DPAPI 保存密钥。详情见 architecture.md。

## 3. Feature Checklist

| 功能 | 实际状态 |
|---|---|
| 首页表单、例子、筛选、四个导航页面 | 完成，响应式已测 |
| 本地 Browser Use 启动、访问、DOM、截图 | 完成，真实公网访问已测 |
| Agent 自定义工具与结构化保存 | 完成，真实 Agent.run + 脚本模型契约已测 |
| DeepSeek V4.1 Flash / 通用兼容配置 | DeepSeek 线上 JSON Output 连接与实际网页证据保存已验证；其他兼容服务未逐个测试 |
| 事件时间线、SSE 重连、页面刷新恢复 | 已实现；后端回放测试、UI 状态测试通过 |
| 原文字段核验、过期日期、缺失值、冲突 | 已实现并单元测试；语义核验有限 |
| 资格匹配、推荐理由、去重 | 保守规则实现；复杂资格和跨站同义合并未实现 |
| 官网身份与赛事权威级别 | 不自动背书，保持待核实；没有虚构评分 |
| 历史、取消、超时、失败部分保存 | 已实现；受控执行器及真实浏览器任务取消/30 秒超时通过；真实失败任务部分结果保留 |
| CSV / Markdown、赛事集合与筛选 | 已实现并测试 |
| 设置、健康检查、本地清理 | 完成；仅清数据库，不批量删除文件 |
| README、架构、流程、测试、报告、环境模板 | 完成 |
| 公网部署、多用户认证、PDF 专用提取 | 未实现，不属于当前本地运行交付 |

## 4. Agent Verification

实际浏览器：本机 Chrome，由 Browser Use 0.13.11 驱动；网页访问不依赖云浏览器。

- `https://www.bing.com/search?...`：访问成功，当前网络返回搜索框架，正文内容少，未把搜索框架当赛事结果。
- `https://jsjds.blcu.edu.cn/`：中国大学生计算机设计大赛网站，成功捕获真实文本和截图。
- `https://jsjds.blcu.edu.cn/info/1042/2294.htm`：4C2026 通知，真实 Agent 工具契约测试生成有来源的赛事名称；未知字段为 null，报名状态待核实。
- 原尝试的 `www.4c.org.cn` 无可接受的公网解析，未绕过限制，改用经搜索确认的实际官网。

模型选择：DeepSeek V4.1 Flash，官方 API ID `deepseek-flash`。用户授权后已实际调用官方服务，模型列表和结构化探针通过。Browser Use 0.13.11 适配器没有识别该别名，且实测函数调用参数反复缺少末尾括号；本地 DeepSeekChat 补齐关闭思考参数，并对结构化调用采用官方 JSON Output，完整 Pydantic 校验保留。未放松原文证据要求。

原始需求真实任务已访问中国大学生计算机设计大赛首页和参赛要求，保存有引用的记录。失败、部分成功及最新任务均保留，详见 live-acceptance.json。真实取消任务约 1 秒进入 cancelled；30 秒超时任务约 30.2 秒结束，活跃任务数归零且默认配置恢复。未获得服务商实付账单，不报告推测费用或统计意义上的成功率。脚本模型与隔离 UI 夹具仍清楚区分，不计入真实模型结果。

最终限定核验任务 `2058cadc-ea06-4cb7-9c9e-595f7b673288`：要求只核验计算机设计大赛 2026 年人工智能方向，允许已结束，实际访问 Bing 与参赛要求原文，6 个步骤后 completed，保存 1 条记录并正确识别已结束。保留 Browser Use 的步骤评估和记忆字段后，模型能正常结束；这与 DeepSeek 服务端关闭思考的兼容参数是两层不同设置。最终活跃任务数 0，隔离 Chrome 进程 0，搜索超时恢复为 300 秒。原始需求任务 `b59f1d03-3526-4617-8b5f-dbf23f00e4f7` 的 partial 状态没有改写。

## 5. UI Verification

首页、任务、赛事、设置在 390/768/1440 像素测试通过；无水平溢出。验证示例填充、模型未配置提示、卡片来源、原文展开、筛选与取消状态。实际查看桌面/手机截图。结果态回归截图清晰标注 UI TEST ONLY。未收到 docs/design-reference.png，不主张与缺失图片对照验收。

本次另在应用内浏览器实际提交搜索、从历史恢复任务并查看生产结果。真实截图为 `screenshots/live-search.png`、`live-results.png`、`live-completed.png`，没有 API 拦截或模拟结果。

## 6. Security Review

已落实：服务绑定 loopback；Host/Origin 限制；后端密钥 DPAPI 加密与脱敏；无前端环境密钥；移除危险 Agent 工具；拒绝非 HTTP(S)、凭据 URL、内网/loopback/云元数据与非常用端口；校验全部 DNS 结果并固定 IP 连接；Fake-IP 用独立公网解析重新验证；Chromium 禁用直连 QUIC、限制 WebRTC；公网重定向到本机已实际拦截；CSV 防公式注入；无登录/自动报名工具；浏览器无个人 Cookie；输入、步骤、页面和时间预算。

剩余风险：本地服务无账户认证，不能公网发布；代理是应用层控制，不是 OS 级网络沙箱；远端网页自身 JavaScript 可能发起对公网的请求，不能证明绝对只读；工具限制降低提示注入影响但不保证模型语义判断正确；TLS 隧道不做内容审查；官方域名所有权与日期语义没有独立证明；第三方 Chromium/Browser Use 仍需持续安全更新。不得把当前安全测试当作渗透测试或生产安全认证。

## 7. Test Results

后端 `pytest -q`：48 passed。Next.js build：通过。npm 生产依赖审计：0 vulnerabilities。浏览器访问、Agent 工具契约、跳转拦截、两组前端响应式脚本通过。真实模型连接、导出一致性、SSE 回放、取消、超时通过；实际搜索及修复记录见 testing.md / live-acceptance.json。初次失败任务与报告保留，没有隐藏失败。

## 8. Known Limitations

搜索引擎在当前网络可能返回无关内容或空页，赛事覆盖率有限；真实结果并不保证当前仍可报名。另有 PDF 专用提取缺失、官网身份未独立核实、复杂资格匹配有限、无届次记录与有届次记录可能分别保留、单进程限制、缺少 Alembic 升级迁移。截图库不会自动批量清理。原文出现不等于语义或主办方身份已获独立证实。

## 9. Run Instructions

根目录执行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1` 安装并构建，再执行 `scripts\start.ps1` 启动隐藏后台服务。访问 http://127.0.0.1:3000/settings，填写 Key、保存并测试，然后发起真实搜索。端口 3000/8000 被占用时脚本拒绝覆盖原服务。停止用 `scripts\stop.ps1`。完整配置、手动终端及测试命令见 README.md。

## 10. Final Verdict

**READY FOR DEMO（本地演示）**

已通过真实模型的限定赛事核验闭环与生命周期测试，可进行本地功能演示。原始广泛需求访问 15 页，保留 3 条记录，其中一条截止日期已过、两条待核实（存在同名赛事不同信息完整度的记录）；该任务为 partial。最终限定核验任务为 completed。真实取消、30 秒超时、SSE 和导出通过。搜索覆盖及长期稳定性仍需更多样本，不能把有记录等同于找到了当前可报名且适合大一的赛事，也不宣称具备生产部署条件。

## 官方依据

- Browser Use 源码及 MIT：https://github.com/browser-use/browser-use
- 当前稳定分发与 Python 要求：https://pypi.org/project/browser-use/0.13.11/
- 本地 Python 使用与回调：https://docs.browser-use.com/open-source/quickstart ，https://docs.browser-use.com/open-source/customize/hooks
- DeepSeek V4.1 Flash 官方 API 模型说明：https://api-docs.deepseek.com/news/news260910/
