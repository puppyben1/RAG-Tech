import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Database,
  FileSearch,
  Files,
  MessageSquareText,
  Settings,
} from "lucide-react";
import { apiRequest, getInitialApiBase, saveApiBase } from "./api.js";
import { Badge, EmptyState, ErrorBox, EvidenceCard, HealthBadge, MetricCard } from "./components.jsx";

const navItems = [
  { key: "dashboard", label: "工作台", icon: Activity },
  { key: "ask", label: "问答", icon: MessageSquareText },
  { key: "search", label: "证据检索", icon: FileSearch },
  { key: "documents", label: "文档库", icon: Files },
  { key: "status", label: "知识库状态", icon: Database },
  { key: "eval", label: "评测中心", icon: BarChart3 },
];

const sampleQuestion =
  "根据 Excel 附件《2023年10月人身险公司经营情况表》（工作表：人身保险公司（月度） ），“原保险保费收入”在“本年累计/截至当期”口径下的数值是多少？";

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [apiBase, setApiBase] = useState(getInitialApiBase);
  const [health, setHealth] = useState("unknown");
  const current = useMemo(() => navItems.find((item) => item.key === tab), [tab]);

  useEffect(() => {
    saveApiBase(apiBase);
  }, [apiBase]);

  async function checkHealth() {
    try {
      const data = await apiRequest(apiBase, "/health");
      setHealth(data.status === "ok" ? "ok" : "error");
    } catch {
      setHealth("error");
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">金融监管可信 RAG</div>
        <nav className="nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <h1>{current?.label}</h1>
          <div className="api-base">
            <HealthBadge status={health} />
            <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} aria-label="API Base" />
            <button className="icon-button" onClick={checkHealth} title="检查 API">
              <Settings size={18} />
            </button>
          </div>
        </header>
        {tab === "dashboard" && <DashboardPage apiBase={apiBase} setTab={setTab} />}
        {tab === "ask" && <AskPage apiBase={apiBase} />}
        {tab === "search" && <SearchPage apiBase={apiBase} />}
        {tab === "documents" && <DocumentsPage apiBase={apiBase} />}
        {tab === "status" && <StatusPage apiBase={apiBase} />}
        {tab === "eval" && <EvalPage apiBase={apiBase} />}
      </main>
    </div>
  );
}

function DashboardPage({ apiBase, setTab }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest(apiBase, "/kb/status").then(setStatus).catch((err) => setError(err.message));
  }, [apiBase]);

  return (
    <div className="stack">
      <ErrorBox message={error} />
      <section className="metrics-grid">
        <MetricCard label="文档" value={status?.documents} tone="blue" />
        <MetricCard label="文本块" value={status?.text_chunks} />
        <MetricCard label="表格事实" value={status?.table_cells} />
        <MetricCard label="行级证据" value={status?.table_rows} />
        <MetricCard label="错误" value={status?.error_count} tone={status?.error_count ? "red" : "green"} />
      </section>
      <section className="panel command-panel">
        <button className="primary" onClick={() => setTab("ask")}>进入问答</button>
        <button className="secondary" onClick={() => setTab("search")}>检索证据</button>
        <button className="secondary" onClick={() => setTab("eval")}>运行评测</button>
      </section>
    </div>
  );
}

