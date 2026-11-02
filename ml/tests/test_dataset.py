import unittest
from copy import deepcopy

from ml.dataset import generate_drafts, split_dataset, validate_dataset
from ml.train import mask_completion


class DatasetTests(unittest.TestCase):
    def test_draft_distribution_matches_plan_and_has_no_fake_review(self):
        rows = generate_drafts()
        self.assertEqual(len(rows), 1500)
        self.assertEqual(sum(r["language"] == "en-HK" for r in rows), 900)
        self.assertEqual(sum(r["language"] == "zh-HK" for r in rows), 450)
        self.assertEqual(sum(r["language"] == "mixed" for r in rows), 150)
        self.assertEqual(sum(r["task"] == "question" for r in rows), 600)
        self.assertEqual(sum(r["task"] == "feedback" for r in rows), 525)
        self.assertEqual(sum(r["task"] == "report" for r in rows), 225)
        self.assertEqual(sum(r["task"] == "safety" for r in rows), 150)
        self.assertTrue(all(r["reviews"] == [] for r in rows))

    def test_unreviewed_examples_cannot_be_used_for_training(self):
        result = validate_dataset(generate_drafts()[:3], require_review=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("review" in e for e in result["errors"]))

    def test_same_person_cannot_supply_both_reviews(self):
        row = generate_drafts()[0]
        row["double_review_required"] = True
        review = {
            "reviewer": "student-a",
            "decision": "approved",
            "reviewed_at": "2026-11-02T12:00:00Z",
            "content_sha256": row["content_sha256"],
        }
        row["reviews"] = [review, deepcopy(review)]
        self.assertFalse(validate_dataset([row], require_review=True)["valid"])

    def test_group_split_never_splits_role_family_or_source(self):
        groups = split_dataset(generate_drafts(), check_duplicates=False)
        roles = {s: {r["role_family"] for r in rows} for s, rows in groups.items()}
        self.assertFalse(roles["train"] & roles["validation"])
        self.assertFalse(roles["train"] & roles["test"])
        self.assertEqual(
            {k: len(v) for k, v in groups.items()},
            {"train": 1200, "validation": 150, "test": 150},
        )

    def test_changed_answer_invalidates_old_review(self):
        row = generate_drafts()[0]
        row["reviews"] = [
            {
                "reviewer": "a",
                "decision": "approved",
                "reviewed_at": "2026-11-02T12:00:00Z",
                "content_sha256": row["content_sha256"],
            }
        ]
        row["messages"][-1]["content"] = row["messages"][-1]["content"].replace(
            "Result", "Action"
        )
        result = validate_dataset([row], require_review=True)
        self.assertTrue(any("hash changed" in error for error in result["errors"]))

    def test_draft_templates_are_rejected_for_release_splitting(self):
        with self.assertRaises(ValueError):
            split_dataset(generate_drafts())

    def test_near_duplicates_cannot_be_promoted_by_changing_ids(self):
        rows = generate_drafts()[:1]
        duplicate = deepcopy(rows[0])
        duplicate["id"] = "renamed-copy"
        result = validate_dataset(rows + [duplicate], check_duplicates=True)
        self.assertFalse(result["valid"])
        self.assertEqual(result["near_duplicates"][0]["similarity"], 1.0)

    def test_prompt_tokens_are_masked_and_completion_remains(self):
        self.assertEqual(mask_completion([1, 2, 3, 4], [1, 2]), [-100, -100, 3, 4])
        with self.assertRaises(ValueError):
            mask_completion([1, 9, 3], [1, 2])
        with self.assertRaises(ValueError):
            mask_completion([1, 2], [1, 2])


if __name__ == "__main__":
    unittest.main()
