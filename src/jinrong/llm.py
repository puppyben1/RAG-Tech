from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    api_key: str | None
    base_url: str
    model: str
    timeout_seconds: int


@dataclass(frozen=True)
class LLMResult:
    used: bool
    answer: str | None
    raw: str | None
    error: str | None = None


def load_llm_config() -> LLMConfig:
    api_key = os.getenv("JINRONG_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("JINRONG_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("JINRONG_LLM_MODEL", DEFAULT_MODEL)
    timeout = int(os.getenv("JINRONG_LLM_TIMEOUT", "30"))
    return LLMConfig(
        enabled=bool(api_key),
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
    )


def generate_grounded_answer(question: str, evidence: list[dict[str, Any]], config: LLMConfig | None = None) -> LLMResult:
    config = config or load_llm_config()
    if not config.enabled or not config.api_key:
        return LLMResult(used=False, answer=None, raw=None, error="LLM disabled: missing API key")

    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _user_prompt(question, evidence)},
    ]
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return LLMResult(used=True, answer=None, raw=body, error=f"HTTP {exc.code}: {body[:500]}")
    except Exception as exc:
        return LLMResult(used=True, answer=None, raw=None, error=str(exc))

    content = data["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return LLMResult(used=True, answer=None, raw=content, error="model returned non-JSON content")
    answer = str(parsed.get("answer", "")).strip()
    if not answer or parsed.get("can_answer") is False:
        return LLMResult(used=True, answer=None, raw=content, error="model refused or returned empty answer")
    return LLMResult(used=True, answer=answer, raw=content)


def _system_prompt() -> str:
    return (
        "你是金融监管可信问答系统的受控生成模块。"
        "你只能依据用户提供的证据回答，不能使用外部知识，不能编造数字、日期、文号、机构名称。"
        "如果证据不足，返回 can_answer=false。"
        "回答要简洁，必须保留关键事实和限制条件。"
        "输出必须是 JSON：{\"can_answer\": boolean, \"answer\": string}。"
    )


def _user_prompt(question: str, evidence: list[dict[str, Any]]) -> str:
    blocks = []
    for idx, item in enumerate(evidence, start=1):
        position = item.get("position") or {}
        source_bits = [
            f"doc_id={item.get('doc_id')}",
            f"title={item.get('source_title')}",
            f"type={item.get('source_type')}",
        ]
        if position:
            source_bits.append(f"position={json.dumps(position, ensure_ascii=False)}")
        text = str(item.get("text", ""))[:1800]
        blocks.append(f"[证据{idx}] {'; '.join(source_bits)}\n{text}")
    return f"问题：{question}\n\n证据：\n" + "\n\n".join(blocks)