function AskPage({ apiBase }) {
  const [mode, setMode] = useState("qa");
  const [qaId, setQaId] = useState("Q001");
  const [question, setQuestion] = useState(sampleQuestion);
  const [optionsText, setOptionsText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const payload = mode === "qa" ? { qa_id: qaId } : { question };
      if (mode !== "qa" && optionsText.trim()) {
        payload.options = JSON.parse(optionsText);
      }
      setResult(await apiRequest(apiBase, "/ask", payload));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="content-grid">
      <section className="panel">
        <h2>输入</h2>
        <label>模式</label>
        <select value={mode} onChange={(event) => setMode(event.target.value)}>
          <option value="qa">按 QA 编号</option>
          <option value="question">自定义问题</option>
        </select>
        {mode === "qa" ? (
          <>
            <label>QA 编号</label>
            <input value={qaId} onChange={(event) => setQaId(event.target.value)} />
          </>
        ) : (
          <>
            <label>问题</label>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            <label>选项 JSON</label>
            <textarea
              value={optionsText}
              onChange={(event) => setOptionsText(event.target.value)}
              placeholder='{"A":"选项 A","B":"选项 B","C":"选项 C","D":"选项 D"}'
            />
          </>
        )}
        <div className="actions">
          <button className="primary" onClick={submit} disabled={loading}>
            {loading ? "处理中" : "提交"}
          </button>
          <button className="secondary" onClick={() => setResult(null)}>清空</button>
        </div>
        <ErrorBox message={error} />
      </section>
      <section className="result">
        <h2>答案</h2>
        {result ? (
          <>
            <div className="answer">{String(result.answer_text ?? result.answer ?? "无答案")}</div>
            <div className="meta">
              <Badge tone={result.confidence === "high" ? "green" : "neutral"}>{result.confidence}</Badge>
              <Badge>{result.route}</Badge>
              {result.answer && <Badge>选项 {result.answer}</Badge>}
            </div>
            <EvidenceList items={result.evidence || []} />
          </>
        ) : (
          <EmptyState>等待提交</EmptyState>
        )}
      </section>
    </div>
  );
}

