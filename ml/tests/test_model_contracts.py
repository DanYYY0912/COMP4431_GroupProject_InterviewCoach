import json
import unittest

from backend.app.coach import ModelCoachTurn, ModelReport
from ml.dataset import generate_drafts
from ml.schemas import SCHEMAS, validate


class ModelContractTests(unittest.TestCase):
    def test_training_output_keys_match_runtime_model_contracts(self):
        expected = {
            "question": ModelCoachTurn,
            "safety": ModelCoachTurn,
            "feedback": ModelReport,
            "report": ModelReport,
        }
        for task, model in expected.items():
            self.assertEqual(set(SCHEMAS[task]["properties"]), set(model.model_fields))

    def test_every_draft_is_accepted_by_runtime_pydantic_models(self):
        for row in generate_drafts():
            model = (
                ModelCoachTurn if row["task"] in ("question", "safety") else ModelReport
            )
            output = json.loads(row["messages"][-1]["content"])
            model.model_validate(output)
            self.assertFalse(validate(output, SCHEMAS[row["task"]]))
            self.assertNotIn("speech_metrics", output)
            self.assertNotIn("citations", output)


if __name__ == "__main__":
    unittest.main()
