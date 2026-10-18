"use client";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BellRing,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  Circle,
  Compass,
  ExternalLink,
  Globe2,
  History,
  Layers3,
  ListFilter,
  LoaderCircle,
  Monitor,
  Play,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Target,
  Telescope,
  Trash2,
  Trophy,
  WandSparkles,
  X,
} from "lucide-react";
import { Button } from "./ui/button";
import {
  api,
  type Competition,
  type Event as AgentEvent,
  type Settings,
  type Task,
} from "@/lib/api";

type View = "home" | "tasks" | "competitions" | "settings";
const names: Record<string, string> = {
  queued: "等待中",
  running: "搜索中",
  cancelling: "正在取消",
  completed: "已完成",
  partial: "部分成功",
  failed: "执行失败",
  cancelled: "已取消",
  interrupted: "已中断",
};
const active = (status?: string) =>
  ["queued", "running", "cancelling"].includes(status || "");
const time = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";
const examples = [
  "适合大一新手参加的比赛",
  "计算机专业高含金量竞赛",
  "可以个人参加的 AI 比赛",
  "创新创业类大学生竞赛",
];
const stages = [
  "理解你的需求",
  "规划搜索策略",
  "搜索相关竞赛",
  "打开目标网页",
  "提取报名信息",
  "核验来源与日期",
  "生成竞赛清单",
];

