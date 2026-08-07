import React, { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, Database, FileSearch, Files, MessageSquareText, PlayCircle, Settings } from "lucide-react";
import { apiRequest, getInitialApiBase, saveApiBase } from "./api.js";
import { Badge, EmptyState, ErrorBox, EvidenceCard, HealthBadge, MetricCard } from "./components.jsx";

const navItems = [
  { key: "dashboard", label: "工作台", icon: Activity },
  { key: "ask", label: "问答", icon: MessageSquareText },
  { key: "search", label: "证据检索", icon: FileSearch },
  { key: "documents", label: "文档库", icon: Files },
  { key: "status", label: "知识库状态", icon: Database },
  { key: "eval", label: "评测中心", icon: BarChart3 },
  { key: "demo", label: "答辩演示", icon: PlayCircle },
];

const demoCases = [
  { id: "policy_fact", label: "制度事实", route: "rag_open", answer: "演示答案：制度事实由当前资料中的官方条款支持。", evidence: [{ source_title: "银行函证办理说明", source_url: "https://example.invalid/official/nfra_397", version_status: "current", position: { page_no: 3, article_no: "第三条" }, text: "证据原文：银行函证办理应按照制度要求执行。" }] },
  { id: "threshold", label: "条款阈值", route: "rag_open", answer: "演示答案：达到条款规定阈值后进入升级流程。", evidence: [{ source_title: "消费者权益保护规定", source_url: "https://example.invalid/official/nfra_390", version_status: "current", position: { page_no: 8, article_no: "第十二条" }, text: "证据原文：达到规定阈值时，应按本条启动升级处理。" }] },
  { id: "excel", label: "Excel 取数", route: "rag_open", answer: "演示答案：取数结果为 128.40。", evidence: [{ source_title: "经营情况统计表", source_url: "https://example.invalid/official/nfra_398", version_status: "current", position: { sheet_name: "月度统计", cell_ref: "H22" }, text: "证据原文：原保险保费收入 | 本年累计 | 128.40 | 亿元" }] },
  { id: "cross_file", label: "跨文件判断", route: "rag_open", answer: "演示答案：制度文件定义条件，统计表提供对应数值。", evidence: [{ source_title: "业务制度", source_url: "https://example.invalid/official/nfra_389", version_status: "current", position: { page_no: 5, article_no: "第二十条" }, text: "证据原文：业务判断条件与处理责任。" }, { source_title: "经营情况统计表", source_url: "https://example.invalid/official/nfra_398", version_status: "current", position: { sheet_name: "月度统计", cell_ref: "H22" }, text: "证据原文：对应统计数值。" }] },
  { id: "refusal", label: "资料不足/旧版冲突拒答", route: "rag_refusal", answer: "无法根据当前资料确定；发现资料不足或版本冲突。", evidence: [{ source_title: "旧版制度（仅作冲突提示）", source_url: "https://example.invalid/official/legacy", version_status: "superseded", position: { page_no: 2, article_no: "第一条" }, text: "证据原文：该版本已被替代，不进入权威回答。" }] },
];

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [apiBase, setApiBase] = useState(getInitialApiBase);
  const [health, setHealth] = useState("unknown");
  const current = useMemo(() => navItems.find((item) => item.key === tab), [tab]);

  useEffect(() => saveApiBase(apiBase), [apiBase]);
  async function checkHealth() {
    try { setHealth((await apiRequest(apiBase, "/health")).status === "ok" ? "ok" : "error"); } catch { setHealth("error"); }
  }

  return <div className="shell">
    <aside className="sidebar"><div className="brand">可信金融 RAG</div><nav className="nav">{navItems.map(({ key, label, icon: Icon }) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}><Icon size={18} /><span>{label}</span></button>)}</nav></aside>
    <main className="main"><header className="topbar"><h1>{current?.label}</h1><div className="api-base"><HealthBadge status={health} /><input value={apiBase} onChange={(e) => setApiBase(e.target.value)} aria-label="API Base" /><button className="icon-button" onClick={checkHealth} title="检查 API"><Settings size={18} /></button></div></header>
      {tab === "dashboard" && <DashboardPage setTab={setTab} apiBase={apiBase} />}
      {tab === "ask" && <AskPage apiBase={apiBase} />}
      {tab === "search" && <SearchPage apiBase={apiBase} />}
      {tab === "documents" && <DocumentsPage apiBase={apiBase} />}
      {tab === "status" && <StatusPage apiBase={apiBase} />}
      {tab === "eval" && <EvalPage apiBase={apiBase} />}
      {tab === "demo" && <DemoPage />}
    </main>
  </div>;
}

