import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Database,
  LogOut,
  MessagesSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`;
const ERP_URL = import.meta.env.VITE_ERP_URL || `${window.location.protocol}//${window.location.hostname}:8080`;

function App() {
  const [token, setToken] = useState(localStorage.getItem("agent_token") || "");
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [health, setHealth] = useState(null);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [searchText, setSearchText] = useState("");
  const [showTools, setShowTools] = useState(true);

  useEffect(() => {
    if (!token) return;
    localStorage.setItem("agent_token", token);
    api("/api/auth/me", token).then(setUser).catch(() => logout());
  }, [token]);

  useEffect(() => {
    if (!token) return;
    refresh();
    const id = setInterval(refresh, 2500);
    return () => clearInterval(id);
  }, [token]);

  function logout() {
    localStorage.removeItem("agent_token");
    setToken("");
    setUser(null);
    setTasks([]);
    setHealth(null);
    setSelectedConversationId("");
  }

  async function refresh(nextSelectedId = selectedConversationId) {
    if (!token) return;
    const [nextTasks, nextHealth] = await Promise.all([
      api("/api/agent/tasks", token).catch(() => []),
      api("/api/erp/health", token).catch((error) => ({ ok: false, detail: error.message })),
    ]);
    setTasks(nextTasks);
    setHealth(nextHealth);
    if (nextSelectedId) {
      setSelectedConversationId(nextSelectedId);
    }
  }

  if (!token) {
    return <Login onToken={setToken} />;
  }

  const conversations = groupConversations(tasks);
  const visibleConversations = conversations.filter((conversation) =>
    conversation.title.toLowerCase().includes(searchText.toLowerCase()),
  );
  const selectedConversation = selectedConversationId
    ? visibleConversations.find((conversation) => conversation.id === selectedConversationId) || null
    : null;
  const selectedConversationTasks = selectedConversation ? selectedConversation.tasks : [];

  return (
    <div className="app-shell">
      <ConversationSidebar
        currentUser={user}
        onLogout={logout}
        onNewChat={() => setSelectedConversationId("")}
        onOpenLatest={() => {
          const latestConversation = groupConversations(tasks)[0];
          if (latestConversation) {
            setSelectedConversationId(latestConversation.id);
          }
        }}
        searchText={searchText}
        selectedConversationId={selectedConversationId}
        conversations={visibleConversations}
        onSearch={setSearchText}
        onSelectConversation={(conversationId) => {
          setSelectedConversationId(conversationId);
        }}
      />

      <main className="chat-workspace">
        <header className="chat-topbar">
          <div>
            <p className="eyebrow">E-commerce ERP Copilot</p>
            <h1>{viewTitle(selectedConversation)}</h1>
          </div>
          <Health health={health} onRefresh={refresh} />
        </header>

        <ChatView
          selectedConversation={selectedConversation}
          tasks={selectedConversationTasks}
          showTools={showTools}
          setShowTools={setShowTools}
          token={token}
          onCreated={(conversationId) => {
            setSelectedConversationId(conversationId);
            refresh(conversationId);
          }}
        />
      </main>
    </div>
  );
}

function ConversationSidebar({
  currentUser,
  onLogout,
  onNewChat,
  onOpenLatest,
  searchText,
  selectedConversationId,
  conversations,
  onSearch,
  onSelectConversation,
}) {
  return (
    <aside className="conversation-sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark"><Activity size={24} /></div>
        <div>
          <strong>Moonsea Ops</strong>
          <span>ERP Agent Console</span>
        </div>
      </div>

      <button className="new-chat-btn" onClick={onNewChat}>
        <Plus size={18} />新建对话
      </button>

      <div className="sidebar-nav">
        <button type="button" className="active" onClick={onOpenLatest}>
          <MessagesSquare size={18} />会话
        </button>
        <a className="sidebar-link" href={ERP_URL} target="_blank" rel="noreferrer">
          <Database size={18} />ERP
        </a>
      </div>

      <label className="search-box">
        <Search size={17} />
        <input value={searchText} onChange={(event) => onSearch(event.target.value)} placeholder="搜索会话..." />
      </label>

      <div className="history-block">
        <span className="history-label">历史记录</span>
        <div className="history-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              className={`history-item ${selectedConversationId === conversation.id ? "active" : ""}`}
              onClick={() => onSelectConversation(conversation.id)}
            >
              <strong>{conversation.title}</strong>
              <span>{relativeTime(conversation.updated_at)}</span>
            </button>
          ))}
          {!conversations.length && <p className="empty-history">暂无会话</p>}
        </div>
      </div>

      <div className="sidebar-footer">
        <div>
          <span>当前用户</span>
          <strong>{currentUser?.username || "..."}</strong>
        </div>
        <button className="logout-btn" onClick={onLogout} title="退出">
          <LogOut size={17} />
        </button>
      </div>
    </aside>
  );
}

