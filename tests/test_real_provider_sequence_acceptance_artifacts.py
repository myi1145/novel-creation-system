import json
import tempfile
import unittest
from pathlib import Path

from tests.real_provider_sequence_acceptance_artifacts import export_real_provider_sequence_artifacts


class RealProviderSequenceAcceptanceArtifactsTest(unittest.TestCase):
    def test_export_should_generate_expected_artifacts_and_summary_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            payload = {
                "batch_status": "completed",
                "next_action": None,
                "stopped_at_chapter_no": None,
                "chapter_results": [
                    {
                        "chapter_no": 1,
                        "stage_status": "completed",
                        "published_chapter_id": "pub-1",
                        "latest_summary": "chapter-1-summary",
                        "latest_next_chapter_seed": "seed-1",
                        "derived_update_status": "completed",
                        "chapter_result": {
                            "draft": {"content": "chapter one text"},
                            "continuity_pack": {"source_published_chapter_id": None},
                        },
                    },
                    {
                        "chapter_no": 2,
                        "stage_status": "completed",
                        "published_chapter_id": "pub-2",
                        "latest_summary": "chapter-2-summary",
                        "latest_next_chapter_seed": "seed-2",
                        "derived_update_status": "completed_with_warnings",
                        "chapter_result": {
                            "draft": {"content": "chapter two text"},
                            "continuity_pack": {"source_published_chapter_id": "pub-1"},
                        },
                    },
                ],
                "sequence_batch_report": {"summary": {"completed_chapter_count": 2}},
            }

            export_result = export_real_provider_sequence_artifacts(
                output_root=output_root,
                acceptance_name="real_provider_sequence_acceptance",
                provider_name="openai_compatible",
                model_name="gpt-test",
                project_id="project-1",
                workflow_run_id="run-12345678",
                chapter_count=2,
                sequence_response_data=payload,
            )

            artifact_dir = Path(export_result["artifact_dir"])
            acceptance_summary_path = Path(export_result["acceptance_summary_path"])
            batch_report_path = Path(export_result["sequence_batch_report_path"])

            self.assertTrue(artifact_dir.exists())
            self.assertTrue(acceptance_summary_path.exists())
            self.assertTrue(batch_report_path.exists())
            self.assertTrue((artifact_dir / "chapter_01.txt").exists())
            self.assertTrue((artifact_dir / "chapter_01_summary.json").exists())
            self.assertTrue((artifact_dir / "chapter_02.txt").exists())
            self.assertTrue((artifact_dir / "chapter_02_summary.json").exists())

            summary = json.loads(acceptance_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["completed_chapter_count"], 2)
            self.assertEqual(summary["failed_chapter_count"], 0)
            self.assertEqual(summary["attention_chapter_count"], 0)


if __name__ == "__main__":
    unittest.main()
