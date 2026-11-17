import json
import unittest

from evaluation import run
from evaluation.metrics import (
    citation_precision,
    cohens_kappa,
    error_rate,
    percentile,
    recall_at_k,
    sus_score,
    validate_output,
)


def test_no_rag_removes_current_and_legacy_source_fields():
    passages = [{"text": "Fixture passage"}]
    payload = {"quoted_sources": passages, "job_sources": passages, "language": "en-HK"}
    row = {
        "messages": [
            {"role": "system", "content": "Fixture"},
            {"role": "user", "content": json.dumps(payload)},
            {"role": "assistant", "content": "Fixture target"},
        ]
    }
    assert json.loads(run.model_messages(row)[-1]["content"]) == payload
    no_rag = json.loads(run.model_messages(row, include_sources=False)[-1]["content"])
    assert no_rag == {"quoted_sources": [], "job_sources": [], "language": "en-HK"}
    assert json.loads(row["messages"][1]["content"]) == payload


def test_evaluation_refresh_keeps_archived_training_and_benchmark_limits(
    tmp_path, monkeypatch
):
    training = {"status": "training_completed", "reviewed_examples": 971}
    limit = "Historical no-RAG run needs a rerun."
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"recorded_training": training}))
    (tmp_path / "model.json").write_text(json.dumps({"limitations": [limit]}))
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr(run, "training_metadata", lambda: {"status": "not_trained"})

    run.write_result("smoke", {"status": "software_check"})

    refreshed = json.loads(latest.read_text())
    assert refreshed["recorded_training"] == training
    assert refreshed["training"]["status"] == "not_trained"
    assert limit in refreshed["limitations"]


class MetricTests(unittest.TestCase):
    def test_word_and_character_error(self):
        self.assertAlmostEqual(error_rate("I built a test", "I built test"), 0.25)
        self.assertAlmostEqual(error_rate("我做測試", "我做試", unit="character"), 0.25)
        with self.assertRaises(ValueError):
            error_rate("", "anything")

    def test_percentile_is_interpolated(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 95), 4.8)
        with self.assertRaises(ValueError):
            percentile([], 95)

    def test_retrieval_uses_relevant_denominator(self):
        self.assertEqual(recall_at_k(["x", "a"], ["a", "b"], 5), 0.5)
        self.assertEqual(citation_precision(["a", "x"], ["a"]), 0.5)

    def test_human_metrics(self):
        self.assertEqual(cohens_kappa(["A", "B", "A"], ["A", "B", "A"]), 1)
        self.assertEqual(sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]), 100)
        with self.assertRaises(ValueError):
            sus_score([5, 0] * 5)

    def test_output_validation_rejects_unknown_fields(self):
        response = {
            "interviewer_text": "Explain your action.",
            "question_type": "follow_up",
            "targeted_competencies": ["testing"],
            "adaptive_follow_up_reason": "Missing action",
            "citation_ids": ["source-a"],
        }
        self.assertTrue(validate_output(response, "question"))
        self.assertFalse(validate_output({**response, "hire_score": 90}, "question"))
        self.assertFalse(
            validate_output({**response, "interviewer_text": ""}, "question")
        )
        self.assertFalse(
            validate_output({**response, "citation_ids": ["source-a"] * 5}, "question")
        )


if __name__ == "__main__":
    unittest.main()
