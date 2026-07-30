from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .services import search_evidence
from .trusted_qa import assess_evidence
from .utils import norm_text


@dataclass
class ComplianceAnswer:
    answer: dict[str, Any]
    answer_text: str
    evidence: list[dict[str, Any]]
    confidence: str
    route: str
    debug: str


def is_compliance_question(question: str) -> bool:
    markers = [
        "是否合规",
        "合规判断",
        "是否应当",
        "是否应该",
        "能否",
        "可否",
        "是否可以",
        "是否存在风险",
        "风险点",
        "改进建议",
        "给出判断",
        "给出合规判断",
        "不合规",
        "合规风险",
    ]
    q = norm_text(question)
    return any(norm_text(marker) in q for marker in markers)


def answer_compliance_question(question: str) -> ComplianceAnswer:
    search = _search_for_compliance(question)
    evidence = search.get("results", [])[:5]
    assessment = assess_evidence(question, evidence)
    if not assessment["sufficient"]:
        payload = _payload(
            judgement="无法判断",
            answer_text="无法根据当前资料形成合规判断；需要补充明确制度依据、最小充分证据或具体业务事实。",
            basis=[],
            risk_points=[],
            missing_facts=["缺少明确制度依据或适用条件", "缺少可核验的场景事实"],
            confidence="low",
        )
        return ComplianceAnswer(
            answer=payload,
            answer_text=payload["answer_text"],
            evidence=evidence[:3],
            confidence="low",
            route="compliance_judgement",
            debug=json.dumps({**assessment, **_debug_fields(payload), "search_index": search.get("index")}, ensure_ascii=False),
        )

    basis = [_basis_item(item) for item in evidence[:3]]
    judgement = _infer_judgement(question, evidence)
    risk_points = _risk_points(question, judgement)
    missing_facts = _missing_facts(question, judgement)
    confidence = "high" if assessment["level"] == "high" and basis else "medium"
    answer_text = _compose_answer_text(judgement, basis, risk_points, missing_facts)
    payload = _payload(
        judgement=judgement,
        answer_text=answer_text,
        basis=basis,
        risk_points=risk_points,
        missing_facts=missing_facts,
        confidence=confidence,
    )
    return ComplianceAnswer(
        answer=payload,
        answer_text=answer_text,
        evidence=evidence[:3],
        confidence=confidence,
        route="compliance_judgement",
        debug=json.dumps({**assessment, **_debug_fields(payload), "search_index": search.get("index")}, ensure_ascii=False),
    )


def _payload(
    judgement: str,
    answer_text: str,
    basis: list[dict[str, Any]],
    risk_points: list[str],
    missing_facts: list[str],
    confidence: str,
) -> dict[str, Any]:
    return {
        "judgement": judgement,
        "answer_text": answer_text,
        "basis": basis,
        "risk_points": risk_points,
        "missing_facts": missing_facts,
        "remediation": _remediation(risk_points, missing_facts),
        "missing_evidence": missing_facts,
        "confidence": confidence,
    }


def _search_for_compliance(question: str) -> dict[str, Any]:
    q = norm_text(question)
    if any(term in q for term in ["单位", "期间", "表格数值", "监管指标"]):
        return search_evidence(
            query=f"{question} 商业银行主要监管指标 资本充足率 单位 亿元 %",
            source_type="excel",
            top_k=8,
        )
    if any(term in q for term in ["旧版", "新版", "统计口径", "绿色信贷"]):
        return search_evidence(
            query=f"{question} 绿色信贷统计制度 统计口径 统计说明",
            source_type="pdf",
            top_k=8,
        )
    if any(term in q for term in ["来源URL", "来源", "证据位置", "文件标题", "可追溯"]):
        return search_evidence(
            query=f"{question} 银行函证 数据安全 投诉 证据 依据",
            top_k=8,
        )
    return search_evidence(query=question, top_k=8)


def _basis_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": item.get("doc_id"),
        "title": item.get("source_title"),
        "position": item.get("position") or {},
        "evidence_type": item.get("evidence_type"),
        "quote": _quote(item),
    }


