import React from "react";
import { AlertCircle, CheckCircle2, FileText, ExternalLink } from "lucide-react";
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
  const location = position.sheet_name && position.cell_ref
    ? `${position.sheet_name}!${position.cell_ref}`
    : [position.page_no && `page ${position.page_no}`, position.article_no && `article ${position.article_no}`, position.section_path].filter(Boolean).join(" / ");
  return (
    <article className="evidence-card">
      <div className="evidence-head">
        <FileText size={16} />
        <strong>{item.source_title || item.file_name || "证据"}</strong>
      </div>
      <div className="meta">
        {item.evidence_type && <Badge>{item.evidence_type}</Badge>}
        {item.index && <Badge>{item.index}</Badge>}
        {item.score !== undefined && <Badge>score {item.score}</Badge>}
        {item.source_type && <Badge>{item.source_type}</Badge>}
        {item.source && <Badge>{shortPath(item.source)}</Badge>}
        {item.version_status && <Badge tone={item.version_status === "current" ? "green" : item.version_status === "superseded" ? "red" : "neutral"}>version: {item.version_status}</Badge>}
        {location && <Badge>{location}</Badge>}
        {position.row_index && <Badge>row {position.row_index}</Badge>}
        {item.unit && <Badge>{item.unit}</Badge>}
      </div>
      {item.source_url && <a className="source-link" href={item.source_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> source link</a>}
      <pre className="evidence-text">{item.text || JSON.stringify(item, null, 2)}</pre>
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
