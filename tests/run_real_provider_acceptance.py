"""真实 provider 验收统一入口（与默认 mock 回归分离）。"""

from __future__ import annotations

import argparse
import subprocess
import sys


SMOKE_TESTS = [
    "tests.test_real_provider_single_chapter_smoke",
]

ACCEPTANCE_TESTS = [
    "tests.test_real_provider_single_chapter_repeat_acceptance",
    "tests.test_real_provider_multi_chapter_continuity",
    "tests.test_real_provider_multi_chapter_revision_acceptance",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real provider smoke/acceptance tests.")
    parser.add_argument("--suite", choices=["smoke", "acceptance", "all"], default="all")
    args = parser.parse_args()

    modules: list[str] = []
    if args.suite in {"smoke", "all"}:
        modules.extend(SMOKE_TESTS)
    if args.suite in {"acceptance", "all"}:
        modules.extend(ACCEPTANCE_TESTS)

    cmd = [sys.executable, "-m", "unittest", *modules]
    print(f"[real-provider-entry] running: {' '.join(cmd)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
