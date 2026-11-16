"""Guards for the runtime-aligned draft corpus produced by ``ml.runtime_dataset``.

The file under test is an unreviewed draft corpus: it must be format-identical to what the
app sends, grounded in its own sources, free of near-duplicates, splittable without
leakage, and short enough for ``ml/train.py`` (2,048 tokens).
"""

import json
import math
import os
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

import pytest
from app.coach import (
    REPORT_INSTRUCTIONS,
    SYSTEM_PROMPT,
    ModelCoachTurn,
    ModelReport,
    answer_excerpts,
    check_question_output,
    check_report_output,
)
from app.ingestion import COMPETENCY_TERMS
from app.schemas import Citation

from ml.dataset import (
    near_duplicate_pairs,
    normalized_text,
    read_jsonl,
    split_dataset,
    validate_dataset,
)
from ml.runtime_dataset import (
    DOUBLE_REVIEW_RATE,
    TASK_TOTALS,
    TOTAL_ROWS,
    Builder,
    estimate_tokens,
    generate_rows,
    load_scenarios,
    shingles,
)

DRAFTS = Path(__file__).resolve().parents[1] / "data" / "runtime_drafts.jsonl"
ROWS = read_jsonl(DRAFTS)
STAR = ("Situation", "Task", "Action", "Result")
QUESTION_KEYS = {
    "language",
    "difficulty",
    "question_number",
    "allowed_competencies",
    "previous_answer",
    "quoted_sources",
}
REPORT_KEYS = {
    "task",
    "language",
    "allowed_competencies",
    "quoted_answer_excerpts",
    "quoted_sources",
}


def payload(row) -> dict:
    return json.loads(row["messages"][1]["content"])


def target(row) -> dict:
    return json.loads(row["messages"][2]["content"])


def sources_of(row) -> list[Citation]:
    return [Citation(**item) for item in payload(row)["quoted_sources"]]


def families() -> list[str]:
    jobs, _, _ = load_scenarios()
    return [family["role_family"] for family in jobs["families"]]


def test_counts_match_the_approved_plan():
    assert len(ROWS) == TOTAL_ROWS == 1000
    assert Counter(row["task"] for row in ROWS) == Counter(TASK_TOTALS)
    assert Counter(row["language"] for row in ROWS) == Counter({"en-HK": 600, "zh-HK": 400})
    assert len({row["id"] for row in ROWS}) == len(ROWS)
    assert (
        Counter((row["task"], row["language"]) for row in ROWS)
        == Counter(
            {
                ("question", "en-HK"): 270,
                ("question", "zh-HK"): 180,
                ("report", "en-HK"): 210,
                ("report", "zh-HK"): 140,
                ("safety", "en-HK"): 120,
                ("safety", "zh-HK"): 80,
            }
        )
    )


def test_each_role_family_gets_an_equal_share():
    expected = families()
    seen = Counter(row["role_family"] for row in ROWS)
    assert sorted(seen) == sorted(expected)
    # 15 families, 1000 rows: ten families take 67 and five take 66.
    assert sorted(seen.values()) == [66] * 5 + [67] * 10
    for family in expected:
        rows = [row for row in ROWS if row["role_family"] == family]
        assert {row["language"] for row in rows} == {"en-HK", "zh-HK"}, family
        assert {"question", "report"} <= {row["task"] for row in rows}, family
        assert {"question", "report"} <= {
            row["task"] for row in rows if row["language"] == "zh-HK"
        }, family


def test_every_row_passes_the_runtime_validators():
    for row in ROWS:
        body = payload(row)
        draft = json.loads(row["messages"][2]["content"])
        allowed = body["allowed_competencies"]
        sources = sources_of(row)
        assert allowed, row["id"]
        assert set(allowed) <= set(COMPETENCY_TERMS), row["id"]
        if row["task"] == "report":
            excerpts = body["quoted_answer_excerpts"]
            assert excerpts and all(isinstance(item, str) for item in excerpts)
            feedback = check_report_output(
                ModelReport.model_validate(draft), allowed, row["language"], excerpts, sources
            )
            assert len(feedback) <= 3
        else:
            check_question_output(
                ModelCoachTurn.model_validate(draft), allowed, row["language"], sources
            )


def test_citations_and_evidence_are_grounded_in_the_rows_own_sources():
    for row in ROWS:
        body = payload(row)
        draft = json.loads(row["messages"][2]["content"])
        source_ids = [source.chunk_id for source in sources_of(row)]
        if row["task"] == "report":
            excerpts = body["quoted_answer_excerpts"]
            for item in draft["star"]:
                assert item["present"] == bool(item["evidence"]), row["id"]
                if item["evidence"]:
                    assert any(item["evidence"] in text for text in excerpts), row["id"]
            for item in draft["competencies"]:
                assert set(item["citation_ids"]) <= set(source_ids), row["id"]
                assert item["name"] in body["allowed_competencies"], row["id"]
                if item["evidence"]:
                    assert any(item["evidence"] in text for text in excerpts), row["id"]
            for strength in draft["strengths"]:
                assert any(strength["evidence"] in text for text in excerpts), row["id"]
        else:
            assert set(draft["citation_ids"]) <= set(source_ids), row["id"]
            assert set(draft["targeted_competencies"]) <= set(body["allowed_competencies"])


