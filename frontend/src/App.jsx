import React, { useEffect, useMemo, useState } from "react";
import {
  Activity, Archive, BarChart3, ChevronLeft, ChevronRight,
  BookOpen, Braces, Calculator, ClipboardList, Database, ExternalLink, FileCheck2, FileSearch, Files, Gauge, GitBranch, MessageSquareText, Network,
  PanelRight, Play, Plus, RefreshCw, Search, Send, Settings, Sparkles, Table2,
  ShieldCheck, Target, X,
} from "lucide-react";
import { apiRequest, getInitialApiBase, saveApiBase } from "./api.js";
import { Badge, EmptyState, ErrorBox, EvidenceCard, HealthBadge, MetricCard } from "./components.jsx";

const navItems = [
  { key: "dashboard", label: "工作台", icon: Activity },
  { key: "ask", label: "新对话", icon: MessageSquareText },
  { key: "documents", label: "文档中心", icon: Files },
  { key: "search", label: "证据检索", icon: FileSearch },
  { key: "eval", label: "评测中心", icon: BarChart3 },
  { key: "guide", label: "方案说明", icon: ClipboardList },
];

const sampleQuestion = "根据 Excel 附件《2023年10月人身险公司经营情况表》（工作表：人身保险公司（月度）），“原保险保费收入”在“本年累计/截至当期”口径下的数值是多少？";

