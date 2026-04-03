from __future__ import annotations

from pathlib import Path

from app.core.config import Settings

try:
    from dotenv import dotenv_values
except Exception:  # pragma: no cover - fallback path
    dotenv_values = None


class PreflightError(ValueError):
    """Raised when runtime environment preflight checks fail."""


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _parse_bool(raw: str | bool | None, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    value = str(raw).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _load_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if dotenv_values is not None:
        values = dotenv_values(env_path)
        return {k: str(v) for k, v in values.items() if v is not None}

    parsed: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def run_preflight(expected_env: str, env_file: str | Path = ".env") -> tuple[bool, list[str]]:
    """Run lightweight runtime env checks and return (ok, errors)."""

    normalized_env = expected_env.strip().lower()
    if normalized_env not in {"dev", "ci", "real-provider", "prod"}:
        raise PreflightError(f"不支持的 --env: {expected_env}")

    defaults = Settings(_env_file=None)
    env_data = _load_env_file(env_file)

    app_env = env_data.get("APP_ENV", defaults.app_env).strip().lower()
    provider = env_data.get("AGENT_PROVIDER", defaults.agent_provider).strip().lower()
    fallback = _parse_bool(env_data.get("AGENT_FALLBACK_TO_MOCK"), defaults.agent_fallback_to_mock)
    auto_create = _parse_bool(env_data.get("AUTO_CREATE_TABLES"), defaults.auto_create_tables)
    agent_model = env_data.get("AGENT_MODEL", defaults.agent_model)
    agent_api_base_url = env_data.get("AGENT_API_BASE_URL", defaults.agent_api_base_url)
    agent_api_key = env_data.get("AGENT_API_KEY", defaults.agent_api_key)

    errors: list[str] = []

    if app_env != normalized_env:
        errors.append(f"APP_ENV 不匹配：期望 `{normalized_env}`，实际 `{app_env}`。")

    if normalized_env == "ci" and auto_create:
        errors.append("ci 模式禁止 AUTO_CREATE_TABLES=true，请先执行 alembic upgrade head。")

    if normalized_env in {"real-provider", "prod"}:
        if provider == "mock":
            errors.append(f"{normalized_env} 模式禁止 AGENT_PROVIDER=mock。")
        if fallback:
            errors.append(f"{normalized_env} 模式禁止 AGENT_FALLBACK_TO_MOCK=true。")
        if auto_create:
            errors.append(
                f"{normalized_env} 模式禁止 AUTO_CREATE_TABLES=true，请先执行 alembic upgrade head。"
            )

        for field_name, value in {
            "AGENT_API_BASE_URL": agent_api_base_url,
            "AGENT_API_KEY": agent_api_key,
            "AGENT_MODEL": agent_model,
        }.items():
            if _is_blank(value):
                errors.append(f"{normalized_env} 模式缺少必填配置：{field_name}。")

    return (len(errors) == 0, errors)
