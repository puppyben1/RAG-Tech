import React from "react";
import { AlertCircle, CheckCircle2, FileText } from "lucide-react";
import { shortPath } from "./api.js";

export function Badge({ children, tone = "neutral" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function ErrorBox({ message }) {
  if (!message) return null;
  return (
    <div className="notice error">
      <AlertCircle size={16} />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ children = "暂无数据" }) {
  return <p className="muted empty">{children}</p>;
}

export function EvidenceCard({ item }) {
  const position = item.position || {};
  const sheetName = position.sheet_name || item.sheet_name;
  const cellRef = position.cell_ref || item.cell_ref;
  const rowHeader = position.row_header || item.row_header;
  const colHeader = position.col_header || item.col_header;
  return (
    <article className="evidence-card">
      <div className="evidence-head">
        <FileText size={16} />
        <strong>{item.source_title || item.file_name || "证据片段"}</strong>
      </div>
      <div className="meta">
        {item.evidence_type && <Badge>{item.evidence_type}</Badge>}
        {item.index && <Badge>{item.index}</Badge>}
        {item.score !== undefined && <Badge>score {item.score}</Badge>}
        {item.source_type && <Badge>{item.source_type}</Badge>}
        {item.source && <Badge>{shortPath(item.source)}</Badge>}
        {sheetName && <Badge>工作表 {sheetName}</Badge>}
        {cellRef && <Badge>单元格 {cellRef}</Badge>}
        {position.row_index && <Badge>row {position.row_index}</Badge>}
        {rowHeader && <Badge>行 {rowHeader}</Badge>}
        {colHeader && <Badge>列 {colHeader}</Badge>}
        {item.unit && <Badge>{item.unit}</Badge>}
      </div>
      <pre className="evidence-text">{item.text || JSON.stringify(item, null, 2)}</pre>
      <details className="evidence-details">
        <summary>查看完整定位字段</summary>
        <dl>
          <dt>文档 ID</dt><dd>{item.doc_id || "-"}</dd>
          <dt>发布机关</dt><dd>{item.publisher || "-"}</dd>
          <dt>文号</dt><dd>{item.doc_no || "-"}</dd>
          <dt>章节</dt><dd>{position.section_path || item.section_path || "-"}</dd>
          <dt>条款</dt><dd>{position.article_no || item.article_no || "-"}</dd>
          <dt>页码</dt><dd>{position.page_no || item.page_no || "-"}</dd>
          <dt>结构单元</dt><dd>{position.unit_id || item.unit_id || "-"}</dd>
          <dt>原始值</dt><dd>{item.value_raw ?? "-"}</dd>
          <dt>检索分数</dt><dd>{item.score ?? item.base_score ?? "-"}</dd>
        </dl>
      </details>
    </article>
  );
}

export function MetricCard({ label, value, tone = "neutral" }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong className={tone}>{value ?? "-"}</strong>
    </div>
  );
}

export function HealthBadge({ status }) {
  if (status === "ok") {
    return (
      <span className="health ok">
        <CheckCircle2 size={16} />
        API ok
      </span>
    );
  }
  return <span className="health">API {status}</span>;
}