def test_prompts_are_the_runtime_builders_output():
    for row in ROWS:
        system = row["messages"][0]["content"]
        body = payload(row)
        if row["task"] == "report":
            assert system == SYSTEM_PROMPT + REPORT_INSTRUCTIONS, row["id"]
            assert set(body) == REPORT_KEYS, row["id"]
            assert body["task"].startswith("Give reflective STAR coaching")
            assert body["language"] == row["language"]
        else:
            assert system == SYSTEM_PROMPT, row["id"]
            assert set(body) == QUESTION_KEYS, row["id"]
            assert body["language"] == row["language"]
            assert body["difficulty"] in {"foundation", "standard", "stretch"}
            assert body["question_number"] in {1, 3}
            if body["previous_answer"] is not None:
                assert body["previous_answer"]["language"] == row["language"]
                assert body["previous_answer"]["transcript"].strip()
        assert [message["role"] for message in row["messages"]] == [
            "system",
            "user",
            "assistant",
        ]


def test_injected_sources_are_visible_in_the_quoted_window():
    jobs, stories, injections = load_scenarios()
    builder = Builder(jobs, stories, injections)
    injected = [row for row in ROWS if row["safety_case"] == "source"]
    assert injected
    for row in injected:
        line = builder.injection_line(row["role_family"], row["language"])
        quoted = [source["text"] for source in payload(row)["quoted_sources"]]
        assert any(line in text for text in quoted), row["id"]
        assert any(
            source["source"] == "job-description.txt" for source in payload(row)["quoted_sources"]
        ), row["id"]
    asked = [row for row in ROWS if row["safety_case"] == "answer"]
    assert asked
    for row in asked:
        assert payload(row)["previous_answer"] is not None, row["id"]
        draft = target(row)
        assert draft["question_type"] == "follow_up", row["id"]
        assert draft["adaptive_follow_up_reason"], row["id"]


def test_no_near_duplicates_and_distinct_candidate_wording():
    pairs = near_duplicate_pairs(ROWS, limit=len(ROWS) ** 2)
    assert pairs == [], pairs[:3]
    texts = [normalized_text(row) for row in ROWS]
    assert all(texts), "every row must normalise to non-empty text"
    assert len(set(texts)) / len(texts) >= 0.99
    # Openings and injected sources carry no candidate answer, so their wording must
    # differ on its own; the generator enforces it with these shingles.
    plain = [texts[index] for index, row in enumerate(ROWS) if payload(row).get("previous_answer") is None
             and not payload(row).get("quoted_answer_excerpts")]
    assert len(plain) > 100
    assert len({frozenset(shingles(text)) for text in plain}) == len(plain)


def test_reports_cover_every_missing_star_element():
    reports = [row for row in ROWS if row["task"] == "report"]
    assert Counter(row["missing_star_element"] for row in reports)[None] > 0
    for element in STAR:
        assert sum(row["missing_star_element"] == element for row in reports) > 0
    absent = Counter()
    present = Counter()
    for row in reports:
        for item in target(row)["star"]:
            (present if item["present"] else absent)[item["element"]] += 1
    assert set(absent) == set(STAR)
    assert all(absent[element] > 0 and present[element] > 0 for element in STAR)
    assert sum(absent.values()) > 100


def test_report_star_shape_and_coaching_length_limits():
    for row in ROWS:
        if row["task"] != "report":
            continue
        draft = target(row)
        assert [item["element"] for item in draft["star"]] == list(STAR), row["id"]
        assert len(draft["competencies"]) <= 3, row["id"]
        assert len(draft["strengths"]) <= 2, row["id"]
        assert draft["strengths"], row["id"]
        coaching_text = [item["coaching"] for item in draft["star"]]
        coaching_text += [item["feedback"] for item in draft["competencies"]]
        coaching_text += [draft["prioritized_improvement"], draft["retry_exercise"]]
        coaching_text += [item["text"] for item in draft["strengths"]]
        for sentence in coaching_text:
            assert sentence.strip(), row["id"]
            for part in re.split(r"(?<=[.!?])\s+", sentence):
                if row["language"] == "zh-HK":
                    assert len(re.findall(r"[\u3400-\u9fff]", part)) <= 35, (row["id"], part)
                else:
                    assert len(re.findall(r"[A-Za-z0-9'-]+", part)) <= 20, (row["id"], part)


def test_reviews_are_empty_and_provenance_is_honest():
    for row in ROWS:
        assert row["reviews"] == [], row["id"]
        provenance = row["provenance"]
        assert provenance["kind"] == "synthetic_runtime_aligned_draft", row["id"]
        assert provenance["license"] == "CC0-1.0", row["id"]
        assert provenance["review_status"] == "unreviewed", row["id"]
        assert "review" in provenance["author"].lower(), row["id"]
        assert "review" in provenance["warning"].lower(), row["id"]
        assert row["role_family"] and row["source_id"] and row["template_family"]