function DashboardPage({ setTab, apiBase }) {
  const [status, setStatus] = useState(null); const [error, setError] = useState("");
  useEffect(() => { setError(""); apiRequest(apiBase, "/kb/status").then(setStatus).catch((e) => setError(e.message)); }, [apiBase]);
  return <div className="stack"><ErrorBox message={error} /><section className="metrics-grid"><MetricCard label="文档" value={status?.documents} tone="blue" /><MetricCard label="文本单元" value={status?.text_units ?? status?.text_chunks} /><MetricCard label="表格单元" value={status?.table_cells} /><MetricCard label="表格行" value={status?.table_rows} /><MetricCard label="错误" value={status?.error_count} tone={status?.error_count ? "red" : "green"} /></section><section className="panel command-panel"><button className="primary" onClick={() => setTab("ask")}>进入问答</button><button className="secondary" onClick={() => setTab("search")}>检索证据</button><button className="secondary" onClick={() => setTab("demo")}>打开答辩演示</button></section></div>;
}

function AskPage({ apiBase }) {
  const [question, setQuestion] = useState(""); const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  async function submit() { setLoading(true); setError(""); try { setResult(await apiRequest(apiBase, "/ask", { question })); } catch (e) { setError(e.message); } finally { setLoading(false); } }
  return <div className="content-grid"><section className="panel"><h2>问题</h2><textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="输入制度、条款、统计或跨文件问题" /><div className="actions"><button className="primary" onClick={submit} disabled={loading || !question.trim()}>{loading ? "处理中" : "提交"}</button><button className="secondary" onClick={() => { setQuestion(""); setResult(null); }}>清空</button></div><ErrorBox message={error} /></section><section className="result"><h2>答案</h2>{result ? <><div className="answer">{String(result.answer_text ?? result.answer ?? "无答案")}</div><div className="meta"><Badge tone={result.route === "rag_refusal" ? "red" : "green"}>{result.route}</Badge><Badge>{result.confidence || "-"}</Badge></div><EvidenceList items={result.evidence || []} /></> : <EmptyState>等待提交</EmptyState>}</section></div>;
}

function SearchPage({ apiBase }) {
  const [query, setQuery] = useState(""); const [result, setResult] = useState(null); const [error, setError] = useState("");
  async function submit() { setError(""); try { setResult(await apiRequest(apiBase, "/search", { query, top_k: 5 })); } catch (e) { setError(e.message); } }
  return <div className="content-grid"><section className="panel"><h2>检索条件</h2><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="输入关键词" /><div className="actions"><button className="primary" onClick={submit} disabled={!query.trim()}>检索</button></div><ErrorBox message={error} /></section><section className="result"><h2>证据结果</h2>{result ? <><div className="status-line"><Badge>{result.index || "-"}</Badge><Badge>命中 {result.total ?? 0}</Badge></div><EvidenceList items={result.results || []} /></> : <EmptyState>等待检索</EmptyState>}</section></div>;
}