export function Workspace({ view }: { view: View }) {
  const client = useQueryClient();
  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(true);
  const [busy, setBusy] = useState(false);
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () =>
      api<{ status: string; model_configured: boolean }>("/health"),
    refetchInterval: 30000,
  });
  const history = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api<Task[]>("/tasks"),
    enabled: view === "tasks",
    refetchInterval: (q) =>
      q.state.data?.some((t) => active(t.status)) ? 5000 : false,
  });
  const task = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api<Task>(`/tasks/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (q) => (active(q.state.data?.status) ? 5000 : false),
  });
  useEffect(() => {
    const id =
      new URLSearchParams(window.location.search).get("task") ||
      sessionStorage.getItem("saitan-task") ||
      "";
    if (id && view === "home") setTaskId(id);
  }, [view]);
  useEffect(() => {
    if (taskId) sessionStorage.setItem("saitan-task", taskId);
  }, [taskId]);
  useEffect(() => {
    if (!taskId || !active(task.data?.status)) return;
    const after = task.data?.events.at(-1)?.id || 0;
    const source = new EventSource(
      `/api/tasks/${taskId}/events?after=${after}`,
    );
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("progress", (message) => {
      const event: AgentEvent = JSON.parse((message as MessageEvent).data);
      client.setQueryData<Task>(["task", taskId], (old) =>
        old && !old.events.some((e) => e.id === event.id)
          ? { ...old, events: [...old.events, event] }
          : old,
      );
      if (
        ["competition_found", "verification_updated"].includes(event.type) ||
        event.type.startsWith("task_")
      )
        void client.invalidateQueries({ queryKey: ["task", taskId] });
    });
    source.addEventListener("end", () => {
      source.close();
      void client.invalidateQueries({ queryKey: ["task", taskId] });
    });
    return () => source.close();
  }, [taskId, task.data?.status, client]);
  async function start(query: string, filters: Record<string, string>) {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id: string }>("/tasks", {
        method: "POST",
        body: JSON.stringify({ query, filters }),
      });
      setTaskId(result.id);
      void client.invalidateQueries({ queryKey: ["tasks"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    setError("");
    try {
      await api(`/tasks/${taskId}/cancel`, { method: "POST" });
      void client.invalidateQueries({ queryKey: ["task", taskId] });
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <Image
              src="/brand/saitan-logo.png"
              alt="赛探 AI Logo"
              width={48}
              height={48}
              priority
            />
          </span>
          <span>
            赛探 <b>AI</b>
            <small>用 AI 帮你发现更大的舞台</small>
          </span>
        </Link>
        <nav aria-label="主导航">
          {[
            { href: "/", id: "home", label: "首页", icon: Compass },
            { href: "/tasks", id: "tasks", label: "任务记录", icon: History },
            {
              href: "/competitions",
              id: "competitions",
              label: "竞赛清单",
              icon: Trophy,
            },
            {
              href: "/settings",
              id: "settings",
              label: "设置",
              icon: Settings2,
            },
          ].map((n) => (
            <Link
              href={n.href}
              key={n.id}
              className={view === n.id ? "nav-active" : ""}
            >
              <n.icon size={16} />
              {n.label}
            </Link>
          ))}
        </nav>
        <span className="service">
          <i className={health.isSuccess ? "online" : ""} />
          {health.isSuccess ? "Agent 服务在线" : "连接服务中"}
        </span>
      </header>
      <main>
        {(error || task.error) && (
          <div role="alert" className="alert">
            {error || task.error?.message}
            <button aria-label="关闭提示" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {view === "home" && (
          <>
            <section className="hero">
              <div className="hero-copy">
                <div className="eyebrow">
                  <span /> YOUR NEXT CHALLENGE, DISCOVERED
                </div>
                <h1>
                  你的热爱，
                  <br />
                  值得一个<span>更大的舞台。</span>
                </h1>
                <p>
                  让每一个热爱探索的大学生，
                  <br />
                  不错过任何一个值得参加的竞赛。
                </p>
                <div className="hero-proof">
                  <span>
                    <Globe2 size={15} />
                    真实网页搜索
                  </span>
                  <span>
                    <ShieldCheck size={15} />
                    信息来源可溯
                  </span>
                  <span>
                    <Radio size={15} />
                    实时过程可见
                  </span>
                </div>
                <div className="orbit-art" aria-hidden="true">
                  <div className="orbit-ring ring-one" />
                  <div className="orbit-ring ring-two" />
                  <div className="orbit-core">
                    <Compass size={40} strokeWidth={1} />
                  </div>
                  <span className="orbit-star">✦</span>
                </div>
              </div>
              <SearchForm
                start={start}
                disabled={busy || active(task.data?.status)}
                configured={settings.data?.api_key_configured}
              />
            </section>
            <div className="section-heading">
              <div>
                <span className="eyebrow muted">EXPLORATION WORKSPACE</span>
                <h2>
                  探索工作台 <span>每一步，都看得见</span>
                </h2>
              </div>
              <span className="subtle small">
                由 Browser Use 驱动 <span className="dot-separator">·</span>{" "}
                本地浏览器 Agent
              </span>
            </div>
            <div className="workspace-grid">
              <AgentPanel
                task={task.data}
                connected={connected}
                onCancel={cancel}
              />
              <Results
                records={task.data?.results || []}
                task={task.data}
                taskId={taskId}
              />
            </div>
            <div className="trust-strip">
              <ShieldCheck size={18} />
              <p>
                每一条结果，都有迹可循。
                <span>
                  赛探 AI 基于智能浏览器 Agent
                  搜索、整理和核验竞赛信息；无法确认的内容会标记为待核实。
                </span>
              </p>
              <span className="outline-label">EVIDENCE FIRST</span>
            </div>
          </>
        )}
        {view === "tasks" && (
          <section className="page-section">
            <PageHeading
              eyebrow="YOUR EXPLORATIONS"
              title="每一次探索，都有记录"
              description="重新打开搜索过程、查看已发现的赛事，接着上一次的灵感出发。"
            />
            <div className="panel history-panel">
              {history.isLoading ? (
                <Loading />
              ) : history.error ? (
                <Empty title="暂时无法加载任务" text={history.error.message} />
              ) : !history.data?.length ? (
                <Empty
                  title="你的第一场探索，从这里开始"
                  text="开始一次真实搜索，执行过程和竞赛清单会自动保存在这里。"
                  action
                />
              ) : (
                history.data.map((t) => (
                  <div className="history-row" key={t.id}>
                    <div className="row-icon">
                      <Search size={20} />
                    </div>
                    <div className="history-info">
                      <Link href={`/?task=${t.id}`}>{t.query}</Link>
                      <span>
                        {time(t.created_at)} · {t.result_count} 项赛事 ·{" "}
                        {t.started_at && t.ended_at
                          ? `${Math.round((+new Date(t.ended_at) - +new Date(t.started_at)) / 1000)} 秒`
                          : "尚未结束"}
                      </span>
                    </div>
                    <span className={`status ${t.status}`}>
                      {names[t.status]}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={async () => {
                        if (
                          !confirm(
                            active(t.status)
                              ? "停止这个任务？"
                              : "删除这条任务记录？赛事仍保留在竞赛清单。",
                          )
                        )
                          return;
                        try {
                          await api(
                            `/tasks/${t.id}${active(t.status) ? "/cancel" : ""}`,
                            { method: active(t.status) ? "POST" : "DELETE" },
                          );
                          void history.refetch();
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      {active(t.status) ? (
                        <Square size={16} />
                      ) : (
                        <Trash2 size={16} />
                      )}
                      <span>{active(t.status) ? "取消" : "删除"}</span>
                    </Button>
                  </div>
                ))
              )}
            </div>
          </section>
        )}
        {view === "competitions" && <CompetitionLibrary />}
        {view === "settings" && <SettingsPanel />}
      </main>
      <footer>
        <span>
          <Image
            src="/brand/saitan-logo.png"
            alt=""
            width={22}
            height={22}
            className="footer-brand-mark"
          />{" "}
          赛探 AI <span className="subtle">/</span>{" "}
          让探索，通向可能
        </span>
        <span>
          公开信息检索 · 报名前请再次确认官方通知 <ArrowUpRight size={13} />
        </span>
      </footer>
    </div>
  );
}

function SearchForm({
  start,
  disabled,
  configured,
}: {
  start: (q: string, f: Record<string, string>) => void;
  disabled: boolean;
  configured?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({
    major: "计算机科学与技术",
    grade: "大一",
    category: "人工智能",
    participation: "个人优先",
    region: "全国",
    status: "报名中优先",
  });
  const fields = [
    {
      key: "major",
      label: "我的专业",
      options: [
        "计算机科学与技术",
        "电子信息",
        "经济管理",
        "设计艺术",
        "不限专业",
      ],
    },
    {
      key: "grade",
      label: "当前年级",
      options: ["大一", "大二", "大三", "大四", "研究生"],
    },
    {
      key: "category",
      label: "比赛方向",
      options: [
        "人工智能",
        "软件开发",
        "创新创业",
        "数学建模",
        "设计创意",
        "不限方向",
      ],
    },
    {
      key: "participation",
      label: "参赛方式",
      options: ["个人优先", "团队参赛", "不限"],
    },
    {
      key: "region",
      label: "比赛地区",
      options: ["全国", "国际", "线上", "本省"],
    },
    {
      key: "status",
      label: "报名状态",
      options: ["报名中优先", "即将开始", "全部状态"],
    },
  ];
  return (
    <form
      className="search-card"
      onSubmit={(e) => {
        e.preventDefault();
        const description = query.trim();
        const filterQuery = `寻找适合${filters.grade}学生参加的${filters.category}相关竞赛。专业：${filters.major}；参赛方式：${filters.participation}；比赛地区：${filters.region}；报名状态：${filters.status}。`;
        const searchQuery =
          description.length >= 5
            ? description
            : `${filterQuery}${description ? `补充需求：${description}` : ""}`;
        start(searchQuery, filters);
      }}
    >
      <div className="form-heading">
        <span className="tiny-icon">
          <Sparkles size={18} />
        </span>
        <h2>告诉赛探，你想挑战什么</h2>
        <span className="tag">AI SEARCH</span>
      </div>
      <div className="textarea-wrap">
        <textarea
          aria-label="竞赛搜索需求"
          aria-describedby="search-query-hint"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={1500}
          placeholder="补充你的偏好（可选），例如：想找适合新手、近期可以报名的比赛"
        />
        <span id="search-query-hint">
          <WandSparkles size={13} /> 可选 · 留空则按下方筛选条件搜索
        </span>
      </div>
      <div className="filter-grid">
        {fields.map((f) => (
          <label key={f.key}>
            {f.label}
            <div className="select-wrap">
              <select
                value={filters[f.key as keyof typeof filters]}
                onChange={(e) =>
                  setFilters({ ...filters, [f.key]: e.target.value })
                }
              >
                {f.options.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
              <ChevronDown size={13} />
            </div>
          </label>
        ))}
      </div>
      <div className="example-row">
        <span>试着问问</span>
        {examples.map((example, i) => (
          <button type="button" key={example} onClick={() => setQuery(example)}>
            {i === 0 && <Sparkles size={11} />} {example}
          </button>
        ))}
      </div>
      <div className="form-bottom">
        <span>
          {configured ? (
            <>
              <ShieldCheck size={13} /> 仅浏览公开网页，不自动报名
            </>
          ) : (
            <Link href="/settings">
              <Settings2 size={13} /> 先配置 DeepSeek API Key
            </Link>
          )}
        </span>
        <Button type="submit" disabled={disabled}>
          {disabled ? (
            <LoaderCircle className="spin" size={17} />
          ) : (
            <Sparkles size={17} />
          )}
          开始搜索 <ArrowRight size={16} />
        </Button>
      </div>
    </form>
  );
}

function AgentPanel({
  task,
  connected,
  onCancel,
}: {
  task?: Task;
  connected: boolean;
  onCancel: () => void;
}) {
  const events = task?.events || [];
  const current = events.filter((e) => e.type === "page_visited").at(-1);
  const snapshot = events.filter((e) => e.type === "browser_snapshot").at(-1);
  const stage = Math.max(
    -1,
    ...events
      .filter((e) => !e.type.startsWith("task_") || e.type === "task_completed")
      .map((e) => e.payload.stage ?? -1),
  );
  const running = active(task?.status);
  const terminal = !!task && !running;
  const complete = task?.status === "completed";
  const visited = [
    ...new Map(
      events
        .filter((e) => e.type === "page_visited")
        .map((e) => [e.payload.url, e]),
    ).values(),
  ];
  const stats = task?.stats || {
    visited: 0,
    candidates: 0,
    verified: 0,
    pending: 0,
  };
  return (
    <section className="panel agent-panel">
      <div className="panel-header">
        <h3>
          <span className="tiny-icon blue">
            <Monitor size={18} />
          </span>
          Agent 执行过程
        </h3>
        <span className={`live-badge ${running ? "is-live" : ""}`}>
          <i />
          {task ? names[task.status] : "等待开始"}
        </span>
      </div>
      {task?.error && <div className="inline-warning">{task.error}</div>}
      {running && !connected && (
        <div className="inline-warning">
          实时连接中断，正在重连；任务数据仍会自动同步。
        </div>
      )}
      <div className="browser-preview">
        <div className="browser-toolbar">
          <div className="traffic">
            <i />
            <i />
            <i />
          </div>
          <span>
            <ShieldCheck size={11} />
            {current?.payload.url
              ? new URL(current.payload.url).hostname
              : "等待 Agent 打开网页"}
          </span>
          <ExternalLink size={12} />
        </div>
        <div className={`browser-canvas ${snapshot ? "has-image" : ""}`}>
          {snapshot ? (
            <img
              src={snapshot.payload.image}
              alt={`Agent 实际访问的页面：${snapshot.payload.title}`}
            />
          ) : (
            <div className="browser-empty">
              <div className="scan-orbit">
                <Globe2 size={36} strokeWidth={1} />
                <span />
              </div>
              <b>{running ? "正在连接真实浏览器" : "浏览器已就位，等你出发"}</b>
              <p>
                {running
                  ? "页面访问成功后将在这里展示截图"
                  : "开始搜索后，实时查看 AI 正在探索的网页"}
              </p>
              <span className="preview-label">
                <span /> LIVE BROWSER PREVIEW
              </span>
            </div>
          )}
        </div>
        {current && (
          <div className="current-page">
            <Globe2 size={12} />
            <a href={current.payload.url} target="_blank" rel="noreferrer">
              {current.payload.title || current.payload.url}
            </a>
          </div>
        )}
      </div>
      <div className="timeline-heading">
        <span>执行时间线</span>
        {running ? (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            <Square size={11} />
            取消任务
          </Button>
        ) : (
          <span className="subtle small">
            {task ? time(task.created_at) : "准备探索"}
          </span>
        )}
      </div>
      <ol className="timeline">
        {stages.map((label, i) => {
          const event = events.find((e) => e.payload.stage === i);
          const done = !!event && (complete || i < stage);
          const live = running && i === stage;
          const stopped = terminal && !complete && i === stage;
          return (
            <li
              key={label}
              className={done ? "step-done" : live ? "step-live" : ""}
            >
              <span className="step-icon">
                {done ? (
                  <Check size={12} />
                ) : live ? (
                  <LoaderCircle size={12} className="spin" />
                ) : stopped ? (
                  <X size={12} />
                ) : (
                  <Circle size={7} />
                )}
              </span>
              <div>
                <span>{label}</span>
                {live && <small>{events.at(-1)?.message}</small>}
              </div>
              <span className="step-time">
                {done
                  ? event
                    ? time(event.created_at).split(" ").at(-1)
                    : "已完成"
                  : live
                    ? "进行中"
                    : stopped
                      ? "已停止"
                      : terminal
                        ? "已跳过"
                        : "等待中"}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="stats-row">
        {[
          { v: stats.visited, l: "已访问网页" },
          { v: stats.candidates, l: "候选赛事" },
          { v: stats.verified, l: "已核实原文" },
          { v: stats.pending, l: "待核实" },
        ].map((s, i) => (
          <div key={s.l}>
            <strong className={i === 2 ? "mint" : i === 3 ? "purple" : ""}>
              {s.v.toString().padStart(2, "0")}
            </strong>
            <span>{s.l}</span>
          </div>
        ))}
      </div>
      {events.length > 0 && (
        <details className="event-details">
          <summary>
            查看完整事件与访问记录 <ChevronDown size={13} />
          </summary>
          <div className="event-log">
            {events.map((e) => (
              <p key={e.id}>
                <time>{time(e.created_at)}</time>
                {e.message}
              </p>
            ))}
            {visited.map((e) => (
              <a
                key={e.id}
                href={e.payload.url}
                target="_blank"
                rel="noreferrer"
              >
                {e.payload.title || e.payload.url}
                <ExternalLink size={11} />
              </a>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

function Results({
  records,
  task,
  taskId,
  library = false,
}: {
  records: Competition[];
  task?: Task;
  taskId?: string;
  library?: boolean;
}) {
  const [status, setStatus] = useState("全部状态"),
    [category, setCategory] = useState("全部方向"),
    [sort, setSort] = useState("匹配程度"),
    [query, setQuery] = useState("");
  const shown = records
    .filter(
      (c) =>
        (status === "全部状态" || c.registration_status === status) &&
        (category === "全部方向" || c.category === category) &&
        c.name.toLowerCase().includes(query.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "赛事名称"
        ? a.name.localeCompare(b.name, "zh-CN")
        : sort === "报名截止"
          ? (a.registration_deadline || "9999").localeCompare(
              b.registration_deadline || "9999",
            )
          : b.match_count - a.match_count,
    );
  const exportPath = library ? "/api/export" : `/api/tasks/${taskId}/export`;
  return (
    <section
      className={`panel results-panel ${library ? "library-results" : ""}`}
    >
      <div className="panel-header">
        <h3>
          <span className="tiny-icon violet">
            <Trophy size={18} />
          </span>
          {library ? "全部竞赛" : "为你发现的竞赛"}{" "}
          <span className="count-badge">{records.length}</span>
        </h3>
        <details className="export-menu">
          <summary>
            <ArrowDownToLine size={14} />
            导出
            <ChevronDown size={12} />
          </summary>
          <div>
            {records.length > 0 ? (
              <>
                <a href={`${exportPath}?format=csv`}>导出 CSV</a>
                <a href={`${exportPath}?format=md`}>导出 Markdown</a>
              </>
            ) : (
              <span>暂无可导出的结果</span>
            )}
          </div>
        </details>
      </div>
      <div className="result-filters">
        {library && (
          <label className="name-search">
            <Search size={14} />
            <input
              aria-label="搜索竞赛名称"
              placeholder="搜索竞赛名称"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        )}
        <label>
          <ListFilter size={13} />
          <select
            aria-label="按方向筛选"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option>全部方向</option>
            {[...new Set(records.map((c) => c.category).filter(Boolean))].map(
              (c) => (
                <option key={c}>{c}</option>
              ),
            )}
          </select>
        </label>
        <select
          aria-label="按报名状态筛选"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {["全部状态", "报名中", "即将开始", "已结束", "待核实"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="排序方式"
          className="sort-select"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          {["匹配程度", "报名截止", "赛事名称"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="result-body">
        {shown.length ? (
          shown.map((c, i) => <CompetitionCard key={c.id} item={c} index={i} />)
        ) : (
          <div className="results-empty">
            <div className="empty-constellation">
              <div />
              <div />
              <Telescope size={48} strokeWidth={1} />
              <Sparkles className="small-spark" size={18} />
            </div>
            <span className="eyebrow muted">A WORLD OF POSSIBILITIES</span>
            <h3>
              {records.length
                ? "没有符合筛选条件的赛事"
                : active(task?.status)
                  ? "正在为你寻找值得挑战的机会"
                  : task
                    ? "本次探索暂无可保存的赛事"
                    : "下一场值得参加的竞赛，等你发现"}
            </h3>
            <p>
              {records.length
                ? "试试调整报名状态或比赛方向。"
                : active(task?.status)
                  ? "Agent 正在浏览公开网页。找到有原文依据的信息后，结果会出现在这里。"
                  : task
                    ? "可以调整需求后重新搜索。我们只保留有可追溯来源的结果。"
                    : "描述你的专业、兴趣与参赛想法，赛探会带着你的目标出发，将真实的竞赛信息整理在这里。"}
            </p>
            <div className="empty-features">
              <span>
                <Target size={16} />
                围绕你的需求
              </span>
              <span>
                <BookOpen size={16} />
                附带原始来源
              </span>
              <span>
                <BellRing size={16} />
                核对报名时间
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="results-foot">
        <ShieldCheck size={13} />
        <span>只呈现有来源的信息；未确认的字段不会被补写。</span>
        {records.length > 0 && <b>{shown.length} 项结果</b>}
      </div>
    </section>
  );
}

function CompetitionCard({
  item: c,
  index,
}: {
  item: Competition;
  index: number;
}) {
  return (
    <article className="competition-card">
      <div className="competition-top">
        <span className="competition-number">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div>
          <div className="card-tags">
            <span>{c.category || "方向待核实"}</span>
            <span>{c.edition || "届次待核实"}</span>
          </div>
          <h3>{c.name}</h3>
        </div>
        <span
          className={`registration ${c.registration_status === "报名中" ? "open" : ""}`}
        >
          {c.registration_status}
        </span>
      </div>
      <p className="competition-description">
        {c.description || "赛事介绍暂未核实，请查看来源通知。"}
      </p>
      <div className="competition-facts">
        <span>
          参赛对象 <b>{c.eligible_grades || "暂未核实"}</b>
        </span>
        <span>
          参赛方式 <b>{c.participation_type || "暂未核实"}</b>
        </span>
        <span>
          报名开始 <b>{c.registration_start || "暂未核实"}</b>
        </span>
        <span>
          报名截止 <b>{c.registration_deadline || "暂未核实"}</b>
        </span>
      </div>
      <div className="recommendation">
        <Sparkles size={13} />
        <span>{c.recommendation_reason}</span>
      </div>
      <details className="competition-details">
        <summary>
          查看详情与核验证据
          <ChevronDown size={13} />
        </summary>
        <dl>
          {[
            ["主办单位", c.organizer],
            ["专业要求", c.eligible_majors],
            ["团队人数", c.team_size],
            ["资格匹配", c.eligibility_match],
            ["官方网站", c.official_url],
          ].map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v || "暂未核实"}</dd>
            </div>
          ))}
        </dl>
        {c.conflicts?.map((x) => (
          <p className="inline-warning" key={x}>
            {x}
          </p>
        ))}
        {c.sources.map((s) => (
          <div className="source-evidence" key={s.url}>
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.title || s.url}
              <ExternalLink size={12} />
            </a>
            <small>{s.source_type} · 原文已比对</small>
            <blockquote>{s.excerpt}</blockquote>
          </div>
        ))}
      </details>
      <div className="competition-footer">
        <span>
          <CheckCheck size={13} />
          {c.verification_status} · {time(c.last_verified_at)}
        </span>
        <a href={c.source_urls[0]} target="_blank" rel="noreferrer">
          查看来源
          <ArrowUpRight size={14} />
        </a>
      </div>
    </article>
  );
}

function CompetitionLibrary() {
  const records = useQuery({
    queryKey: ["competitions"],
    queryFn: () => api<Competition[]>("/competitions"),
  });
  return (
    <section className="page-section">
      <PageHeading
        eyebrow="YOUR OPPORTUNITY LIBRARY"
        title="让好机会，成为你的收藏"
        description="汇集历次搜索发现的真实赛事。保留来源，按需筛选，随时导出。"
      />
      {records.isLoading ? (
        <Loading />
      ) : records.error ? (
        <Empty title="加载失败" text={records.error.message} />
      ) : (
        <Results records={records.data || []} library />
      )}
    </section>
  );
}

function SettingsPanel() {
  const client = useQueryClient();
  const saved = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  const [form, setForm] = useState<Settings | null>(null),
    [key, setKey] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (saved.data) setForm(saved.data);
  }, [saved.data]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setMessage("");
    try {
      await api("/settings", {
        method: "PUT",
        body: JSON.stringify({ ...form, api_key: key || undefined }),
      });
      setKey("");
      await client.invalidateQueries({ queryKey: ["settings"] });
      setMessage("设置已保存，密钥仅在后端使用。");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function test() {
    setBusy(true);
    setMessage("");
    try {
      const r = await api<{ message: string }>("/settings/test", {
        method: "POST",
      });
      setMessage(r.message);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="page-section settings-section">
      <PageHeading
        eyebrow="MADE FOR YOUR WORKFLOW"
        title="配置好，一起去探索"
        description="连接你的模型服务，设定合理的搜索预算。API Key 不会回显到浏览器。"
      />
      {saved.error ? (
        <Empty title="无法连接后端" text={saved.error.message} />
      ) : !form ? (
        <Loading />
      ) : (
        <form className="settings-grid" onSubmit={save}>
          <div className="panel settings-card">
            <h3>
              <Sparkles size={18} />
              模型连接{" "}
              <span
                className={`status ${form.api_key_configured ? "completed" : ""}`}
              >
                {form.api_key_configured ? "已配置密钥" : "等待配置"}
              </span>
            </h3>
            <label>
              LLM Provider
              <select
                value={form.llm_provider}
                onChange={(e) =>
                  setForm({ ...form, llm_provider: e.target.value })
                }
              >
                <option value="deepseek">DeepSeek · OpenAI 兼容接口</option>
                <option value="openai-compatible">OpenAI 兼容 API</option>
              </select>
            </label>
            <label>
              Model Name
              <input
                value={form.model}
                required
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
              <small>DeepSeek V4.1 Flash 的官方模型 ID：deepseek-flash</small>
            </label>
            <label>
              API Base URL
              <input
                type="url"
                value={form.api_base_url}
                required
                onChange={(e) =>
                  setForm({ ...form, api_base_url: e.target.value })
                }
              />
            </label>
            <label>
              API Key
              <input
                type="password"
                autoComplete="new-password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={
                  form.api_key_configured
                    ? "已保存 · 留空保留现有密钥"
                    : "输入你的 API Key"
                }
              />
              <small>
                <ShieldCheck size={12} /> Windows 使用 DPAPI
                加密保存，仅当前系统账户可解密。
              </small>
            </label>
            <div className="settings-buttons">
              <Button disabled={busy} type="submit">
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Check size={15} />
                )}
                保存配置
              </Button>
              <Button
                disabled={busy || !form.api_key_configured}
                type="button"
                variant="outline"
                onClick={test}
              >
                <Radio size={15} />
                测试模型连接
              </Button>
            </div>
            <p className="subtle small">
              请先保存再测试。连通测试验证结构化响应，完整浏览能力需要通过一次真实搜索确认。
            </p>
          </div>
          <div className="settings-right">
            <div className="panel settings-card">
              <h3>
                <Layers3 size={18} />
                搜索预算
              </h3>
              <div className="budget-grid">
                {[
                  {
                    key: "default_count",
                    label: "默认赛事数量",
                    min: 1,
                    max: 20,
                  },
                  { key: "max_steps", label: "最大执行步骤", min: 3, max: 80 },
                  { key: "max_pages", label: "最大访问页面", min: 2, max: 40 },
                  {
                    key: "timeout_seconds",
                    label: "搜索超时（秒）",
                    min: 30,
                    max: 900,
                  },
                ].map((f) => (
                  <label key={f.key}>
                    {f.label}
                    <input
                      type="number"
                      min={f.min}
                      max={f.max}
                      value={form[f.key as keyof Settings] as number}
                      onChange={(e) =>
                        setForm({ ...form, [f.key]: Number(e.target.value) })
                      }
                    />
                  </label>
                ))}
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.headless}
                  onChange={(e) =>
                    setForm({ ...form, headless: e.target.checked })
                  }
                />
                无头浏览器模式（页面仍提供真实截图）
              </label>
              <p className="subtle small">
                每次只执行一个任务，避免浏览器资源和模型成本失控。
              </p>
            </div>
            <div className="panel settings-card">
              <h3>
                <ShieldCheck size={18} />
                本地数据
              </h3>
              <p>搜索历史、原文证据和截图保存在本机。</p>
              <Button
                variant="destructive"
                type="button"
                onClick={async () => {
                  if (
                    !confirm(
                      "清空数据库中的全部任务和赛事？此操作不可撤销，截图文件需手动清理。",
                    )
                  )
                    return;
                  try {
                    const r = await api<{ message: string }>("/data", {
                      method: "DELETE",
                    });
                    sessionStorage.removeItem("saitan-task");
                    await client.invalidateQueries();
                    setMessage(r.message);
                  } catch (e) {
                    setMessage((e as Error).message);
                  }
                }}
              >
                <Trash2 size={14} />
                清空本地记录
              </Button>
            </div>
          </div>
        </form>
      )}
      {message && (
        <div role="status" className="settings-message">
          {message}
        </div>
      )}
    </section>
  );
}
function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="page-heading">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}
function Empty({
  title,
  text,
  action = false,
}: {
  title: string;
  text: string;
  action?: boolean;
}) {
  return (
    <div className="general-empty">
      <Compass size={36} />
      <h3>{title}</h3>
      <p>{text}</p>
      {action && (
        <Button asChild>
          <Link href="/">
            开始探索
            <ArrowRight size={15} />
          </Link>
        </Button>
      )}
    </div>
  );
}
function Loading() {
  return (
    <div className="general-empty">
      <LoaderCircle className="spin" />
      <p>正在读取本地数据…</p>
    </div>
  );
}
