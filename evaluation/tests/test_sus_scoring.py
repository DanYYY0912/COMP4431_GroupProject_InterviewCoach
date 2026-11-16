import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from evaluation.metrics import sus_score
from scripts.score_sus import main, read_rows, summarise

HEADER = ",".join(
    ["participant_id", *[f"q{index}" for index in range(1, 11)]]
    + ["flow_completed", "duration_minutes"]
)


def write_sheet(directory, body, header=HEADER):
    path = Path(directory) / "usability.csv"
    path.write_text(header + "\n" + body, encoding="utf-8")
    return path


def run_main(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class SusDirectionTests(unittest.TestCase):
    def test_all_neutral_answers_score_fifty(self):
        self.assertEqual(sus_score([3] * 10), 50.0)

    def test_straight_positive_and_negative_extremes(self):
        self.assertEqual(sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]), 100.0)
        self.assertEqual(sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]), 0.0)

    def test_each_odd_item_is_positive_and_each_even_item_is_negative(self):
        for index in (0, 2, 4, 6, 8):
            answers = [3] * 10
            answers[index] = 5
            self.assertEqual(sus_score(answers), 55.0, f"q{index + 1} direction")
        for index in (1, 3, 5, 7, 9):
            answers = [3] * 10
            answers[index] = 5
            self.assertEqual(sus_score(answers), 45.0, f"q{index + 1} direction")


class SummaryTests(unittest.TestCase):
    def test_two_known_participants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_sheet(
                directory,
                "P1,4,2,4,2,4,2,4,2,4,2,true,12\n"
                "P2,5,1,5,1,5,1,5,1,5,1,false,14\n",
            )
            summary = summarise(read_rows(path))
        self.assertEqual(summary["participant_count"], 2)
        self.assertEqual(summary["sample_status"], "below_release_sample")
        self.assertEqual(summary["mean_sus"], 87.5)
        self.assertEqual(summary["median_sus"], 87.5)
        self.assertAlmostEqual(summary["sd_sus"], 17.68, places=2)
        self.assertEqual(summary["min_sus"], 75.0)
        self.assertEqual(summary["max_sus"], 100.0)
        self.assertEqual(summary["flow_completion_count"], 1)
        self.assertEqual(summary["flow_completion_percent"], 50.0)
        self.assertEqual(summary["mean_duration_minutes"], 13.0)
        self.assertFalse(summary["release_gates"]["participants_5_to_8"])
        self.assertFalse(summary["release_gates"]["all_met"])

    def test_gate_is_met_only_with_five_to_eight_participants(self):
        rows = [
            {
                "participant_id": f"P{index}",
                "sus": 100.0,
                "flow_completed": True,
                "duration_minutes": 10.0,
            }
            for index in range(1, 6)
        ]
        summary = summarise(rows)
        self.assertEqual(summary["mean_sus"], 100.0)
        self.assertEqual(summary["flow_completion_percent"], 100.0)
        self.assertTrue(summary["release_gates"]["all_met"])

    def test_missing_optional_fields_are_not_imputed(self):
        with tempfile.TemporaryDirectory() as directory:
            header = ",".join(["participant_id", *[f"q{index}" for index in range(1, 11)]])
            path = write_sheet(directory, "P1,3,3,3,3,3,3,3,3,3,3\n", header=header)
            summary = summarise(read_rows(path))
        self.assertEqual(summary["mean_sus"], 50.0)
        self.assertIsNone(summary["flow_completion_rate"])
        self.assertIsNone(summary["mean_duration_minutes"])
        self.assertFalse(summary["release_gates"]["flow_completion_at_least_90_percent"])


class CliTests(unittest.TestCase):
    def test_cli_prints_table_and_writes_measured_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_sheet(
                directory,
                "P1,4,2,4,2,4,2,4,2,4,2,true,12\n"
                "P2,5,1,5,1,5,1,5,1,5,1,false,14\n",
            )
            destination = Path(directory) / "results" / "usability_metrics.json"
            code, stdout, stderr = run_main(
                [str(source), "--out", str(destination)]
            )
            self.assertEqual(stderr, "")
            self.assertEqual(code, 0)
            payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "measured")
        self.assertFalse(payload["summary"]["release_gates"]["all_met"])
        self.assertEqual(
            [row["participant_id"] for row in payload["participants"]], ["P1", "P2"]
        )
        self.assertEqual(payload["participants"][0]["sus"], 75.0)
        self.assertEqual(payload["participants"][1]["sus"], 100.0)
        self.assertIn("| P1 | 75.0 | yes | 12.0 |", stdout)
        self.assertIn("Mean SUS: **87.50**", stdout)
        self.assertIn("Release gate: **NOT MET**", stdout)

    def test_empty_sheet_is_refused_and_no_metrics_file_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_sheet(directory, "")
            destination = Path(directory) / "usability_metrics.json"
            code, stdout, stderr = run_main([str(source), "--out", str(destination)])
            self.assertEqual(code, 2)
            self.assertFalse(destination.exists())
            self.assertIn("refusing", stderr)
            self.assertEqual(stdout, "")

    def test_out_of_range_answers_are_rejected(self):
        for bad in ("0", "6", "3.5", "abc", ""):
            with self.subTest(value=bad), tempfile.TemporaryDirectory() as directory:
                row = f"P1,3,3,3,3,{bad},3,3,3,3,3,true,10"
                source = write_sheet(directory, row + "\n")
                destination = Path(directory) / "usability_metrics.json"
                code, _, stderr = run_main([str(source), "--out", str(destination)])
                self.assertEqual(code, 2)
                self.assertFalse(destination.exists())
                self.assertIn("q5", stderr)

    def test_missing_answer_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            header = ",".join(
                ["participant_id", *[f"q{index}" for index in range(1, 10)]]
            )
            source = write_sheet(
                directory, "P1,3,3,3,3,3,3,3,3,3\n", header=header
            )
            destination = Path(directory) / "usability_metrics.json"
            code, _, stderr = run_main([str(source), "--out", str(destination)])
            self.assertEqual(code, 2)
            self.assertFalse(destination.exists())
            self.assertIn("q10", stderr)

    def test_duplicate_participant_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = write_sheet(
                directory,
                "P1,3,3,3,3,3,3,3,3,3,3,true,10\n"
                "P1,4,4,4,4,4,4,4,4,4,4,true,10\n",
            )
            destination = Path(directory) / "usability_metrics.json"
            code, _, stderr = run_main([str(source), "--out", str(destination)])
            self.assertEqual(code, 2)
            self.assertFalse(destination.exists())
            self.assertIn("duplicate participant_id", stderr)

    def test_jsonl_accepts_sus_answers_array(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "usability.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "participant_id": "P1",
                        "sus_answers": [3] * 10,
                        "flow_completed": "yes",
                        "duration_minutes": 9.5,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            destination = Path(directory) / "usability_metrics.json"
            code, _, stderr = run_main([str(source), "--out", str(destination)])
            self.assertEqual(stderr, "")
            self.assertEqual(code, 0)
            payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(payload["participants"][0]["sus"], 50.0)
        self.assertTrue(payload["participants"][0]["flow_completed"])


if __name__ == "__main__":
    unittest.main()
