import unittest

from evaluation.metrics import (
    citation_precision,
    cohens_kappa,
    error_rate,
    percentile,
    recall_at_k,
    sus_score,
    validate_output,
)


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
            "citations": [],
        }
        self.assertTrue(validate_output(response, "question"))
        self.assertFalse(validate_output({**response, "hire_score": 90}, "question"))
        self.assertFalse(
            validate_output({**response, "interviewer_text": ""}, "question")
        )
        self.assertFalse(
            validate_output({**response, "citations": [{}] * 5}, "question")
        )


if __name__ == "__main__":
    unittest.main()