const demoCases = [
  {
    id: "excel-lookup", label: "Excel 精确取数", ability: "结构化表格查询", icon: Table2,
    question: sampleQuestion,
    response: {
      answer_text: "31739.18 亿元", confidence: "high", route: "excel_lookup",
      evidence: [{ doc_id: "nfra_demo_excel", source_title: "2023年10月人身险公司经营情况表", source_type: "excel", sheet_name: "人身保险公司（月度）", cell_ref: "C5", row_header: "原保险保费收入", col_header: "本年累计/截至当期", unit: "单位：亿元", value_raw: 31739.18, text: "原保险保费收入在本年累计/截至当期口径下的原始值为 31739.18。" }],
    },
  },
  {
    id: "excel-calc", label: "Excel 比较计算", ability: "多单元格计算与校验", icon: Calculator,
    question: "比较2023年10月人身险公司经营情况表中的原保险保费收入与赔付支出，并给出差值和计算依据。",
    response: {
      answer_text: "原保险保费收入高于赔付支出，差值为 25310.62 亿元。计算：31739.18 - 6428.56 = 25310.62。", confidence: "high", route: "excel_calc",
      evidence: [
        { doc_id: "nfra_demo_excel", source_title: "2023年10月人身险公司经营情况表", source_type: "excel", sheet_name: "人身保险公司（月度）", cell_ref: "C5", row_header: "原保险保费收入", col_header: "本年累计/截至当期", unit: "单位：亿元", value_raw: 31739.18, text: "原保险保费收入：31739.18。" },
        { doc_id: "nfra_demo_excel", source_title: "2023年10月人身险公司经营情况表", source_type: "excel", sheet_name: "人身保险公司（月度）", cell_ref: "C8", row_header: "赔付支出", col_header: "本年累计/截至当期", unit: "单位：亿元", value_raw: 6428.56, text: "赔付支出：6428.56。" },
      ],
    },
  },
  {
    id: "policy-text", label: "制度条款检索", ability: "章节级文本证据", icon: BookOpen,
    question: "银行函证工作如何提高质量和效率？",
    response: {
      answer_text: "银行应通过规范函证业务流程、强化内部控制、推动数字化函证和明确各参与方职责，提高银行函证工作的质量与效率。", confidence: "high", route: "rag_open",
      evidence: [{ doc_id: "nfra_398", source_title: "银行函证工作操作指引", source_type: "pdf", publisher: "金融监管总局办公厅、财政部办公厅", doc_no: "财会〔2022〕39号", position: { page_no: 1, section_path: "一、总体要求", unit_id: "nfra_398_unit_0001" }, text: "规范银行函证及回函工作，提高银行函证工作质量和效率，防范操作风险。" }],
    },
  },
];

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [apiBase, setApiBase] = useState(getInitialApiBase);
  const [health, setHealth] = useState("unknown");
  const [collapsed, setCollapsed] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [selectedDemo, setSelectedDemo] = useState(null);
  const [documentCount, setDocumentCount] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const current = useMemo(() => navItems.find((item) => item.key === tab), [tab]);

  useEffect(() => { saveApiBase(apiBase); }, [apiBase]);
  useEffect(() => { checkHealth(); }, []);
  async function checkHealth() {
    try {
      const [healthData, statusData] = await Promise.all([apiRequest(apiBase, "/health"), apiRequest(apiBase, "/kb/status")]);
      setHealth(healthData.status === "ok" ? "ok" : "error");
      setDocumentCount(statusData.documents ?? null);
    } catch { setHealth("error"); setDocumentCount(null); }
  }
  function openDemo(demoCase) {
    setSelectedDemo(demoCase);
    setDemoMode(true);
    setTab("ask");
  }

  return (
    <div className={`shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand-row"><div className="brand-mark">R</div><span className="brand-name">RegRAG</span><button className="ghost icon-button sidebar-toggle" title="收起导航" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}</button></div>
        <div className="workspace-card"><div className="workspace-avatar">银</div><div><strong>银行监管助手</strong><small>TRUSTED WORKSPACE</small></div></div>
        <button className="new-chat" onClick={() => setTab("ask")}><Plus size={16} /><span>新建对话</span></button>
        <nav className="nav">{navItems.map((item) => { const Icon = item.icon; return <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)} title={item.label}><Icon size={17} /><span>{item.label}</span></button>; })}</nav>
        <div className="sidebar-bottom"><div className="workspace-label"><Database size={15} /><span>监管知识库</span><span className="workspace-count">{documentCount ?? "-"}</span></div><div className="user-row"><div className="avatar">R</div><div className="user-copy"><strong>竞赛演示环境</strong><small>公开监管资料</small></div></div></div>
      </aside>
      <main className="main">
        <header className="topbar"><div className="breadcrumbs"><span>监管知识库</span><ChevronRight size={14} /><strong>{current?.label}</strong></div><div className="top-actions"><div className="data-mode" role="group" aria-label="数据模式"><button className={!demoMode ? "active" : ""} onClick={() => setDemoMode(false)}>实时数据</button><button className={demoMode ? "active" : ""} onClick={() => setDemoMode(true)}>演示样例</button></div><HealthBadge status={health} /><div className="settings-wrap"><button className="ghost icon-button" onClick={() => setShowSettings(!showSettings)} title="服务设置" aria-expanded={showSettings}><Settings size={17} /></button>{showSettings && <div className="settings-popover"><label htmlFor="api-base">API 地址</label><input id="api-base" value={apiBase} onChange={(e) => setApiBase(e.target.value)} /><button className="secondary" onClick={checkHealth}><RefreshCw size={14} />重新连接</button></div>}</div></div></header>
        <div className="page-content">
          {demoMode && <div className="demo-banner"><Play size={14} /><strong>演示样例模式</strong><span>当前答案与证据为预置演示数据，不代表实时知识库结果。</span><button onClick={() => setDemoMode(false)}>切换到实时数据</button></div>}
          {tab === "dashboard" && <DashboardPage apiBase={apiBase} setTab={setTab} demoMode={demoMode} openDemo={openDemo} />}
          {tab === "ask" && <AskPage apiBase={apiBase} demoMode={demoMode} initialDemo={selectedDemo} openDemo={openDemo} />}
          {tab === "search" && <SearchPage apiBase={apiBase} />}
          {tab === "documents" && <DocumentsPage apiBase={apiBase} />}
          {tab === "eval" && <EvalPage apiBase={apiBase} />}
          {tab === "guide" && <ProductSpecPage setTab={setTab} documentCount={documentCount} />}
        </div>
      </main>
    </div>
  );
}

function DashboardPage({ apiBase, setTab, demoMode, openDemo }) {
  const [status, setStatus] = useState(null); const [trusted, setTrusted] = useState(null); const [error, setError] = useState("");
  useEffect(() => {
    if (demoMode) { setError(""); setStatus({ documents: 500, processed_documents: 500, text_units: 7132, table_cells: 83555, table_rows: 15775, error_count: 0 }); setTrusted(null); return; }
    Promise.allSettled([apiRequest(apiBase, "/kb/status"), apiRequest(apiBase, "/eval/trusted/summary")]).then(([statusResult, trustedResult]) => {
      if (statusResult.status === "fulfilled") setStatus(statusResult.value); else setError("知识库状态暂时无法读取，请检查后端服务。");
      if (trustedResult.status === "fulfilled" && trustedResult.value?.available) setTrusted(trustedResult.value);
    });
  }, [apiBase, demoMode]);
  const cases = demoCases;
  return <div className="stack">
    <div className="demo-hero"><div><p className="eyebrow">DEMO WORKSPACE</p><h1>用证据回答监管问题</h1><p>从 Excel 精确取数，到制度条款检索，每个答案都能回到原始资料。</p></div><div className="hero-actions"><button className="primary" onClick={() => openDemo(cases[0])}><Play size={15} />开始演示</button><button className="secondary" onClick={() => setTab("ask")}><MessageSquareText size={15} />进入完整问答</button></div></div>
    <ErrorBox message={error} />
    <div className="spec-strip"><span><strong>3</strong> 类演示题</span><span><strong>{status?.documents ?? "-"}</strong> 份资料</span><span><strong>{trusted?.current ? `${trusted.passed ?? trusted.correct ?? "-"}/${trusted.total ?? "-"}` : "待验收"}</strong> 当前评测</span><span className="strip-note">实时数据优先，演示样例仅在主动切换后使用</span></div>
    <section><div className="section-title"><div><p className="eyebrow">DEMO ROUTES</p><h2>选择一条演示路径</h2></div><span className="muted">点击题目后可查看完整检索过程</span></div><div className="demo-case-grid">{cases.map((demoCase, index) => { const Icon = demoCase.icon; return <button className="demo-case" key={demoCase.id} onClick={() => openDemo(demoCase)}><div className="demo-case-top"><span className={`case-number case-${index + 1}`}>0{index + 1}</span><Icon size={18} /></div><strong>{demoCase.label}</strong><p>{demoCase.ability}</p><span className="case-question">{demoCase.question}</span><span className="case-cta">填入问题 <ChevronRight size={14} /></span></button>; })}</div></section>
    <section className="dashboard-grid"><div className="panel status-panel"><div className="section-head"><div><p className="eyebrow">KNOWLEDGE BASE</p><h2>知识库状态</h2></div><span className="status-dot"><i />{demoMode ? "演示数据" : "实时状态"}</span></div><div className="metrics-grid mini-metrics"><MetricCard label="已入库文档" value={status?.documents} tone="blue" /><MetricCard label="文本单元" value={status?.text_units || status?.text_chunks} /><MetricCard label="表格事实" value={status?.table_cells} /></div><div className="progress-row"><span>文档处理</span><strong>{status?.processed_documents ?? "-"} / {status?.documents ?? "-"}</strong></div><div className="progress-track"><i style={{ width: `${status?.documents ? Math.round((status.processed_documents || 0) / status.documents * 100) : 0}%` }} /></div></div><div className="panel status-panel"><div className="section-head"><div><p className="eyebrow">EVALUATION</p><h2>可信评测摘要</h2></div><button className="text-button" onClick={() => setTab("eval")}>查看详情</button></div>{trusted?.current ? <div className="eval-summary"><strong>{Math.round(Number(trusted.accuracy || 0) * 100)}%</strong><span>当前准确率</span><div><b>{trusted.passed ?? trusted.correct ?? "-"}</b><small>通过题数</small></div><div><b>{trusted.total ?? "-"}</b><small>总题数</small></div></div> : trusted?.available ? <div className="stale-eval"><ShieldCheck size={20} /><div><strong>待独立验收</strong><span>历史诊断结果 {trusted.passed ?? trusted.correct ?? "-"}/{trusted.total ?? "-"} 已过期，不作为当前成绩。</span></div></div> : <EmptyState>尚无可用的当前验收结果</EmptyState>}</div></section>
  </div>;
}

function AskPage({ apiBase, demoMode, initialDemo, openDemo }) {
  const [mode, setMode] = useState("question"); const [qaId, setQaId] = useState("Q001"); const [question, setQuestion] = useState(""); const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [showEvidence, setShowEvidence] = useState(true); const [steps, setSteps] = useState([]); const [copied, setCopied] = useState(false);
  useEffect(() => { if (initialDemo) { setQuestion(initialDemo.question); setResult(null); setError(""); } }, [initialDemo]);
  async function submit() { if (mode === "question" && !question.trim()) { setError("请输入问题后再发送。"); return; } if (mode === "qa" && !/^Q\d{3}$/i.test(qaId.trim())) { setError("QA 编号格式应为 Q001。"); return; } setLoading(true); setError(""); setResult(null); setCopied(false); setSteps(["识别问题类型", "检索知识库证据"]); try { if (demoMode && initialDemo) { await new Promise((resolve) => setTimeout(resolve, 520)); setSteps(["识别问题类型", "检索知识库证据", "完成数字一致性校验"]); setResult({ ...initialDemo.response, demo: true }); return; } const payload = mode === "qa" ? { qa_id: qaId.trim().toUpperCase() } : { question }; const data = await apiRequest(apiBase, "/ask", payload); setSteps(["识别问题类型", "检索知识库证据", "完成可信性校验"]); setResult(data); } catch (e) { setError(e.message); setSteps([]); } finally { setLoading(false); } }
  async function copyAnswer() { await navigator.clipboard?.writeText(String(result?.answer_text || result?.answer || "")); setCopied(true); }
  const refusalLabel = refusalReasonLabel(result?.refusal_reason);
  return <div className="ask-layout"><section className="chat-column"><div className="chat-title"><div><p className="eyebrow">可信问答 {demoMode && <span className="inline-demo-tag">演示样例</span>}</p><h1>{initialDemo ? initialDemo.label : "今天想了解什么？"}</h1></div></div><div className="conversation">{!result && !loading ? <div className="welcome"><div className="welcome-icon"><Sparkles size={20} /></div><h2>{initialDemo ? "问题已准备好，点击发送查看证据" : "从监管资料中找到可靠答案"}</h2><p>支持制度条款检索、Excel 取数、比较计算和多事实问答。</p><div className="suggestions">{demoCases.map((demoCase) => <button key={demoCase.id} onClick={() => openDemo(demoCase)}>{demoCase.label} <ChevronRight size={14} /></button>)}</div></div> : <><div className="question-bubble">{mode === "qa" ? `QA 编号：${qaId}` : question}</div>{loading && <div className="agent-trace">{steps.map((s, i) => <div className="trace-row" key={s}><span className="trace-icon">{i === steps.length - 1 ? <Activity size={14} /> : <span className="check">✓</span>}</span><span>{s}</span>{i === steps.length - 1 && <small>处理中</small>}</div>)}</div>}{result && <div className="answer-block"><div className="answer-meta"><span className={`status-dot ${result.refusal_reason ? "refused" : ""}`}><i />{result.refusal_reason ? "已拒答" : result.demo ? "演示结果" : "已完成"}</span><span>引用 {result.evidence?.length || 0} 份证据</span><span>·</span><span>{result.route || "可信问答"}</span></div>{refusalLabel && <div className="refusal-notice"><ShieldCheck size={16} /><div><strong>{refusalLabel.title}</strong><span>{refusalLabel.description}</span></div></div>}<div className="answer-text">{String(result.answer_text ?? result.answer ?? "无法根据当前资料确定。")}</div><div className="answer-actions"><button className="ghost" onClick={copyAnswer}>{copied ? "已复制" : "复制答案"}</button><button className="ghost" onClick={() => setShowEvidence(!showEvidence)}><PanelRight size={14} />{showEvidence ? "收起证据" : "查看证据"}</button></div></div>}</>}</div><div className="composer">{mode === "qa" ? <input className="qa-id-input" value={qaId} onChange={(e) => setQaId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="Q001" aria-label="QA 编号" /> : <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} placeholder="直接向模型提问" />}<div className="composer-footer"><div className="composer-tools"><span className="composer-hint">{mode === "qa" ? "输入 Q001 至 Q300" : "Enter 发送，Shift+Enter 换行"}</span></div><div className="composer-actions"><select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="问答模式"><option value="question">自定义问题</option><option value="qa">按 QA 编号</option></select><button className="send-button" onClick={submit} disabled={loading} title="发送"><Send size={16} /></button></div></div></div><ErrorBox message={error} /></section>{showEvidence && <aside className="evidence-drawer"><div className="drawer-head"><div><p className="eyebrow">SOURCE TRACE</p><h2>证据与引用 {result?.demo && <span className="inline-demo-tag">演示数据</span>}</h2></div><button className="ghost icon-button" onClick={() => setShowEvidence(false)} title="关闭"><X size={16} /></button></div>{result ? <><div className="confidence-row"><span>回答可信度</span><Badge tone={result.confidence === "high" ? "green" : "neutral"}>{result.confidence || "待评估"}</Badge></div><div className="evidence-list"><EvidenceList items={result.evidence || []} /></div></> : <EmptyState>提交问题后显示来源片段、页码和单元格定位。</EmptyState>}</aside>}</div>;
}

function refusalReasonLabel(reason) {
  return {
    out_of_scope_or_sensitive: { title: "问题超出资料范围或涉及敏感内容", description: "系统在检索前执行了安全拒答。" },
    non_authoritative_evidence: { title: "检索结果尚未通过来源与版本认证", description: "可查看候选证据，但系统不会将其作为权威监管结论。" },
    no_evidence: { title: "知识库未检索到相关证据", description: "请调整问题表述或补充文件名称、期间和指标。" },
    insufficient_evidence: { title: "现有证据不足以支持结论", description: "系统保留检索结果，但不补全缺失事实。" },
  }[reason] || null;
}

function SearchPage({ apiBase }) { const [query, setQuery] = useState("银行函证 工作质量 效率"); const [sourceType, setSourceType] = useState(""); const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(""); async function submit() { if (!query.trim()) { setError("请输入检索词。"); return; } const startedAt = performance.now(); setLoading(true); setError(""); try { const data = await apiRequest(apiBase, "/search", { query: query.trim(), source_type: sourceType || null, retrieval: "hybrid", rerank: true, top_k: 8 }); setResult({ ...data, elapsed_ms: Math.round(performance.now() - startedAt) }); } catch (e) { setError(e.message); } finally { setLoading(false); } } return <div className="search-page"><div className="page-intro compact"><div><p className="eyebrow">RETRIEVAL LAB</p><h1>证据检索</h1><p className="muted">用关键词和元数据定位可核验的最小证据。</p></div><button className="secondary" onClick={submit} disabled={loading}><Search size={15} />{loading ? "检索中" : "开始检索"}</button></div><section className="filter-bar"><div className="search-input"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="搜索证据、条款、指标..." /></div><select value={sourceType} onChange={(e) => setSourceType(e.target.value)}><option value="">全部类型</option><option value="excel">Excel</option><option value="word">Word</option><option value="pdf">PDF</option></select><span className="filter-chip">Hybrid + Rerank</span></section><ErrorBox message={error} />{result && <div className="result-summary"><strong>{result.total} 个结果</strong><span>耗时：{result.elapsed_ms} ms</span><span>索引：{result.index}</span><span>展示前 {result.results?.length || 0} 条</span></div>}<EvidenceList items={result?.results || []} /></div>; }

function DocumentsPage({ apiBase }) { const [sourceType, setSourceType] = useState(""); const [query, setQuery] = useState(""); const [result, setResult] = useState(null); const [selected, setSelected] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(""); async function load(nextSourceType = sourceType) { setLoading(true); setError(""); try { const params = new URLSearchParams({ limit: "50" }); if (nextSourceType) params.set("source_type", nextSourceType); if (query) params.set("query", query); setResult(await apiRequest(apiBase, `/documents?${params}`)); } catch (e) { setError(e.message); } finally { setLoading(false); } } useEffect(() => { load(); }, [apiBase]); return <div className="documents-page"><div className="page-intro compact"><div><p className="eyebrow">KNOWLEDGE BASE</p><h1>文档中心</h1><p className="muted">浏览监管制度、政策文件与统计报表。</p></div><button className="primary" onClick={() => load()} disabled={loading}><RefreshCw size={15} />{loading ? "刷新中" : "刷新文档"}</button></div><div className="document-workspace simple"><aside className="folder-tree panel"><div className="section-head"><h2>范围</h2></div><div className="folder static"><Archive size={15} />当前结果 <small>{result?.total ?? "-"}</small></div></aside><section className="document-list"><div className="doc-toolbar"><div className="search-input"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} placeholder="搜索文档名称..." /></div><select value={sourceType} onChange={(e) => { const value = e.target.value; setSourceType(value); load(value); }}><option value="">全部类型</option><option value="excel">Excel</option><option value="word">Word</option><option value="pdf">PDF</option></select></div><ErrorBox message={error} />{loading && !result ? <EmptyState>正在加载文档...</EmptyState> : <div className="doc-grid">{(result?.documents || []).map((doc) => <button className={`doc-card ${selected?.doc_id === doc.doc_id ? "selected" : ""}`} key={doc.doc_id} onClick={() => setSelected(doc)}><div className="doc-card-head"><span className={`file-type ${doc.source_type}`}>{doc.source_type === "excel" ? "XLS" : doc.source_type === "pdf" ? "PDF" : "DOC"}</span><Badge tone={doc.version_status === "current" ? "green" : "neutral"}>{doc.version_status || "unknown"}</Badge></div><strong>{doc.title}</strong><p>{doc.file_name}</p><div className="doc-card-foot"><span>{doc.period || "未标注期间"}</span><span>{doc.file_ext || doc.source_type}</span></div></button>)}</div>}{!loading && !result?.documents?.length && <EmptyState>暂无匹配文档</EmptyState>}</section>{selected && <aside className="document-detail panel"><div className="drawer-head"><div><p className="eyebrow">DOCUMENT DETAIL</p><h2>{selected.title}</h2></div><button className="ghost icon-button" onClick={() => setSelected(null)} title="关闭"><X size={16} /></button></div><div className="detail-meta"><Badge>{selected.source_type}</Badge><Badge tone={selected.version_status === "current" ? "green" : "neutral"}>{selected.version_status || "版本未知"}</Badge></div><dl><dt>文档编号</dt><dd>{selected.doc_id}</dd><dt>文件名</dt><dd>{selected.file_name}</dd><dt>发布机关</dt><dd>{selected.publisher || "-"}</dd><dt>文号</dt><dd>{selected.doc_no || "-"}</dd><dt>路径</dt><dd>{selected.local_path || "-"}</dd><dt>官方来源</dt><dd>{selected.source_url ? <a href={selected.source_url} target="_blank" rel="noreferrer">打开来源 <ExternalLink size={12} /></a> : "尚未认证"}</dd></dl></aside>}</div></div>; }

function EvalPage({ apiBase }) { const [scope, setScope] = useState("all"); const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(""); async function run() { setLoading(true); setError(""); try { setResult(await apiRequest(apiBase, "/eval", { scope })); } catch (e) { setError(e.message); } finally { setLoading(false); } } return <div className="eval-page"><div className="page-intro compact"><div><p className="eyebrow">QUALITY CONTROL</p><h1>评测中心</h1><p className="muted">验证回答准确率、证据命中和运行环境一致性。</p></div><button className="primary" onClick={run} disabled={loading}><BarChart3 size={15} />{loading ? "评测中" : "运行评测"}</button></div><section className="panel eval-controls"><label>评测范围</label><select value={scope} onChange={(e) => setScope(e.target.value)}><option value="all">全部题目</option><option value="excel">Excel</option><option value="text">Word / PDF</option></select><ErrorBox message={error} /></section>{result ? <section className="metrics-grid eval-metrics"><MetricCard label="总题数" value={result.total} tone="blue" /><MetricCard label="通过" value={result.correct} tone="green" /><MetricCard label="失败" value={(result.total || 0) - (result.correct || 0)} tone="red" /><MetricCard label="准确率" value={`${Math.round(Number(result.accuracy || 0) * 100)}%`} tone="green" /></section> : <section className="panel eval-empty"><BarChart3 size={28} /><h2>还没有本次评测结果</h2><p className="muted">选择范围并运行评测，查看失败样本和指标变化。</p></section>}</div>; }

function ProductSpecPage({ setTab, documentCount }) {
  const targets = [
    ["制度事实准确率", "≥ 85%"],
    ["表格取数准确率", "≥ 80%"],
    ["证据引用命中率", "≥ 90%"],
    ["关键事实错误率", "≤ 5%"],
    ["依据不足拒答率", "≥ 80%"],
  ];
  const pipeline = [
    { icon: Files, title: "多源资料接入", text: "Word、PDF、Excel 与官方网页附件，统一记录来源、哈希和版本。" },
    { icon: Layers3, title: "结构化解析", text: "保留标题层级、条款编号、表头、单位、期间和单元格定位。" },
    { icon: GitBranch, title: "混合检索", text: "关键词、向量、元数据和表格结构联合召回，并执行版本过滤与重排。" },
    { icon: ShieldCheck, title: "受控生成", text: "依据最小充分证据生成；无权威证据时拒答，不让模型自由补全。" },
    { icon: FileCheck2, title: "引用与评测", text: "答案返回文件、页码、条款或单元格，并持续评测准确率与新鲜度。" },
  ];
  return <div className="spec-page">
    <section className="spec-cover panel">
      <div><p className="eyebrow">PRODUCT SPECIFICATION · V1.0</p><h1>银行业监管可信 RAG 问答系统</h1><p>面向制度查询、流程核对、统计取数和合规判断，建设“问得准、找得到、答得清、可追溯、可复现”的监管知识工作台。</p></div>
      <div className="cover-actions"><button className="primary" onClick={() => setTab("ask")}><MessageSquareText size={15} />体验可信问答</button><button className="secondary" onClick={() => setTab("documents")}><Database size={15} />查看知识库</button></div>
    </section>
    <div className="section-title"><div><p className="eyebrow">COMPETITION TARGETS</p><h2>比赛目标阈值</h2></div><span className="muted">非当前实测结果，最终成绩以独立 holdout 验收为准</span></div>
    <section className="spec-kpi-grid">{targets.map(([label, value]) => <div className="spec-kpi" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>
    <section className="spec-grid two-column"><article className="panel"><div className="section-head"><div><p className="eyebrow">WHY NOW</p><h2>业务问题</h2></div><Target size={19} /></div><ul className="spec-list"><li>监管资料分散在多个官方渠道，格式和版本不统一。</li><li>人工检索易漏查、误用旧规，条款和指标定位不稳定。</li><li>制度正文与统计表格需要跨文件、跨模态联合推理。</li><li>关键数字、日期、机构和文号必须精确且可核验。</li></ul></article><article className="panel"><div className="section-head"><div><p className="eyebrow">DELIVERABLES</p><h2>交付成果</h2></div><Braces size={19} /></div><ul className="spec-list"><li>可运行的 RAG Web 系统与 API 服务。</li><li>含来源、版本和位置元数据的结构化知识库。</li><li>Word / PDF / Excel 解析与可复现构建脚本。</li><li>检索、生成、拒答和独立 holdout 评测报告。</li></ul></article></section>
    <section><div className="section-title"><div><p className="eyebrow">SYSTEM FLOW</p><h2>可信问答链路</h2></div><span className="muted">每一步都保留可审计输入与输出</span></div><div className="pipeline-grid">{pipeline.map(({ icon: Icon, title, text }, index) => <article className="pipeline-card" key={title}><div className="pipeline-index">0{index + 1}</div><Icon size={19} /><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <section className="spec-grid two-column"><article className="panel"><div className="section-head"><div><p className="eyebrow">QUESTION TYPES</p><h2>覆盖问题类型</h2></div><Network size={19} /></div><div className="tag-cloud">{["监管事实", "条款阈值", "业务流程", "保存期限", "禁止性规定", "Excel 取数", "指标口径", "跨文件判断", "合规场景", "依据不足拒答"].map((tag) => <Badge key={tag}>{tag}</Badge>)}</div></article><article className="panel"><div className="section-head"><div><p className="eyebrow">DATASET</p><h2>当前数据基础</h2></div><Database size={19} /></div><div className="dataset-stats"><div><strong>{documentCount ?? "-"}</strong><span>当前入库文档</span></div><div><strong>300</strong><span>Legacy MCQ 回归题</span></div></div><p className="muted dataset-note">来源与版本治理、独立 holdout 复核仍按验收门禁推进。</p></article></section>
    <section className="panel acceptance-panel"><div><p className="eyebrow">ACCEPTANCE</p><h2>验收原则</h2><p className="muted">权威来源优先、旧版默认排除、证据不足明确拒答；任何成功指标都必须来自当前代码、当前数据和独立评测集。</p></div><div className="acceptance-badges"><span><ShieldCheck size={15} />可溯源</span><span><Gauge size={15} />可量化</span><span><GitBranch size={15} />可复现</span></div></section>
  </div>;
}

function EvidenceList({ items }) { if (!items.length) return <EmptyState>暂无证据</EmptyState>; return <div className="evidence-list">{items.map((item, index) => <EvidenceCard key={`${item.doc_id || "e"}-${index}`} item={item} />)}</div>; }
