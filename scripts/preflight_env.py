#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.preflight import PreflightError, run_preflight


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runtime env preflight checker")
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "ci", "real-provider", "prod"],
        help="Expected runtime mode",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to env file (default: .env)",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    env_file = Path(args.env_file)
    if not env_file.exists():
        print(f"❌ env 文件不存在：{env_file}")
        return 2

    try:
        ok, errors = run_preflight(expected_env=args.env, env_file=env_file)
    except PreflightError as exc:
        print(f"❌ preflight 失败：{exc}")
        return 1

    if not ok:
        print(f"❌ preflight 未通过（env={args.env}, env_file={env_file}）")
        for item in errors:
            print(f" - {item}")
        return 1

    print(f"✅ preflight 通过（env={args.env}, env_file={env_file}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
