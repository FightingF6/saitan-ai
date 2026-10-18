# Agent 搜索和证据链

1. 后端持久化需求、筛选、预算快照，并使用 Asia/Shanghai 当天年份构建搜索计划。
2. 独立本地 Chromium 无个人用户配置、无扩展、无 CAPTCHA 求解、无自动 PDF 下载。额外调用 CDP `Browser.setDownloadBehavior(deny)`，避免第三方下载 watchdog 覆盖配置。
3. Browser Use 官方 Agent 仅获得 done、open_public_page、read_public_page、record_competition。去除输入、点击、文件读写、上传、执行 JavaScript、PDF 保存等通用工具。应用自身的固定 JS 只读取 DOM，不由模型提供代码。
4. 打开网页前检查协议、凭据、主机、端口和 DNS。Chromium 所有代理网络请求通过本地公网代理，DNS 全部结果需为全球可路由地址；连接使用校验后的 IP，避免二次解析。重定向和子资源再经过代理校验。检测到全为 198.18/15 的 Fake-IP 时，使用固定 `1.1.1.1` HTTPS DNS 独立解析后重新验证，不放行 Fake-IP。
5. 捕获真实 URL、标题、正文、链接，发布 page_visited 与阶段截图。正文最多 100,000 字符，链接最多 120 个，DOM 等待最多 5 秒。
6. 模型通过自定义保存工具提交 Candidate，每个非空字段附原文 quote。服务端重新构造 Pydantic 模型，只有来自实际已访问页面且可逐字匹配的引用可进入核验。不存在赛事名称证据则拒收整个候选。
7. 未证实字段置 null。日期必须包含完整年份；截止已过标记已结束；没有开始、截止或当年届次，不能标记报名中；开始晚于截止或多个来源冲突均待核实。推荐理由由已证实字段与筛选条件生成，没有虚假分数。大一/大二与明确“大三及以上”等限制冲突时标记不符合。
8. 有届次的赛事按名称、届次、来源主机精确去重；无届次按来源完整 URL 区分。跨主机别名不自动合并，避免误合并赛事。每次保存立刻入库并发送 competition_found、verification_updated。
9. 完成、取消、错误、超时都关闭浏览器。失败但已有有效赛事记为 partial。SSE 与历史记录保留发生过的真实事件。

## 模型配置

DeepSeek 使用继承 Browser Use 0.13.11 `ChatDeepSeek` 的本地适配器 `backend/llm.py`，默认 `deepseek-flash`，OpenAI 兼容 `/chat/completions`。显式关闭思考，结构化结果使用官方 JSON Output，再进行 Pydantic 校验；拒绝格式错误、缺少必需字段或因 token 上限截断的输出。通用 OpenAI 兼容服务使用 `ChatOpenAI`；不承诺任意服务兼容 strict JSON schema。设置页测试会检查 Pydantic 结构化响应，但不是完整自主浏览验收。

本版采用文本 DOM 决策，`use_vision=False`，降低视觉接口差异；浏览器截图仍供用户查看。模型一次最多输出 6000 tokens，Agent 默认 25 步、每步 1 个动作、最多 2 次连续失败，模型请求最多 1 次重试。步骤和总时间受硬限制，但预算不是精确费用上限。

## 核验的边界

原文比对是保守的证据检查，无法自动证明网站身份、日期语义或网页本身的真实性。官网身份没有独立核验时 official_url 为 null，来源链接仍完整保存。不接受模型独自宣称“官方”。中文日期范围省略年份、PDF 内容、页面复杂表格或多届次混排可能导致字段留空，需人工查看原文。当前年级规则并非完整招生资格引擎。
