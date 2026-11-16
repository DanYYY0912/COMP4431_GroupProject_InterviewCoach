"""The labelling tool must never manufacture a label, and scoring must not move."""

import argparse
import json
import os

import pytest

from scripts import review_retrieval as rr


def write_rows(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def fixture_queries():
    return rr.read_jsonl(rr.DEFAULT_QUERIES)


def fixture_corpus():
    return rr.read_jsonl(rr.DEFAULT_CORPUS)


def label_everything(labels_dir, names=("Alice Chan", "Bob Lee", "Carol Ng", "Dan Ho")):
    """Label the whole fixture the way four reviewers would: one shard each."""
    queries = fixture_queries()
    for index, name in enumerate(names, 1):
        for query in rr.shard_rows(queries, f"{index}/{len(names)}"):
            rr.record_label(labels_dir, name, query["id"], query["relevant_ids"][:1])
    return queries


def test_shards_partition_the_fixture_without_overlap():
    queries = fixture_queries()
    assert len(queries) == 40
    shards = [rr.shard_rows(queries, f"{number}/4") for number in range(1, 5)]
    assigned = [query["id"] for shard in shards for query in shard]
    assert len(assigned) == len(set(assigned)) == 40
    assert set(assigned) == {query["id"] for query in queries}
    assert [len(shard) for shard in shards] == [10, 10, 10, 10]
    # A different shard count still covers each query exactly once.
    single = rr.shard_rows(queries, "40/40")
    assert len(single) == 1
    with pytest.raises(ValueError):
        rr.shard_rows(queries, "5/4")


def test_labels_round_trip_through_the_reviewers_own_file(tmp_path):
    record = rr.record_label(
        tmp_path, "Alice Chan", "eval-api-en-HK-0", ["eval-api-en-HK"]
    )
    path = rr.label_path(tmp_path, "Alice Chan")
    assert path == tmp_path / f"{rr.slug('Alice Chan')}.jsonl"
    assert rr.load_labels(tmp_path) == [record]
    assert set(json.loads(path.read_text().strip())) == {
        "query_id",
        "reviewer",
        "relevant_ids",
        "labelled_at",
    }
    assert record["labelled_at"].endswith("+00:00")


def test_relabelling_replaces_and_reviewers_stay_separate(tmp_path):
    rr.record_label(tmp_path, "Alice Chan", "q1", ["a"])
    rr.record_label(tmp_path, "alice chan", "q1", ["b"])
    rr.record_label(tmp_path, "Bob Lee", "q1", ["a"])
    labels = rr.load_labels(tmp_path)
    assert len(labels) == 2
    assert {label["relevant_ids"][0] for label in labels} == {"a", "b"}
    by_query = rr.latest_labels(labels)
    alice = next(
        entry
        for entry in by_query["q1"]
        if entry["reviewer"].casefold() == "alice chan"
    )
    assert alice["relevant_ids"] == ["b"]
    assert [entry["reviewer"] for entry in by_query["q1"]] == ["alice chan", "Bob Lee"]


def test_merge_refuses_incomplete_or_unattributable_labels(tmp_path):
    queries = fixture_queries()
    empty = tmp_path / "labels-empty"
    output = tmp_path / "reviewed.jsonl"
    with pytest.raises(ValueError, match="No human labels"):
        rr.merge_rows(queries, rr.load_labels(empty), output)
    assert not output.exists()

    partial = tmp_path / "labels-partial"
    for query in queries[:-1]:
        rr.record_label(partial, "Alice Chan", query["id"], query["relevant_ids"][:1])
    with pytest.raises(ValueError, match="1 of 40 queries have no human label"):
        rr.merge_rows(queries, rr.load_labels(partial), output)
    assert not output.exists()

    stray = tmp_path / "labels-stray"
    stray.mkdir()
    rr.record_label(stray, "Alice Chan", "no-such-query", ["a"])
    for query in queries:
        rr.record_label(stray, "Alice Chan", query["id"], query["relevant_ids"][:1])
    with pytest.raises(ValueError, match="absent from the fixture"):
        rr.merge_rows(queries, rr.load_labels(stray), output)
    assert not output.exists()

    forged = tmp_path / "labels-forged"
    forged.mkdir()
    (forged / "impostor.jsonl").write_text(
        json.dumps(
            {
                "query_id": "q1",
                "reviewer": "Alice Chan",
                "relevant_ids": ["a"],
                "labelled_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="not this file's reviewer"):
        rr.load_labels(forged)


def test_merge_writes_labels_and_nothing_else_sets_reviewed_by(tmp_path):
    queries = [
        dict(query, reviewed_by=["Dr Robot"], status="synthetic_diagnostic_fixture")
        for query in fixture_queries()[:2]
    ]
    labels_dir = tmp_path / "labels"
    rr.record_label(labels_dir, "Alice Chan", queries[0]["id"], ["eval-api-en-HK"])
    rr.record_label(labels_dir, "Bob Lee", queries[1]["id"], [])
    output = tmp_path / "reviewed.jsonl"
    rows = rr.merge_rows(queries, rr.load_labels(labels_dir), output)
    assert [row["reviewed_by"] for row in rows] == [["Alice Chan"], ["Bob Lee"]]
    assert "Dr Robot" not in output.read_text()
    assert rows[0]["relevant_ids"] == ["eval-api-en-HK"]
    assert rows[0]["synthetic_relevant_ids"] == queries[0]["relevant_ids"]
    assert rows[0]["status"] == "human_labelled"
    assert rows[1]["relevant_ids"] == []


def test_no_cli_option_sets_reviewed_by_or_marks_a_label(tmp_path):
    parser = rr.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["merge", "--reviewed-by", "Dr Robot"])
    with pytest.raises(SystemExit):
        parser.parse_args(["label", "--reviewer", "Alice", "--trusted"])
    with pytest.raises(ValueError, match="nonblank"):
        rr.record_label(tmp_path, "   ", "q1", ["a"])
    anonymous = tmp_path / "anonymous"
    anonymous.mkdir()
    (anonymous / "nobody.jsonl").write_text(
        json.dumps(
            {
                "query_id": "q1",
                "reviewer": " ",
                "relevant_ids": ["a"],
                "labelled_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="nonblank"):
        rr.load_labels(anonymous)


@pytest.mark.parametrize("interrupter", ["replace", "fsync"])
def test_atomic_write_leaves_the_last_complete_file_intact(
    tmp_path, monkeypatch, interrupter
):
    path = tmp_path / "alice.jsonl"
    rr.atomic_write(path, '{"reviewer": "Alice Chan"}\n')

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, interrupter, interrupt)
    with pytest.raises(KeyboardInterrupt):
        rr.atomic_write(path, '{"reviewer": "Alice Chan", "trunc')
    assert path.read_text() == '{"reviewer": "Alice Chan"}\n'
    assert [entry.name for entry in tmp_path.iterdir()] == ["alice.jsonl"]


def test_an_interrupted_session_keeps_every_finished_label(tmp_path):
    queries = fixture_queries()

    async def stub(rows, corpus):
        return {
            row["id"]: [{"id": "eval-api-en-HK", "text": "example"}] for row in rows
        }

    answers = iter(["all"])

    def ask(_prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    args = argparse.Namespace(
        reviewer="Alice Chan",
        shard="1/4",
        queries=rr.DEFAULT_QUERIES,
        corpus=rr.DEFAULT_CORPUS,
        labels_dir=tmp_path,
        limit=2,
    )
    with pytest.raises(KeyboardInterrupt):
        rr.label_session(args, ask=ask, retriever=stub)
    labels = rr.load_labels(tmp_path)
    assert [label["query_id"] for label in labels] == [queries[0]["id"]]
    assert labels[0]["relevant_ids"] == ["eval-api-en-HK"]


def test_session_renders_real_passages_and_resumes(tmp_path):
    async def stub(rows, corpus):
        return {
            row["id"]: [
                {"id": "eval-api-en-HK", "text": "API design includes validation."},
                {"id": "eval-testing-en-HK", "text": "Testing checks behaviour."},
            ]
            for row in rows
        }

    answers = iter(["", "2", "a"])
    args = argparse.Namespace(
        reviewer="Alice Chan",
        shard="1/40",
        queries=rr.DEFAULT_QUERIES,
        corpus=rr.DEFAULT_CORPUS,
        labels_dir=tmp_path,
        limit=1,
    )
    rr.label_session(args, ask=lambda _prompt="": next(answers), retriever=stub)
    labels = rr.load_labels(tmp_path)
    assert len(labels) == 1
    assert labels[0]["relevant_ids"] == ["eval-testing-en-HK"]
    # Second run finds the shard already labelled and asks nothing.
    assert (
        rr.label_session(args, ask=lambda _prompt="": pytest.fail("asked again")) == 0
    )


def test_render_numbers_passages_and_marks_selection():
    query = {"id": "q1", "query": "What does api involve?", "language": "en-HK"}
    passages = [
        {"id": "a", "text": "short"},
        {"id": "b", "text": "x" * (rr.DISPLAY_CHARS + 20)},
    ]
    text = rr.render(query, passages, {2}, 3, 40)
    assert "[3/40] q1" in text
    assert "QUERY: What does api involve?" in text
    assert "  [ ] 1  a" in text
    assert "  [*] 2  b" in text
    assert " …" in text
    assert "a = accept marked" in text
    assert "nothing for this query" in rr.render(query, [], set(), 1, 1)


def test_interpret_toggles_and_reads_one_action():
    marks, action = rr.interpret(set(), "2", 5)
    assert (marks, action) == ({2}, None)
    assert rr.interpret(marks, "2 4", 5) == ({4}, None)
    assert rr.interpret({1, 3}, "a", 5) == ({1, 3}, "accept")
    assert rr.interpret(set(), "all", 5) == (set(), "all")
    assert rr.interpret(set(), "n", 5)[1] == "none"
    assert rr.interpret(set(), "s", 5)[1] == "skip"
    assert rr.interpret(set(), "q", 5)[1] == "quit"
    assert rr.interpret(set(), "1,3,a", 5) == ({1, 3}, "accept")
    with pytest.raises(ValueError, match="1 to 5"):
        rr.interpret(set(), "6", 5)
    with pytest.raises(ValueError, match="Unknown input"):
        rr.interpret(set(), "approve", 5)


async def test_score_measures_against_human_labels_with_a_stubbed_retriever(tmp_path):
    corpus = [
        {"id": "a", "source": "s", "text": "a"},
        {"id": "b", "source": "s", "text": "b"},
        {"id": "c", "source": "s", "text": "c"},
        {"id": "d", "source": "s", "text": "d"},
        {"id": "e", "source": "s", "text": "e"},
        {"id": "f", "source": "s", "text": "f"},
    ]
    rows = [
        {"id": "q1", "query": "one", "relevant_ids": ["a"], "reviewed_by": ["Alice"]},
        {"id": "q2", "query": "two", "relevant_ids": ["f"], "reviewed_by": ["Bob"]},
        {"id": "q3", "query": "three", "relevant_ids": [], "reviewed_by": ["Carol"]},
    ]
    input_path = write_rows(tmp_path / "reviewed.jsonl", rows)

    async def stub(queries, corpus_rows):
        return {
            "q1": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}],
            "q2": [{"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}, {"id": "f"}],
            "q3": [{"id": "a"}],
        }

    output = tmp_path / "metrics.json"
    result = await rr.score(input_path, corpus, output, retriever=stub)

    records = {record["id"]: record for record in result["records"]}
    assert records["q1"]["recall_at_5"] == 1.0
    assert records["q1"]["citation_precision"] == 0.2
    assert records["q2"]["recall_at_5"] == 1.0  # rank 5 is inside k=5
    assert records["q2"]["citation_precision"] == 0.2
    assert records["q3"]["recall_at_5"] is None  # no human-labelled passage
    assert records["q3"]["citation_precision"] is None
    summary = result["summary"]
    assert summary["recall_at_5"] == 1.0
    assert summary["recall_at_5_denominator"] == 2
    assert summary["citation_precision"] == 0.2
    assert summary["citation_precision_denominator"] == 2
    assert result["reviewers"] == ["Alice", "Bob", "Carol"]
    assert result["status"] == "measured"
    assert result["date"] == rr.datetime.now(rr.UTC).date().isoformat()
    assert json.loads(output.read_text())["summary"] == summary


async def test_score_drops_passages_outside_top_five_and_prefers_generated_citations(
    tmp_path,
):
    corpus = [{"id": name, "source": "s", "text": name} for name in "abcdef"]
    rows = [
        {
            "id": "q1",
            "query": "one",
            "relevant_ids": ["f"],
            "reviewed_by": ["Alice"],
            "cited_ids": ["a", "f"],
            "supported_citation_ids": ["f"],
        }
    ]
    input_path = write_rows(tmp_path / "reviewed.jsonl", rows)

    async def stub(queries, corpus_rows):
        return {"q1": [{"id": name} for name in "abcdef"]}

    result = await rr.score(input_path, corpus, tmp_path / "m.json", retriever=stub)
    record = result["records"][0]
    assert record["retrieved_ids"] == ["a", "b", "c", "d", "e"]
    assert record["recall_at_5"] == 0.0
    assert record["citation_precision"] == 0.5


async def test_score_refuses_unreviewed_or_impossible_labels(tmp_path):
    corpus = [{"id": "a", "source": "s", "text": "a"}]

    async def stub(queries, corpus_rows):
        return {row["id"]: [{"id": "a"}] for row in queries}

    unreviewed = write_rows(
        tmp_path / "unreviewed.jsonl",
        [{"id": "q1", "query": "one", "relevant_ids": ["a"], "reviewed_by": []}],
    )
    with pytest.raises(ValueError, match="run merge first"):
        await rr.score(unreviewed, corpus, tmp_path / "m.json", retriever=stub)

    unknown = write_rows(
        tmp_path / "unknown.jsonl",
        [{"id": "q1", "query": "one", "relevant_ids": ["zzz"], "reviewed_by": ["A"]}],
    )
    with pytest.raises(ValueError, match="absent from the corpus"):
        await rr.score(unknown, corpus, tmp_path / "m.json", retriever=stub)


async def test_a_full_four_reviewer_merge_scores_the_whole_fixture(tmp_path):
    queries = fixture_queries()
    corpus = fixture_corpus()
    label_everything(tmp_path)
    merged = rr.merge_rows(
        queries, rr.load_labels(tmp_path), tmp_path / "reviewed.jsonl"
    )
    assert len(merged) == 40
    assert {row["status"] for row in merged} == {"human_labelled"}
    reviewers = sorted({name for row in merged for name in row["reviewed_by"]})
    assert reviewers == ["Alice Chan", "Bob Lee", "Carol Ng", "Dan Ho"]

    async def stub(rows, corpus_rows):
        return {row["id"]: [{"id": row["relevant_ids"][0]}] for row in rows}

    result = await rr.score(
        tmp_path / "reviewed.jsonl", corpus, tmp_path / "metrics.json", retriever=stub
    )
    assert result["summary"]["recall_at_5"] == 1.0
    assert result["summary"]["recall_at_5_denominator"] == 40
    assert result["reviewers"] == reviewers