function SearchPage({ apiBase }) {
  const [query, setQuery] = useState("银行函证 工作质量 效率");
  const [sourceType, setSourceType] = useState("pdf");
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setLoading(true);
    setError("");
    try {
      setResult(await apiRequest(apiBase, "/search", { query, source_type: sourceType || null, top_k: topK }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="content-grid">
      <section className="panel">
        <h2>检索条件</h2>
        <label>关键词</label>
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
        <div className="form-row">
          <div>
            <label>文件类型</label>
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="">全部</option>
              <option value="excel">Excel</option>
              <option value="word">Word</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
          <div>
            <label>Top K</label>
            <input type="number" min="1" max="50" value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
          </div>
        </div>
        <div className="actions">
          <button className="primary" onClick={submit} disabled={loading}>
            {loading ? "检索中" : "检索"}
          </button>
        </div>
        <ErrorBox message={error} />
      </section>
      <section className="result">
        <h2>结果</h2>
        {result ? (
          <>
            <div className="status-line">
              <Badge>{result.index}</Badge>
              <Badge>命中 {result.total}</Badge>
              <Badge>展示 {result.results.length}</Badge>
            </div>
            <EvidenceList items={result.results || []} />
          </>
        ) : (
          <EmptyState>等待检索</EmptyState>
        )}
      </section>
    </div>
  );
}

function DocumentsPage({ apiBase }) {
  const [sourceType, setSourceType] = useState("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const params = new URLSearchParams();
      if (sourceType) params.set("source_type", sourceType);
      if (query) params.set("query", query);
      params.set("limit", "50");
      setResult(await apiRequest(apiBase, `/documents?${params.toString()}`));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="stack">
      <section className="panel">
        <div className="form-row">
          <div>
            <label>文件类型</label>
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="">全部</option>
              <option value="excel">Excel</option>
              <option value="word">Word</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
          <div>
            <label>标题关键词</label>
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
        </div>
        <div className="actions">
          <button className="primary" onClick={load}>查询</button>
        </div>
        <ErrorBox message={error} />
      </section>
      <section className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>doc_id</th>
              <th>标题</th>
              <th>类型</th>
              <th>期间</th>
              <th>文件名</th>
            </tr>
          </thead>
          <tbody>
            {(result?.documents || []).map((doc) => (
              <tr key={doc.doc_id}>
                <td>{doc.doc_id}</td>
                <td>{doc.title}</td>
                <td>{doc.source_type}</td>
                <td>{doc.period || "-"}</td>
                <td>{doc.file_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function StatusPage({ apiBase }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setStatus(await apiRequest(apiBase, "/kb/status"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, [apiBase]);

  return (
    <div className="stack">
      <section className="metrics-grid">
        <MetricCard label="文档" value={status?.documents} />
        <MetricCard label="已处理" value={status?.processed_documents} />
        <MetricCard label="文本块" value={status?.text_chunks} />
        <MetricCard label="表格事实" value={status?.table_cells} />
        <MetricCard label="行级证据" value={status?.table_rows} />
        <MetricCard label="错误" value={status?.error_count} tone={status?.error_count ? "red" : "green"} />
      </section>
      <section className="panel">
        <div className="actions top-actions">
          <button className="secondary" onClick={load}>刷新</button>
        </div>
        <ErrorBox message={error} />
        {status ? <pre className="json-view">{JSON.stringify(status, null, 2)}</pre> : <EmptyState />}
      </section>
    </div>
  );
}

function EvalPage({ apiBase }) {
  const [scope, setScope] = useState("excel");
  const [result, setResult] = useState(null);
  const [trusted, setTrusted] = useState(null);
  const [trustedType, setTrustedType] = useState("summary");
  const [loading, setLoading] = useState(false);
  const [trustedLoading, setTrustedLoading] = useState(false);
  const [error, setError] = useState("");
  const [trustedError, setTrustedError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      setResult(await apiRequest(apiBase, "/eval", { scope }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadTrusted(type = trustedType) {
    setTrustedLoading(true);
    setTrustedError("");
    try {
      const path = type === "summary" ? "/eval/trusted/summary" : `/eval/trusted/${type}`;
      setTrusted(await apiRequest(apiBase, path));
      setTrustedType(type);
    } catch (err) {
      setTrustedError(err.message);
    } finally {
      setTrustedLoading(false);
    }
  }

  useEffect(() => {
    loadTrusted("summary");
  }, [apiBase]);

  return (
    <div className="content-grid">
      <section className="panel">
        <h2>评测任务</h2>
        <label>范围</label>
        <select value={scope} onChange={(event) => setScope(event.target.value)}>
          <option value="excel">Excel</option>
          <option value="text">Word/PDF</option>
          <option value="all">全部</option>
        </select>
        <div className="actions">
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? "评测中" : "运行评测"}
          </button>
        </div>
        <ErrorBox message={error} />
      </section>
      <section className="result">
        <h2>指标</h2>
        {result ? (
          <>
            <div className="answer">{result.correct} / {result.total}</div>
            <div className="meta">
              <Badge tone="green">accuracy {Number(result.accuracy).toFixed(4)}</Badge>
              <Badge>{result.scope}</Badge>
            </div>
            <pre className="json-view">{JSON.stringify(result, null, 2)}</pre>
          </>
        ) : (
          <EmptyState>等待评测</EmptyState>
        )}
      </section>
      <section className="result trusted-eval-panel">
        <div className="section-head">
          <h2>可信评测总览</h2>
          <button className="secondary" onClick={() => loadTrusted("summary")} disabled={trustedLoading}>
            {trustedLoading ? "读取中" : "刷新"}
          </button>
        </div>
        <ErrorBox message={trustedError} />
        {trusted?.available ? (
          <>
            <section className="metrics-grid trusted-metrics">
              <MetricCard label="总题数" value={trusted.total} tone="blue" />
              <MetricCard label="通过" value={trusted.passed} tone="green" />
              <MetricCard label="失败" value={trusted.failed} tone={trusted.failed ? "red" : "green"} />
              <MetricCard label="准确率" value={`${Math.round(Number(trusted.accuracy || 0) * 100)}%`} tone="green" />
            </section>
            <div className="trusted-report-list">
              {Object.entries(trusted.by_type || {}).map(([type, row]) => (
                <button key={type} className="trusted-row" onClick={() => loadTrusted(type)}>
                  <span>
                    <strong>{type}</strong>
                    <small>{row.report_path}</small>
                  </span>
                  <span className="trusted-score">
                    {row.passed}/{row.total}
                    <Badge tone={row.failed ? "red" : "green"}>{Math.round(Number(row.accuracy || 0) * 100)}%</Badge>
                  </span>
                </button>
              ))}
            </div>
            <div className="meta">
              <Badge>{trustedType}</Badge>
              <Badge>{trusted.report_path}</Badge>
            </div>
            <pre className="json-view">{JSON.stringify(trusted, null, 2)}</pre>
          </>
        ) : (
          <EmptyState>{trusted?.message || "等待可信评测报告"}</EmptyState>
        )}
      </section>
    </div>
  );
}

function EvidenceList({ items }) {
  if (!items.length) return <EmptyState />;
  return (
    <div className="evidence-list">
      {items.map((item, index) => (
        <EvidenceCard key={`${item.doc_id || "e"}-${index}`} item={item} />
      ))}
    </div>
  );
}
