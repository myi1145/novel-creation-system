"""真实 provider 验收测试辅助：统一入口前置校验、skip 语义、诊断摘要。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from unittest import SkipTest

from app.core.config import settings


@dataclass
class RealProviderReadiness:
    ready: bool
    reasons: list[str]


def evaluate_real_provider_readiness() -> RealProviderReadiness:
    reasons: list[str] = []
    provider = (settings.agent_provider or "").strip().lower()
    if provider != "openai_compatible":
        reasons.append(f"AGENT_PROVIDER={settings.agent_provider!r}（期望 openai_compatible）")
    if bool(settings.agent_fallback_to_mock):
        reasons.append("AGENT_FALLBACK_TO_MOCK=True（真实 provider 验收要求关闭 fallback）")
    if not (settings.agent_api_base_url or "").strip():
        reasons.append("AGENT_API_BASE_URL 缺失")
    if not (settings.agent_api_key or "").strip():
        reasons.append("AGENT_API_KEY 缺失")
    if not (settings.agent_model or "").strip():
        reasons.append("AGENT_MODEL 缺失")
    return RealProviderReadiness(ready=not reasons, reasons=reasons)


def skip_unless_real_provider_ready(test_case: Any, suite_name: str) -> RealProviderReadiness:
    readiness = evaluate_real_provider_readiness()
    if not readiness.ready:
        test_case.skipTest(
            f"[{suite_name}] 跳过真实 provider 验收：环境前置未满足："
            + "; ".join(readiness.reasons)
        )
    return readiness


def raise_skip_unless_real_provider_ready(suite_name: str) -> RealProviderReadiness:
    readiness = evaluate_real_provider_readiness()
    if not readiness.ready:
        raise SkipTest(
            f"[{suite_name}] 跳过真实 provider 验收：环境前置未满足："
            + "; ".join(readiness.reasons)
        )
    return readiness


def preflight_gateway_or_skip(test_case: Any, client: TestClient, suite_name: str) -> dict[str, Any]:
    resp = client.get("/api/v1/workflows/agent-gateway/status")
    if resp.status_code != 200:
        test_case.skipTest(
            f"[{suite_name}] 跳过真实 provider 验收：gateway 状态接口不可用，status_code={resp.status_code}"
        )
    data = resp.json().get("data") or {}
    problems: list[str] = []
    if data.get("configured_provider") != "openai_compatible":
        problems.append(f"configured_provider={data.get('configured_provider')}")
    if data.get("active_provider") != "openai_compatible":
        problems.append(f"active_provider={data.get('active_provider')}")
    if bool(data.get("fallback_active")):
        problems.append(f"fallback_active={data.get('fallback_active')}")
    if not bool(data.get("available")):
        problems.append(f"available={data.get('available')}")
    if problems:
        test_case.skipTest(
            f"[{suite_name}] 跳过真实 provider 验收：gateway 预检未通过："
            + "; ".join(problems)
            + f"; gateway_status={data}"
        )
    return data


def format_recent_agent_calls(calls: list[dict[str, Any]], limit: int = 10) -> str:
    rows: list[str] = []
    for item in calls[:limit]:
        response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
        parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
        provider_error_details = response_summary.get("provider_error_details") if isinstance(response_summary, dict) else None
        rows.append(
            " ".join(
                [
                    f"step={item.get('action_name')}",
                    f"configured_provider={item.get('configured_provider')}",
                    f"active_provider={item.get('active_provider')}",
                    f"model={item.get('model_name')}",
                    f"status={item.get('call_status')}",
                    f"fallback_used={item.get('fallback_used')}",
                    f"error_type={item.get('error_type')}",
                    f"provider_error_details={provider_error_details}",
                    f"parse_report={parse_report}",
                ]
            )
        )
    return "\n".join(rows)