def test_double_review_sampling_is_stratified_and_rounds_up():
    from ml.runtime_dataset import SECOND_REVIEW_TOPUP

    topup = set()
    if SECOND_REVIEW_TOPUP.exists():
        topup = {e["id"] for e in json.loads(SECOND_REVIEW_TOPUP.read_text())["rows"]}
    strata = defaultdict(list)
    for row in ROWS:
        strata[(row["language"], row["task"])].append(row)
    total = 0
    for key, group in strata.items():
        required = math.ceil(len(group) * DOUBLE_REVIEW_RATE)
        flagged = sum(bool(row["double_review_required"]) for row in group)
        # Rejected rows shrink a stratum, so 15% can demand more second reviews than the
        # original sampling produced; the documented top-up list closes that gap.
        extra = sum(1 for row in group if row["id"] in topup)
        assert flagged == required + extra, key
        assert flagged >= required, key
        total += flagged
    assert total == sum(bool(row["double_review_required"]) for row in ROWS) == 151 + len(topup)


def test_every_row_fits_the_training_token_limit():
    counts = sorted(estimate_tokens(row["messages"]) for row in ROWS)
    assert counts[-1] <= 2048
    assert counts[int(len(counts) * 0.99)] <= 1900
    # When the real tokenizer is available, check it as well; the estimate must be an
    # upper bound. Set QWEN_TOKENIZER_JSON to a tokenizer.json to enable this.
    tokenizer = _qwen_tokenizer()
    if tokenizer is None:
        return
    real = sorted(
        sum(len(tokenizer.encode(message["content"]).ids) for message in row["messages"]) + 24
        for row in ROWS
    )
    assert real[-1] <= 2048
    assert real[int(len(real) * 0.99)] <= 1900
    for row in ROWS:
        real_row = sum(len(tokenizer.encode(m["content"]).ids) for m in row["messages"]) + 24
        assert estimate_tokens(row["messages"]) >= real_row, row["id"]


def _qwen_tokenizer():
    path = Path(__file__).resolve().parents[2] / "ml" / "tokenizer.json"
    candidate = os.environ.get("QWEN_TOKENIZER_JSON")
    if not candidate and path.exists():
        candidate = str(path)
    if not candidate:
        return None
    try:
        from tokenizers import Tokenizer
    except ImportError:  # pragma: no cover - optional dependency, never required to train
        pytest.skip("tokenizers is not installed; the conservative estimate is used")
    return Tokenizer.from_file(candidate)


def test_reports_use_answer_excerpts_bounded_by_the_runtime_helper():
    for row in ROWS:
        if row["task"] != "report":
            continue
        answers = payload(row)["quoted_answer_excerpts"]
        assert 1 <= len(answers) <= 3
        for answer in answers:
            assert answer == answer_excerpts([answer])[0], row["id"]


def test_grouped_split_is_possible_once_reviews_are_recorded():
    rows = deepcopy(ROWS)
    for row in rows:
        reviewers = ["test-reviewer-a"]
        if row["double_review_required"]:
            reviewers.append("test-reviewer-b")
        row["reviews"] = [
            {
                "reviewer": name,
                "decision": "approved",
                "reviewed_at": "2026-11-16T00:00:00Z",
                "content_sha256": row["content_sha256"],
            }
            for name in reviewers
        ]
    check = validate_dataset(
        rows, require_review=True, check_duplicates=True, enforce_review_quota=True
    )
    assert check["valid"], check["errors"][:5]
    assert check["reviewed"] == len(rows)
    # Drafts as shipped must still be blocked by the human-review gate only.
    draft_check = validate_dataset(ROWS, require_review=True, check_duplicates=True)
    assert draft_check["reviewed"] == 0
    assert draft_check["near_duplicates"] == []
    assert all("requires" in error and "review" in error for error in draft_check["errors"])
    assert len(draft_check["errors"]) == len(rows)

    splits = split_dataset(rows)
    sizes = {name: len(part) for name, part in splits.items()}
    assert sum(sizes.values()) == len(rows)
    assert all(sizes.values())
    # 15 families of 66-67 rows cannot hit 80/10/10 exactly; the splitter packs whole groups.
    assert 0.75 <= sizes["train"] / len(rows) <= 0.85, sizes
    assert 0.05 <= sizes["validation"] / len(rows) <= 0.15, sizes
    assert 0.05 <= sizes["test"] / len(rows) <= 0.15, sizes
    for field in ("role_family", "source_id", "template_family"):
        seen = {name: {row[field] for row in part} for name, part in splits.items()}
        assert not seen["train"] & seen["validation"], field
        assert not seen["train"] & seen["test"], field
        assert not seen["validation"] & seen["test"], field
    ids = [row["id"] for part in splits.values() for row in part]
    assert sorted(ids) == sorted(row["id"] for row in rows)


def test_generator_is_deterministic_and_matches_the_committed_file():
    regenerated = generate_rows()
    assert [(row["id"], row["content_sha256"]) for row in regenerated] == [
        (row["id"], row["content_sha256"]) for row in ROWS
    ]
