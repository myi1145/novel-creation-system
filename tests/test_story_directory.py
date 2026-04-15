import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import CanonSnapshotORM, ChangeSetORM, ImmutableLogORM, StoryDirectoryORM
from app.db.session import SessionLocal
from app.main import create_app


class StoryDirectoryApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"story-directory-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            canon_count = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
            changeset_count = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()
            return canon_count, changeset_count

    def _count_stale_events(self, project_id: str) -> int:
        with SessionLocal() as db:
            return (
                db.query(ImmutableLogORM)
                .filter(
                    ImmutableLogORM.project_id == project_id,
                    ImmutableLogORM.event_type == "chapter_dependency_stale_marked",
                )
                .count()
            )

    def test_story_directory_minimal_loop(self):
        project_a = self._create_project("a")
        project_b = self._create_project("b")

        before_counts = self._count_canon_and_changesets(project_a)
        stale_before = self._count_stale_events(project_a)

        empty_resp = self.client.get(f"/api/v1/projects/{project_a}/story-directory")
        self.assertEqual(empty_resp.status_code, 200)
        self.assertIsNone(empty_resp.json()["data"])

        create_payload = {
            "directory_title": "全书章节目录",
            "directory_summary": "第一卷起势，第二卷扩张。",
            "directory_status": "draft",
            "chapter_items": [
                {
                    "chapter_no": 1,
                    "chapter_title": "灵根初现",
                    "chapter_role": "开篇立主线",
                    "chapter_goal": "主角获得入局契机",
                    "stage_label": "第一卷 / 起势阶段",
                    "required_entities": ["林尘", "青石镇", "清虚宗"],
                    "required_seed_points": ["灵根觉醒", "宗门线开启"],
                    "foreshadow_constraints": ["埋下玉简来历", "不揭露最终反派"],
                }
            ],
        }
        create_resp = self.client.put(f"/api/v1/projects/{project_a}/story-directory", json=create_payload)
        self.assertEqual(create_resp.status_code, 200)
        create_data = create_resp.json()["data"]
        self.assertEqual(create_data["directory_status"], "draft")
        self.assertEqual(create_data["last_update_source"], "manual")
        self.assertEqual(len(create_data["chapter_items"]), 1)

        update_payload = {
            "directory_title": "全书章节目录-更新",
            "directory_summary": "更新后的目录摘要",
            "directory_status": "confirmed",
            "chapter_items": [
                {
                    "chapter_no": 1,
                    "chapter_title": "灵根初现（修订）",
                    "chapter_role": "开篇立主线",
                    "chapter_goal": "主角获得入局契机",
                    "stage_label": "第一卷 / 起势阶段",
                    "required_entities": ["林尘", "清虚宗"],
                    "required_seed_points": ["灵根觉醒"],
                    "foreshadow_constraints": ["不揭露最终反派"],
                },
                {
                    "chapter_no": 2,
                    "chapter_title": "初入宗门",
                    "chapter_role": "建立门派关系",
                    "chapter_goal": "落地第一轮冲突",
                    "stage_label": "第一卷 / 起势阶段",
                    "required_entities": ["林尘", "执事长老"],
                    "required_seed_points": ["外门规则"],
                    "foreshadow_constraints": ["仅暗示支线反派"],
                },
            ],
        }
        update_resp = self.client.put(f"/api/v1/projects/{project_a}/story-directory", json=update_payload)
        self.assertEqual(update_resp.status_code, 200)
        update_data = update_resp.json()["data"]
        self.assertEqual(update_data["id"], create_data["id"])
        self.assertEqual(update_data["directory_status"], "confirmed")
        self.assertEqual(update_data["chapter_items"][1]["chapter_no"], 2)

        get_resp = self.client.get(f"/api/v1/projects/{project_a}/story-directory")
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()["data"]
        self.assertEqual(get_data["id"], create_data["id"])
        self.assertEqual(get_data["directory_title"], "全书章节目录-更新")
        self.assertEqual(len(get_data["chapter_items"]), 2)

        invalid_status = self.client.put(
            f"/api/v1/projects/{project_a}/story-directory",
            json={
                "directory_title": "x",
                "directory_summary": "x",
                "directory_status": "archived",
                "chapter_items": [{"chapter_no": 1, "chapter_title": "x"}],
            },
        )
        self.assertEqual(invalid_status.status_code, 422)

        isolation_resp = self.client.get(f"/api/v1/projects/{project_b}/story-directory")
        self.assertEqual(isolation_resp.status_code, 200)
        self.assertIsNone(isolation_resp.json()["data"])

        with SessionLocal() as db:
            rows_a = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_a).all()
            rows_b = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_b).all()
            self.assertEqual(len(rows_a), 1)
            self.assertEqual(len(rows_b), 0)
            self.assertEqual(rows_a[0].last_update_source, "manual")

        after_counts = self._count_canon_and_changesets(project_a)
        stale_after = self._count_stale_events(project_a)
        self.assertEqual(before_counts, after_counts)
        self.assertEqual(stale_before, stale_after)


if __name__ == "__main__":
    unittest.main()