function DocumentsPage({ apiBase }) { const [result, setResult] = useState(null); const [error, setError] = useState("");
  async function load() { try { setResult(await apiRequest(apiBase, "/documents?limit=50")); } catch (e) { setError(e.message); } }
  useEffect(() => { load(); }, [apiBase]);
  return <div className="stack"><section className="panel"><div className="actions"><button className="primary" onClick={load}>刷新文档</button></div><ErrorBox message={error} /></section><section className="table-wrap"><table><thead><tr><th>doc_id</th><th>标题</th><th>类型</th><th>版本</th><th>文件</th></tr></thead><tbody>{(result?.documents || []).map((doc) => <tr key={doc.doc_id}><td>{doc.doc_id}</td><td>{doc.title}</td><td>{doc.source_type}</td><td>{doc.version_status || "unknown"}</td><td>{doc.file_name}</td></tr>)}</tbody></table></section></div>;
}

function StatusPage({ apiBase }) { const [status, setStatus] = useState(null); const [error, setError] = useState("");
  async function load() { try { setStatus(await apiRequest(apiBase, "/kb/status")); } catch (e) { setError(e.message); } }
  useEffect(() => { load(); }, [apiBase]);
  return <div className="stack"><ErrorBox message={error} /><section className="metrics-grid"><MetricCard label="文档" value={status?.documents} /><MetricCard label="已处理" value={status?.processed_documents} /><MetricCard label="文本单元" value={status?.text_units ?? status?.text_chunks} /><MetricCard label="表格单元" value={status?.table_cells} /><MetricCard label="表格行" value={status?.table_rows} /></section><section className="panel"><button className="secondary" onClick={load}>刷新</button>{status && <pre className="json-view">{JSON.stringify(status, null, 2)}</pre>}</section></div>;
}

function EvalPage({ apiBase }) { const [result, setResult] = useState(null); const [trusted, setTrusted] = useState(null); const [error, setError] = useState("");
  async function run() { try { setResult(await apiRequest(apiBase, "/eval", { scope: "all" })); } catch (e) { setError(e.message); } }
  async function loadTrusted() { try { setTrusted(await apiRequest(apiBase, "/eval/trusted/summary")); } catch (e) { setError(e.message); } }
  useEffect(() => { loadTrusted(); }, [apiBase]);
  return <div className="stack"><section className="panel"><div className="actions"><button className="primary" onClick={run}>运行基础评测</button><button className="secondary" onClick={loadTrusted}>刷新可信报告</button></div><ErrorBox message={error} /></section>{result && <section className="result"><h2>基础评测</h2><div className="answer">{result.correct ?? 0} / {result.total ?? 0}</div><pre className="json-view">{JSON.stringify(result, null, 2)}</pre></section>}{trusted && <section className="result"><h2>可信评测</h2><div className="meta"><Badge tone={trusted.stale ? "red" : "green"}>{trusted.stale ? "stale" : "current"}</Badge><Badge>{trusted.passed ?? 0} / {trusted.total ?? 0}</Badge></div><pre className="json-view">{JSON.stringify(trusted, null, 2)}</pre></section>}</div>;
}

function DemoPage() { const [selected, setSelected] = useState(demoCases[0]); return <div className="demo-layout"><section className="panel"><h2>五条固定演示链路</h2><div className="demo-list">{demoCases.map((item) => <button key={item.id} className={`demo-row ${selected.id === item.id ? "active" : ""}`} onClick={() => setSelected(item)}><span>{item.label}</span><Badge tone={item.route === "rag_refusal" ? "red" : "green"}>{item.route}</Badge></button>)}</div></section><section className="result"><h2>{selected.label}</h2><div className="answer">{selected.answer}</div><div className="meta"><Badge tone={selected.route === "rag_refusal" ? "red" : "green"}>{selected.route}</Badge><Badge>离线演示数据</Badge></div><EvidenceList items={selected.evidence} /></section></div>; }

function EvidenceList({ items }) { if (!items.length) return <EmptyState />; return <div className="evidence-list">{items.map((item, index) => <EvidenceCard key={`${item.doc_id || item.source_title || "e"}-${index}`} item={item} />)}</div>; }
