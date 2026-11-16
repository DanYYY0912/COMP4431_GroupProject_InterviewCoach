"""All approvals below are explicit test-only fixtures, never training data."""

import argparse
import copy
import json
from unittest.mock import patch

import pytest

from ml.dataset import (
    content_hash,
    generate_drafts,
    read_jsonl,
    validate_dataset,
    write_jsonl,
)
from ml.review import (
    apply_edits,
    atomic_write,
    automatic_checks,
    display_example,
    eligible,
    load_records,
    merge,
    parse_shard,
    record_decision,
    save_edit,
    shard_rows,
    slug,
    start,
    status,
)


@pytest.fixture
def row():
    return next(
        r
        for r in generate_drafts()
        if r["task"] == "report" and r["language"] == "en-HK"
    )


def test_shards_are_exhaustive_disjoint_and_repeatable():
    rows = [{"id": str(i)} for i in range(17)]
    parts = [{r["id"] for r in shard_rows(rows, f"{i}/4")} for i in range(1, 5)]
    assert set.union(*parts) == {r["id"] for r in rows}
    assert sum(map(len, parts)) == len(rows)
    assert shard_rows(rows, "3/4") == shard_rows(rows, "3/4")
    for bad in ("0/4", "5/4", "1/0", "bad", "1/2/3"):
        with pytest.raises(ValueError):
            parse_shard(bad)


def test_second_review_requires_another_human_and_current_hash(row, tmp_path):
    row["double_review_required"] = True
    assert not eligible(row, [], "Test Reviewer B", second=True)
    record = record_decision(row, "Test Reviewer A", "approved", tmp_path)
    assert not eligible(row, [record], " test reviewer a ", second=True)
    assert eligible(row, [record], "Test Reviewer B", second=True)
    row["content_sha256"] = "changed"
    assert not eligible(row, [record], "Test Reviewer B", second=True)
    row["double_review_required"] = False
    assert not eligible(row, [record], "Test Reviewer B", second=True)


def test_edit_invalidates_old_approvals_and_merge_is_idempotent(row, tmp_path):
    row["double_review_required"] = True
    reviews, edits = tmp_path / "reviews", tmp_path / "edits"
    record_decision(row, "Test Reviewer A", "approved", reviews)
    output = json.loads(row["messages"][-1]["content"])
    output["retry_exercise"] = "Explain one verified outcome."
    updated = save_edit(row, output, edits)
    assert updated["content_sha256"] != row["content_sha256"]
    assert not eligible(updated, load_records(reviews), "Test Reviewer B", second=True)
    merged = merge([row], reviews, edits, tmp_path / "merged.jsonl")
    assert not merged[0]["reviews"]
    assert not validate_dataset(merged, require_review=True)["valid"]
    record_decision(updated, "Test Reviewer A", "approved", reviews)
    record_decision(updated, "Test Reviewer B", "approved", reviews)
    merged = merge([row], reviews, edits, tmp_path / "merged.jsonl")
    assert validate_dataset(merged, require_review=True)["valid"]
    assert merged == merge(merged, reviews, edits, tmp_path / "merged.jsonl")
    assert merged[0]["content_sha256"] == content_hash(merged[0])
    # Further editing after a merge also works, and both approvals become stale.
    output["retry_exercise"] = "Retry using your exact observations."
    save_edit(merged[0], output, edits)
    assert not merge(merged, reviews, edits, tmp_path / "merged.jsonl")[0]["reviews"]


def test_rejection_revokes_prior_approval_and_requires_reason(row, tmp_path):
    record_decision(row, "Test Reviewer A", "approved", tmp_path)
    with pytest.raises(ValueError, match="reason"):
        record_decision(row, "Test Reviewer A", "rejected", tmp_path, " ")
    record_decision(
        row, "Test Reviewer A", "rejected", tmp_path, "Evidence needs checking"
    )
    result = merge([row], tmp_path, tmp_path / "edits", tmp_path / "output/merged.jsonl")
    assert result[0]["reviews"][0]["decision"] == "rejected"
    assert not validate_dataset(result, require_review=True)["valid"]
    assert eligible(row, load_records(tmp_path), "Test Reviewer A", revisit=True)


def test_atomic_interruption_keeps_last_saved_decision(row, tmp_path):
    record_decision(row, "Test Reviewer A", "approved", tmp_path)
    path = tmp_path / f"{slug('Test Reviewer A')}.jsonl"
    original = path.read_bytes()
    with (
        patch("ml.review.os.replace", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        atomic_write(path, "interrupted")
    assert path.read_bytes() == original
    assert not eligible(row, load_records(tmp_path), "Test Reviewer A")
    assert len(list(tmp_path.iterdir())) == 1


def test_interactive_interrupt_and_resume_preserves_progress(
    row, tmp_path, monkeypatch
):
    other = copy.deepcopy(row)
    other["id"] += "-second"
    write_jsonl(tmp_path / "input.jsonl", [row, other])
    args = argparse.Namespace(
        input=tmp_path / "input.jsonl",
        reviewer="Test Reviewer A",
        shard="1/1",
        second=False,
        revisit=False,
        reviews_dir=tmp_path / "reviews",
        edits_dir=tmp_path / "edits",
    )
    with (
        patch("builtins.input", side_effect=["a", KeyboardInterrupt]),
        pytest.raises(KeyboardInterrupt),
    ):
        start(args)
    records = load_records(args.reviews_dir)
    assert len(records) == 1
    with patch("builtins.input", side_effect=["a"]):
        start(args)
    assert len(load_records(args.reviews_dir)) == 2
    assert not read_jsonl(args.input)[0]["reviews"]


def test_blank_names_and_invalid_outputs_never_create_approvals(row, tmp_path):
    for name in ("", "   "):
        with pytest.raises(ValueError, match="nonblank"):
            record_decision(row, name, "approved", tmp_path)
    output = json.loads(row["messages"][-1]["content"])
    output["star"][0]["evidence"] = "fabricated evidence"
    row["messages"][-1]["content"] = json.dumps(output)
    assert automatic_checks(row)
    with pytest.raises(ValueError, match="Cannot approve"):
        record_decision(row, "Test Reviewer A", "approved", tmp_path)
    assert not list(tmp_path.glob("*.jsonl"))


def test_summary_evidence_and_real_utc_timestamp(row, tmp_path, capsys):
    row["double_review_required"] = True
    record = record_decision(row, "測試審核員甲", "approved", tmp_path)
    assert record["reviewed_at"].endswith("+00:00")
    assert record["reviewer"] == "測試審核員甲"
    result = status([row], [record])
    assert result["remaining"] == 1
    assert result["second_review"] == {"completed": 0, "required": 1, "remaining": 1}
    assert result["reviewers"]["測試審核員甲"]["approved"] == 1
    display_example(row)
    shown = capsys.readouterr().out
    assert "⟦" in shown and "⟧" in shown
    assert "AUTOMATIC CHECKS: PASS" in shown
    assert slug("Alice") != slug("Bob")
    assert slug("Alice") == slug(" alice ")


def test_changed_input_conflicts_with_saved_edit(row, tmp_path):
    output = json.loads(row["messages"][-1]["content"])
    output["retry_exercise"] = "Explain your outcome."
    save_edit(row, output, tmp_path)
    row["messages"][0]["content"] += "changed"
    with pytest.raises(ValueError, match="conflicts"):
        apply_edits([row], tmp_path)