def _quote(item: dict[str, Any]) -> str:
    text = str(item.get("text") or "").replace("\n", " ").strip()
    return text[:300]


def _infer_judgement(question: str, evidence: list[dict[str, Any]]) -> str:
    q = norm_text(question)
    evidence_text = norm_text(" ".join(str(item.get("text", "")) for item in evidence[:3]))
    negative_actions = [
        "不一致",
        "忽略",
        "不说明",
        "混用",
        "仅凭经验",
        "没有来源",
        "没有证据",
        "没有单位",
        "没有期间",
        "无法追溯",
    ]
    if any(norm_text(term) in q for term in negative_actions):
        return "存在风险"
    if any(norm_text(term) in q for term in ["是否应", "需要", "应当"]) and any(
        norm_text(term) in evidence_text for term in ["应当", "应", "需要", "风险", "投诉", "回函", "函证"]
    ):
        return "存在风险"
    if any(norm_text(term) in q for term in ["能否", "可否", "是否可以"]) and any(
        norm_text(term) in evidence_text for term in ["不得", "禁止", "应当", "要求"]
    ):
        return "存在风险"
    return "无法判断"


def _risk_points(question: str, judgement: str) -> list[str]:
    q = norm_text(question)
    risks: list[str] = []
    if "银行函证" in q or "回函" in q:
        risks.append("函证办理或回函信息不准确，可能影响审计证据可靠性和业务可追溯性。")
    if "投诉" in q or "社会群体性事件" in q or "数据安全" in q:
        risks.append("投诉、舆情或群体性事件可能放大数据安全和消费者权益保护风险。")
    if "统计" in q or "口径" in q or "单位" in q or "期间" in q:
        risks.append("统计口径、单位或期间维度缺失，可能导致指标解释和监管报送误用。")
    if "来源" in q or "证据" in q or "依据" in q:
        risks.append("缺少来源和证据位置会削弱答案可核验性，不满足可追溯要求。")
    if not risks and judgement != "无法判断":
        risks.append("需结合具体制度条款和业务事实复核适用范围。")
    return risks[:3]


def _missing_facts(question: str, judgement: str) -> list[str]:
    if judgement == "无法判断":
        return ["缺少明确可适用的监管条款", "缺少完整业务场景事实"]
    q = norm_text(question)
    missing: list[str] = []
    if "具体" not in q:
        missing.append("需补充具体业务发生时间、主体和操作过程。")
    if "文件" not in q and "条款" not in q:
        missing.append("需进一步核对是否存在更直接适用的专项制度条款。")
    return missing[:2]


def _compose_answer_text(
    judgement: str,
    basis: list[dict[str, Any]],
    risk_points: list[str],
    missing_facts: list[str],
) -> str:
    if judgement == "无法判断":
        return "无法根据当前资料形成合规判断；需要补充明确制度依据、最小充分证据或具体业务事实。"
    title = basis[0].get("title") if basis else "检索证据"
    risk_text = "；".join(risk_points) if risk_points else "需结合具体场景复核风险。"
    missing_text = "；".join(missing_facts) if missing_facts else "暂无明显缺失事实。"
    return f"初步判断为{judgement}。依据来自《{title}》等检索证据；主要风险点是：{risk_text} 仍需补充确认：{missing_text}"


def _debug_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "judgement": payload["judgement"],
        "basis": payload["basis"],
        "risk_points": payload["risk_points"],
        "missing_facts": payload["missing_facts"],
        "remediation": payload["remediation"],
        "missing_evidence": payload["missing_evidence"],
    }


def _remediation(risk_points: list[str], missing_facts: list[str]) -> list[str]:
    if not risk_points and not missing_facts:
        return []
    actions: list[str] = []
    if risk_points:
        actions.append("补充最小充分证据，并在答案中保留文件标题、位置和关键原文。")
    if missing_facts:
        actions.append("补充具体业务事实后再复核适用条款。")
    return actions
