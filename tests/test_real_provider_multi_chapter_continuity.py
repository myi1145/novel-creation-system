"""阶段三：真实 provider 同项目 1~3 章连续章节验收。"""

import json
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.real_provider_test_helper import format_recent_agent_calls, preflight_gateway_or_skip, raise_skip_unless_real_provider_ready


class RealProviderMultiChapterContinuityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        raise_skip_unless_real_provider_ready(suite_name="real-provider-multi-chapter-continuity")
        run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        cls.export_dir = Path("output") / "real_provider_multi_chapter" / f"{run_tag}_{uuid4().hex[:8]}"
        cls.export_dir.mkdir(parents=True, exist_ok=True)
        cls.exported_files: list[str] = []
        cls.export_warnings: list[str] = []

    def _create_project(self) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"real-provider-multi-chapter-{uuid4().hex[:8]}",
                "premise": "阶段三真实 provider 连续章节 1-2-3 验收",
                "genre_id": "default",
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _init_canon_snapshot(self, project_id: str) -> str:
        resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "real-provider-multi-chapter-initial-snapshot",
                "initial_rules": [{"rule_name": "世界规则", "description": "基础规则", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _gateway_preflight(self) -> dict[str, Any]:
        return preflight_gateway_or_skip(self, self.client, suite_name="real-provider-multi-chapter-continuity")

    def _list_agent_calls(self, project_id: str, limit: int = 200) -> list[dict[str, Any]]:
        resp = self.client.get("/api/v1/workflows/agent-calls", params={"project_id": project_id, "limit": limit})
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def _diagnostic_recent_calls(self, calls: list[dict[str, Any]], limit: int = 10) -> str:
        return format_recent_agent_calls(calls, limit=limit)

    def _extract_text_payload(self, data: dict[str, Any] | None) -> str:
        if not isinstance(data, dict):
            return str(data or "")
        for key in ("content", "body", "chapter_content", "draft_content", "text", "manuscript", "rendered_content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _export_chapter_text(
        self,
        *,
        chapter_no: int,
        source_type: str,
        body_text: str,
        project_id: str,
        published_chapter_id: str | None = None,
        next_chapter_seed: str | None = None,
        state_summary: str | None = None,
    ) -> None:
        filename = f"chapter_{chapter_no}_{source_type}.md"
        file_path = self.export_dir / filename
        header = [
            f"# Chapter {chapter_no} - {source_type}",
            "",
            f"- project_id: {project_id}",
            f"- chapter_no: {chapter_no}",
            f"- source_type: {source_type}",
            f"- published_chapter_id: {published_chapter_id or ''}",
            f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        ]
        if source_type == "summary":
            header.append(f"- next_chapter_seed: {next_chapter_seed or ''}")
        if state_summary:
            header.append(f"- state_summary: {state_summary}")
        content = "\n".join(header) + "\n\n---\n\n" + (body_text or "(empty)")
        try:
            file_path.write_text(content, encoding="utf-8")
            self.exported_files.append(str(file_path))
        except Exception as exc:  # noqa: BLE001
            self.export_warnings.append(f"{filename} 导出失败: {type(exc).__name__}: {exc}")

    def _timed_post(self, url: str, payload: dict[str, Any] | None) -> tuple[Any, int]:
        start = time.perf_counter()
        if payload is None:
            resp = self.client.post(url)
        else:
            resp = self.client.post(url, json=payload)
        return resp, int((time.perf_counter() - start) * 1000)

    def _run_single_chapter(
        self,
        *,
        project_id: str,
        chapter_no: int,
        current_volume_goal: str,
        previous_summary: str | None,
        previous_next_seed: str | None,
        previous_published_id: str | None,
        expected_published_count_before: int,
    ) -> dict[str, Any]:
        gateway_status = self._gateway_preflight()
        calls_before = self._list_agent_calls(project_id=project_id)
        call_ids_before = {item.get("id") for item in calls_before}

        chapter_result: dict[str, Any] = {
            "chapter_no": chapter_no,
            "project_id": project_id,
            "gateway_status": gateway_status,
            "published_chapter_id": None,
            "summary": None,
            "next_chapter_seed": None,
            "derived": None,
            "durations": {
                "total_duration_ms": 0,
                "generate_blueprints_duration_ms": 0,
                "decompose_scenes_duration_ms": 0,
                "generate_draft_duration_ms": 0,
                "review_gate_duration_ms": 0,
                "summary_duration_ms": 0,
            },
            "agent_call_count": 0,
            "parse_report_count": 0,
            "degraded_count": 0,
            "fallback_count": 0,
            "new_agent_calls": [],
            "published_count_before": expected_published_count_before,
            "published_count_after": None,
            "previous_published_id": previous_published_id,
            "previous_next_seed": previous_next_seed,
            "success": False,
            "error": None,
        }

        start_total = time.perf_counter()
        try:
            if chapter_no > 1:
                self.assertIsNotNone(previous_published_id, msg=f"第{chapter_no}章执行前，上一章未发布。")

            goal_text = current_volume_goal
            if previous_next_seed:
                goal_text = f"{current_volume_goal}；承接上一章种子：{previous_next_seed}"

            goal_resp, _ = self._timed_post(
                "/api/v1/chapters/goals",
                {
                    "project_id": project_id,
                    "chapter_no": chapter_no,
                    "current_volume_goal": goal_text,
                    "previous_chapter_summary": previous_summary,
                },
            )
            self.assertEqual(goal_resp.status_code, 200, msg=f"第{chapter_no}章 create_goal 失败: {goal_resp.text}")
            goal = goal_resp.json()["data"]
            self.assertEqual(goal.get("chapter_no"), chapter_no)

            blueprints_resp, blueprints_ms = self._timed_post(
                "/api/v1/chapters/blueprints/generate",
                {"project_id": project_id, "chapter_goal_id": goal["id"], "candidate_count": 3},
            )
            chapter_result["durations"]["generate_blueprints_duration_ms"] = blueprints_ms
            self.assertEqual(blueprints_resp.status_code, 200, msg=f"第{chapter_no}章 generate_blueprints 失败: {blueprints_resp.text}")
            blueprints = blueprints_resp.json()["data"]
            self.assertGreaterEqual(len(blueprints), 1)

            selected_resp, _ = self._timed_post(
                "/api/v1/chapters/blueprints/select",
                {"project_id": project_id, "blueprint_id": blueprints[0]["id"], "selected_by": "stage3-multi-chapter"},
            )
            self.assertEqual(selected_resp.status_code, 200, msg=f"第{chapter_no}章 select_blueprint 失败: {selected_resp.text}")
            selected_blueprint = selected_resp.json()["data"]

            scenes_resp, scenes_ms = self._timed_post(
                "/api/v1/chapters/scenes/decompose",
                {"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            chapter_result["durations"]["decompose_scenes_duration_ms"] = scenes_ms
            self.assertEqual(scenes_resp.status_code, 200, msg=f"第{chapter_no}章 decompose_scenes 失败: {scenes_resp.text}")
            self.assertGreaterEqual(len(scenes_resp.json()["data"]), 1)

            draft_resp, draft_ms = self._timed_post(
                "/api/v1/chapters/drafts/generate",
                {"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            chapter_result["durations"]["generate_draft_duration_ms"] = draft_ms
            self.assertEqual(draft_resp.status_code, 200, msg=f"第{chapter_no}章 generate_draft 失败: {draft_resp.text}")
            draft = draft_resp.json()["data"]
            self._export_chapter_text(
                chapter_no=chapter_no,
                source_type="draft",
                body_text=self._extract_text_payload(draft),
                project_id=project_id,
            )

            gate_resp, gate_ms = self._timed_post(
                "/api/v1/gates/reviews",
                {"project_id": project_id, "draft_id": draft["id"]},
            )
            chapter_result["durations"]["review_gate_duration_ms"] = gate_ms
            self.assertEqual(gate_resp.status_code, 200, msg=f"第{chapter_no}章 review_gate 失败: {gate_resp.text}")

            proposal_resp, _ = self._timed_post(
                f"/api/v1/chapters/drafts/{draft['id']}/changeset-proposals/generate",
                {"project_id": project_id},
            )
            self.assertEqual(proposal_resp.status_code, 200, msg=f"第{chapter_no}章 generate_changeset_proposal 失败: {proposal_resp.text}")
            proposal = proposal_resp.json()["data"]

            changeset_resp, _ = self._timed_post(
                "/api/v1/changesets/propose",
                {
                    "project_id": project_id,
                    "source_type": "chapter_draft",
                    "source_ref": draft["id"],
                    "rationale": proposal["rationale"],
                    "patch_operations": proposal["patch_operations"],
                },
            )
            self.assertEqual(changeset_resp.status_code, 200, msg=f"第{chapter_no}章 changeset_propose 失败: {changeset_resp.text}")
            changeset = changeset_resp.json()["data"]

            approve_resp, _ = self._timed_post(
                f"/api/v1/changesets/{changeset['id']}/approve",
                {"approved_by": "stage3-multi-chapter"},
            )
            self.assertEqual(approve_resp.status_code, 200, msg=f"第{chapter_no}章 changeset_approve 失败: {approve_resp.text}")

            apply_resp, _ = self._timed_post(f"/api/v1/changesets/{changeset['id']}/apply", None)
            self.assertEqual(apply_resp.status_code, 200, msg=f"第{chapter_no}章 changeset_apply 失败: {apply_resp.text}")

            publish_resp, _ = self._timed_post(
                "/api/v1/chapters/drafts/publish",
                {"project_id": project_id, "draft_id": draft["id"], "published_by": "stage3-multi-chapter"},
            )
            self.assertEqual(publish_resp.status_code, 200, msg=f"第{chapter_no}章 publish 失败: {publish_resp.text}")
            publish_data = publish_resp.json()["data"]
            self.assertEqual(publish_data["publish_record"]["publish_status"], "published")
            published_id = publish_data["published_chapter"]["id"]
            chapter_result["published_chapter_id"] = published_id
            self._export_chapter_text(
                chapter_no=chapter_no,
                source_type="published",
                body_text=self._extract_text_payload(publish_data.get("published_chapter") if isinstance(publish_data, dict) else {}),
                project_id=project_id,
                published_chapter_id=published_id,
            )

            summary_resp, summary_ms = self._timed_post(
                f"/api/v1/chapters/published/{published_id}/summary/generate",
                {"project_id": project_id, "published_chapter_id": published_id},
            )
            chapter_result["durations"]["summary_duration_ms"] = summary_ms
            self.assertEqual(summary_resp.status_code, 200, msg=f"第{chapter_no}章 summary 失败: {summary_resp.text}")
            summary = summary_resp.json()["data"]
            self.assertTrue(summary.get("summary"))
            self.assertTrue(summary.get("next_chapter_seed"))
            chapter_result["summary"] = summary.get("summary")
            chapter_result["next_chapter_seed"] = summary.get("next_chapter_seed")
            summary_body = "\n\n".join(
                [
                    f"summary:\n{summary.get('summary') or ''}",
                    f"state_summary:\n{summary.get('state_summary') or ''}",
                    f"next_chapter_seed:\n{summary.get('next_chapter_seed') or ''}",
                ]
            )
            self._export_chapter_text(
                chapter_no=chapter_no,
                source_type="summary",
                body_text=summary_body,
                project_id=project_id,
                published_chapter_id=published_id,
                next_chapter_seed=summary.get("next_chapter_seed"),
                state_summary=summary.get("state_summary"),
            )

            derived_resp, _ = self._timed_post(
                f"/api/v1/chapters/published/{published_id}/derived-updates/run",
                {"project_id": project_id, "published_chapter_id": published_id},
            )
            self.assertEqual(derived_resp.status_code, 200, msg=f"第{chapter_no}章 derived_updates 失败: {derived_resp.text}")
            derived = derived_resp.json()["data"]
            self.assertGreaterEqual(len(derived.get("tasks") or []), 1)
            chapter_result["derived"] = derived

            published_resp = self.client.get("/api/v1/chapters/published", params={"project_id": project_id})
            self.assertEqual(published_resp.status_code, 200, msg=f"第{chapter_no}章 list_published 失败: {published_resp.text}")
            published_items = published_resp.json()["data"]
            chapter_result["published_count_after"] = len(published_items)
            self.assertEqual(len(published_items), expected_published_count_before + 1)

            calls_after = self._list_agent_calls(project_id=project_id)
            new_calls = [item for item in calls_after if item.get("id") not in call_ids_before]
            chapter_result["new_agent_calls"] = new_calls
            self.assertGreaterEqual(len(new_calls), 1)

            parse_report_count = 0
            degraded_count = 0
            fallback_count = 0
            for item in new_calls:
                self.assertNotEqual(item.get("active_provider"), "mock")
                self.assertFalse(bool(item.get("fallback_used")))
                self.assertNotEqual(item.get("call_status"), "fallback_success")
                if bool(item.get("fallback_used")) or item.get("call_status") == "fallback_success":
                    fallback_count += 1

                response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
                parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
                if isinstance(parse_report, dict):
                    parse_report_count += 1
                    self.assertFalse(bool(parse_report.get("degraded")))
                    self.assertNotEqual(parse_report.get("route"), "provider_fallback")
                    self.assertNotEqual(parse_report.get("decision"), "failed")
                    if bool(parse_report.get("degraded")):
                        degraded_count += 1

            chapter_result["agent_call_count"] = len(new_calls)
            chapter_result["parse_report_count"] = parse_report_count
            chapter_result["degraded_count"] = degraded_count
            chapter_result["fallback_count"] = fallback_count
            chapter_result["success"] = True
        except Exception as exc:  # noqa: BLE001
            chapter_result["error"] = f"{type(exc).__name__}: {exc}"
            calls_after = self._list_agent_calls(project_id=project_id)
            new_calls = [item for item in calls_after if item.get("id") not in call_ids_before]
            chapter_result["new_agent_calls"] = new_calls
        finally:
            chapter_result["durations"]["total_duration_ms"] = int((time.perf_counter() - start_total) * 1000)

        return chapter_result

    def test_real_provider_multi_chapter_continuity_acceptance(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        chapter_plans = {
            1: "第一章建立冲突",
            2: "第二章扩大冲突并推进主角行动",
            3: "第三章让冲突升级并形成阶段性结果",
        }

        chapter_results: list[dict[str, Any]] = []
        previous_summary = None
        previous_seed = None
        previous_published_id = None
        published_count = 0
        for chapter_no in [1, 2, 3]:
            result = self._run_single_chapter(
                project_id=project_id,
                chapter_no=chapter_no,
                current_volume_goal=chapter_plans[chapter_no],
                previous_summary=previous_summary,
                previous_next_seed=previous_seed,
                previous_published_id=previous_published_id,
                expected_published_count_before=published_count,
            )
            chapter_results.append(result)
            if not result.get("success"):
                break
            previous_summary = result.get("summary")
            previous_seed = result.get("next_chapter_seed")
            previous_published_id = result.get("published_chapter_id")
            published_count = int(result.get("published_count_after") or published_count)

        failed_items = [item for item in chapter_results if not item.get("success")]
        if failed_items:
            failed = failed_items[0]
            success_brief = [
                {
                    "chapter_no": item["chapter_no"],
                    "published_chapter_id": item.get("published_chapter_id"),
                    "next_chapter_seed": item.get("next_chapter_seed"),
                    "published_count_after": item.get("published_count_after"),
                    "durations": item.get("durations"),
                }
                for item in chapter_results
                if item.get("success")
            ]
            failed_calls = failed.get("new_agent_calls", [])
            self.fail(
                "真实 provider 连续章节验收失败：\n"
                f"- 失败章号: 第{failed['chapter_no']}章\n"
                f"- project_id: {project_id}\n"
                f"- 失败原因: {failed.get('error')}\n"
                f"- gateway_status: {failed.get('gateway_status')}\n"
                f"- 本章 published_chapter_id: {failed.get('published_chapter_id')}\n"
                f"- 本章 next_chapter_seed: {failed.get('next_chapter_seed')}\n"
                f"- 已成功章节摘要: {success_brief}\n"
                f"- 三章耗时摘要: {[item.get('durations') for item in chapter_results]}\n"
                f"- 最近 agent 调用摘要:\n{self._diagnostic_recent_calls(failed_calls)}\n"
                f"- 导出目录: {self.export_dir}\n"
                f"- 已导出文件: {self.exported_files}\n"
                f"- 导出告警: {self.export_warnings}"
            )

        self.assertEqual(len(chapter_results), 3, msg=f"连续章节验收应成功 3 章，实际成功 {len(chapter_results)} 章")
        self.assertTrue(all(item["project_id"] == project_id for item in chapter_results))
        self.assertEqual([item["chapter_no"] for item in chapter_results], [1, 2, 3])
        self.assertTrue(all(item.get("published_chapter_id") for item in chapter_results))
        self.assertTrue(all(item.get("next_chapter_seed") for item in chapter_results))
        self.assertEqual([item.get("published_count_after") for item in chapter_results], [1, 2, 3])
        self.assertTrue(all(item.get("degraded_count") == 0 for item in chapter_results), msg=f"存在 degraded 调用：{chapter_results}")
        self.assertTrue(all(item.get("fallback_count") == 0 for item in chapter_results), msg=f"存在 fallback 调用：{chapter_results}")
        print(f"已导出章节正文到: {self.export_dir}")
        print(f"导出文件数量: {len(self.exported_files)}")
        for item in self.exported_files:
            print(f"- {item}")
        for warning in self.export_warnings:
            print(f"⚠️ 导出告警: {warning}")


if __name__ == "__main__":
    unittest.main()