function Login({ onToken }) {
  const [username, setUsername] = useState("operator");
  const [password, setPassword] = useState("operator123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await post("/api/auth/login", { username, password });
      onToken(data.token);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-panel" onSubmit={submit}>
        <div className="sidebar-brand login-brand">
          <div className="brand-mark"><Activity size={28} /></div>
          <div>
            <strong>Moonsea Ops</strong>
            <span>ERP Agent Console</span>
          </div>
        </div>
        <label htmlFor="agent-username">
          <span>用户名</span>
          <input
            id="agent-username"
            name="username"
            type="text"
            autoComplete="username"
            spellCheck="false"
            autoCapitalize="off"
            autoCorrect="off"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label htmlFor="agent-password">
          <span>密码</span>
          <input
            id="agent-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="error-line">{error}</p>}
        <div className="login-actions">
          <button type="button" className="ghost-btn" onClick={() => { setUsername(""); setPassword(""); }} disabled={busy}>
            清空
          </button>
          <button type="submit" className="primary-btn" disabled={busy}>
            <ShieldCheck size={18} />{busy ? "登录中" : "进入控制台"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Health({ health, onRefresh }) {
  const ok = health?.ok;
  return (
    <div className={`health-card ${ok ? "ok" : "bad"}`}>
      {ok ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
      <div>
        <span>ERP 连接</span>
        <strong>{ok ? "正常" : "待检查"}</strong>
      </div>
      <button className="health-refresh" onClick={onRefresh} title="刷新"><RefreshCw size={17} /></button>
    </div>
  );
}

function ChatView({ selectedConversation, tasks, showTools, setShowTools, token, onCreated }) {
  return (
    <section className="chat-view">
      <div className="message-stream">
        {!selectedConversation ? (
          <WelcomePanel />
        ) : (
          <>
            {tasks.map((task) => (
              <ChatTurn key={task.task_id} task={task} showTools={showTools} />
            ))}
          </>
        )}
      </div>
      {selectedConversation && <HumanLoopPanel task={tasks[tasks.length - 1]} />}
      <ChatComposer
        conversationId={selectedConversation?.id || ""}
        showTools={showTools}
        setShowTools={setShowTools}
        token={token}
        onCreated={onCreated}
      />
    </section>
  );
}

function WelcomePanel() {
  return (
    <div className="welcome-panel">
      <div className="welcome-mark"><Bot size={42} /></div>
      <h2>把运营目标发给 Agent</h2>
      <p>它会规划步骤、调用 ERP 工具、展示可观察执行过程，并在完成后给出最终运营建议。</p>
    </div>
  );
}

function ChatComposer({ conversationId, showTools, setShowTools, token, onCreated }) {
  const presets = [
    "分析最近30天销售订单，找出库存风险，并给出补货建议。只分析，不要修改 ERP 数据。",
    "查询 AGENT-DEMO 开头的商品，并总结库存情况。只分析，不要修改 ERP 数据。",
    "生成一份电商运营巡检报告，包含订单、库存和补货建议。只分析，不要修改 ERP 数据。",
  ];
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      const data = await apiPost("/api/agent/run", token, { prompt, conversation_id: conversationId || null });
      onCreated(data.conversation_id);
      setPrompt("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="chat-composer" onSubmit={submit}>
      <div className="preset-row">
        {presets.map((preset) => (
          <button key={preset} type="button" onClick={() => setPrompt(preset)}>
            {summarizeTitle(preset)}
          </button>
        ))}
      </div>
      <label className="tool-toggle">
        <input type="checkbox" checked={showTools} onChange={(event) => setShowTools(event.target.checked)} />
        <span>显示工具调用</span>
      </label>
      <div className="composer-box">
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="输入消息，Enter 发送..."
          rows={2}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button className="send-btn" disabled={busy || !prompt.trim()}>
          <Send size={19} />{busy ? "运行中" : "发送"}
        </button>
      </div>
    </form>
  );
}

function ChatTurn({ task, showTools }) {
  const trace = extractTrace(task);
  const finalAnswer = task.status === "succeeded" ? formatResult(task.result) : "";
  const isRunning = task.status === "running" || task.status === "queued";

  return (
    <article className="chat-turn">
      <div className="chat-message user">
        <div className="message-bubble user-bubble">
          <p>{task.prompt}</p>
        </div>
        <div className="round-avatar user-avatar"><UserRound size={18} /></div>
      </div>

      <div className="chat-message agent">
        <div className="round-avatar agent-avatar"><Bot size={18} /></div>
        <div className="message-bubble agent-bubble">
          <div className="agent-head">
            <span>AI</span>
            <Status status={task.status} />
          </div>
          {isRunning && <TypingLine />}
          {task.error && <pre className="error-box">{task.error}</pre>}
          {showTools && <TraceDetails trace={trace} collapsed={task.status === "succeeded"} />}
          {finalAnswer && (
            <div className="final-answer">
              <strong>最终答复</strong>
              <MarkdownView content={finalAnswer} />
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function TypingLine() {
  return (
    <div className="typing-line">
      <i />
      <i />
      <i />
      <em>正在生成回复...</em>
    </div>
  );
}

function TraceDetails({ trace, collapsed }) {
  return (
    <details className="trace-details" open={!collapsed}>
      <summary>
        <ChevronDown size={16} />
        <span>工具调用与执行过程</span>
        <em>{trace.length ? `${trace.length} 条` : "等待中"}</em>
      </summary>
      {trace.length ? (
        <div className="trace-list">
          {trace.map((item) => (
            <div key={item.id} className={`trace-item ${item.kind}`}>
              <Wrench size={15} />
              <div>
                <strong>{item.title}</strong>
                {item.detail && <pre>{item.detail}</pre>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted-line">等待 Agent 返回工具调用和中间执行记录。</p>
      )}
    </details>
  );
}

function MarkdownView({ content }) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);
  return <div className="markdown-view">{blocks}</div>;
}

function HumanLoopPanel({ task }) {
  if (!["waiting_approval", "needs_input"].includes(task.status)) return null;
  const needsApproval = task.status === "waiting_approval";
  return (
    <div className="hitl-panel">
      <div>
        <strong>{needsApproval ? "需要人工审批" : "需要补充信息"}</strong>
        <p>{needsApproval ? "Agent 遇到敏感 ERP 操作，已暂停执行，等待用户确认。" : "Agent 缺少继续执行所需的信息，请补充后继续。"}</p>
      </div>
      <div className="hitl-actions">
        {needsApproval ? (
          <>
            <button type="button" className="ghost-btn">拒绝</button>
            <button type="button" className="primary-btn">批准继续</button>
          </>
        ) : (
          <button type="button" className="primary-btn">补充信息</button>
        )}
      </div>
    </div>
  );
}

function Status({ status }) {
  const labels = { queued: "排队", running: "运行中", succeeded: "完成", failed: "失败", cancelled: "取消" };
  return <span className={`status ${status}`}>{labels[status] || status}</span>;
}

function viewTitle(selectedConversation) {
  return selectedConversation ? selectedConversation.title : "运营 Agent";
}

function groupConversations(tasks) {
  const map = new Map();
  tasks.forEach((task) => {
    const id = task.conversation_id || task.task_id;
    const existing = map.get(id);
    if (existing) {
      existing.tasks.push(task);
      existing.updated_at = task.updated_at > existing.updated_at ? task.updated_at : existing.updated_at;
      return;
    }
    map.set(id, {
      id,
      title: task.conversation_title || summarizeTitle(task.prompt),
      created_at: task.created_at,
      updated_at: task.updated_at,
      tasks: [task],
    });
  });
  return [...map.values()]
    .map((conversation) => ({
      ...conversation,
      tasks: conversation.tasks.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)),
    }))
    .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
}

function summarizeTitle(prompt) {
  const normalized = prompt.replace(/[。！？.!?\n\r]+/g, " ").replace(/\s+/g, " ").trim();
  if (!normalized) return "新的运营会话";
  const cleaned = normalized
    .replace(/只分析.*$/, "")
    .replace(/不要修改.*$/, "")
    .replace(/^请帮我/, "")
    .replace(/^帮我/, "")
    .replace(/^分析/, "")
    .replace(/^查询/, "")
    .replace(/^生成一份/, "")
    .replace(/^生成/, "")
    .trim();
  const firstClause = cleaned.split(/[，,；;、]/).filter(Boolean)[0] || cleaned;
  return truncateText(firstClause, 16);
}

function relativeTime(value) {
  const delta = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(delta / 60000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

function formatResult(result) {
  if (typeof result === "string") return extractLegacyContent(result);
  if (result?.messages?.length) {
    const last = normalizeMessage(result.messages[result.messages.length - 1]);
    return extractLegacyContent(last.content || JSON.stringify(last, null, 2));
  }
  return JSON.stringify(result, null, 2);
}

function extractTrace(task) {
  const messages = task.result?.messages || [];
  const rows = [];

  if (task.status === "queued") rows.push({ id: `${task.task_id}-queued`, kind: "state", title: "任务已进入队列", detail: "" });
  if (task.status === "running") rows.push({ id: `${task.task_id}-running`, kind: "state", title: "Agent 正在执行", detail: "" });

  messages.forEach((message, index) => {
    const normalized = normalizeMessage(message);
    const role = normalized.type || normalized.role || "message";
    const toolCalls = normalized.tool_calls || normalized.additional_kwargs?.tool_calls || [];
    toolCalls.forEach((toolCall, toolIndex) => {
      const name = toolCall.name || toolCall.function?.name || "tool";
      const args = toolCall.args || toolCall.function?.arguments || {};
      rows.push({
        id: `${task.task_id}-${index}-tool-${toolIndex}`,
        kind: "tool",
        title: `调用工具：${name}`,
        detail: compactJson(args),
      });
    });

    if (role === "tool") {
      rows.push({
        id: `${task.task_id}-${index}-tool-result`,
        kind: "tool-result",
        title: `工具返回：${normalized.name || "tool"}`,
        detail: truncateText(normalized.content || "", 700),
      });
    }

    if (role === "ai" && normalized.content && index < messages.length - 1) {
      rows.push({
        id: `${task.task_id}-${index}-ai-note`,
        kind: "note",
        title: "Agent 中间输出",
        detail: truncateText(normalized.content, 500),
      });
    }
  });

  return rows;
}

function parseMarkdownBlocks(content) {
  const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(
        <pre key={`code-${blocks.length}`} className="markdown-code">
          <code data-lang={lang}>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    if (/^#{1,6}\s+/.test(line)) {
      const level = line.match(/^#{1,6}/)?.[0].length || 1;
      const text = line.replace(/^#{1,6}\s+/, "");
      const Tag = `h${level}`;
      blocks.push(
        <Tag key={`h-${blocks.length}`} className="markdown-heading">
          {renderInlineMarkdown(text)}
        </Tag>,
      );
      i += 1;
      continue;
    }

    if (/^(\-|\*|\+)\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^(\-|\*|\+)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^(\-|\*|\+)\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="markdown-list">
          {items.map((item, index) => (
            <li key={index}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ol key={`ol-${blocks.length}`} className="markdown-list">
          {items.map((item, index) => (
            <li key={index}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    if (/^\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1].replace(/\s+/g, ""))) {
      const rows = [];
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
        rows.push(lines[i]);
        i += 1;
      }
      blocks.push(parseMarkdownTable(rows, blocks.length));
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !/^#{1,6}\s+/.test(lines[i]) && !/^\d+\.\s+/.test(lines[i]) && !/^(\-|\*|\+)\s+/.test(lines[i]) && !lines[i].startsWith("```")) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    blocks.push(
      <p key={`p-${blocks.length}`} className="markdown-paragraph">
        {renderInlineMarkdown(paragraph.join(" "))}
      </p>,
    );
  }

  return blocks;
}

function parseMarkdownTable(rows, keySeed) {
  const cells = rows.map((row) =>
    row
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim()),
  );
  const [header, ...body] = cells;
  return (
    <div key={`table-${keySeed}`} className="markdown-table-wrap">
      <table className="markdown-table">
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th key={index}>{renderInlineMarkdown(cell)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{renderInlineMarkdown(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderInlineMarkdown(text) {
  const parts = [];
  const source = String(text || "");
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(source))) {
    if (match.index > lastIndex) {
      parts.push(source.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={`${match.index}-strong`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      parts.push(<em key={`${match.index}-em`}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith("`")) {
      parts.push(<code key={`${match.index}-code`} className="inline-code">{token.slice(1, -1)}</code>);
    } else if (token.startsWith("[")) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        parts.push(
          <a key={`${match.index}-link`} href={linkMatch[2]} target="_blank" rel="noreferrer">
            {linkMatch[1]}
          </a>,
        );
      }
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < source.length) {
    parts.push(source.slice(lastIndex));
  }

  return parts.length ? parts : source;
}

function normalizeMessage(message) {
  if (typeof message === "string") {
    return { type: "ai", content: extractLegacyContent(message), raw: message };
  }
  if (message?.data) {
    return {
      type: message.type || message.data.type,
      name: message.data.name,
      content: message.data.content,
      tool_calls: message.data.tool_calls || message.data.additional_kwargs?.tool_calls || [],
      additional_kwargs: message.data.additional_kwargs || {},
    };
  }
  return message || {};
}

function extractLegacyContent(value) {
  if (typeof value !== "string") return value;
  if (!value.startsWith("content=")) return value;
  const match = value.match(/^content=(['"])([\s\S]*?)\1\s+additional_kwargs=/);
  if (!match) return value;
  try {
    return JSON.parse(`"${match[2].replace(/"/g, '\\"')}"`);
  } catch {
    return match[2].replace(/\\n/g, "\n").replace(/\\'/g, "'");
  }
}

function compactJson(value) {
  if (typeof value === "string") return truncateText(value, 500);
  return truncateText(JSON.stringify(value, null, 2), 500);
}

function truncateText(value, maxLength) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

async function post(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(response);
}

async function api(path, token) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parse(response);
}

async function apiPost(path, token, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(response);
}

async function parse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}

createRoot(document.getElementById("root")).render(<App />);
