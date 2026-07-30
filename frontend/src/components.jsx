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
        {position.sheet_name && <Badge>{position.sheet_name}</Badge>}
        {position.cell_ref && <Badge>{position.cell_ref}</Badge>}
        {position.row_index && <Badge>row {position.row_index}</Badge>}
        {item.unit && <Badge>{item.unit}</Badge>}
      </div>
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
